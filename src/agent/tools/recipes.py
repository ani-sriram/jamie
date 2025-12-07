import json
import sqlite3
import os
from typing import Any, Dict, List, Optional
from pathlib import Path
from agent.schemas import Recipe, Ingredient

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a SQLite connection with Row factory"""
    if db_path is None:
        db_path = str(Path(__file__).resolve().parents[2] / "data" / "recipes.db")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


class RecipeTool:
    def __init__(self, db_path: Optional[str] = None):
        """Initialize RecipeTool with optional custom db_path"""
        self.db_path = db_path
        self.last_search_results: List[Recipe] = []
        self._details_cache: Dict[str, Recipe] = {}  # Cache for recipe details

    def clear_cache(self):
        """Clear the details cache"""
        self._details_cache.clear()
        print("Recipe details cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cached_recipes": len(self._details_cache),
            "cached_ids": list(self._details_cache.keys()),
        }

    def get_indexed_recipe_list(self) -> str:
        """Return a formatted string of recipes with indices for display"""
        if not self.last_search_results:
            return "No recipes found."
        lines = []
        for i, recipe in enumerate(self.last_search_results, start=1):
            total_time = recipe.prep_time + recipe.cook_time
            lines.append(f"{i}. {recipe.title} ({recipe.difficulty}, {total_time} mins)")
        return "\n".join(lines)

    def get_recipe_by_position(self, position: int) -> Optional[Recipe]:
        """Get a recipe from the last search results by position (1-indexed)"""
        if 1 <= position <= len(self.last_search_results):
            return self.last_search_results[position - 1]
        return None

    def get_recipe_by_name(self, name: str) -> Optional[Recipe]:
        """Get a recipe from last search results by name (fuzzy match)"""
        name_lower = name.lower().strip()

        # First: Exact match
        for recipe in self.last_search_results:
            if recipe.title.lower() == name_lower:
                return recipe

        # Second: Partial/contains match
        for recipe in self.last_search_results:
            if name_lower in recipe.title.lower() or recipe.title.lower() in name_lower:
                return recipe

        # Third: Fuzzy word overlap matching
        name_words = set(name_lower.split())
        best_match = None
        best_score = 0
        for recipe in self.last_search_results:
            title_words = set(recipe.title.lower().split())
            overlap = len(name_words & title_words)
            if overlap > best_score:
                best_score = overlap
                best_match = recipe

        if best_match and best_score > 0:
            print(f"Found recipe by fuzzy match: {best_match.title} (score {best_score})")
            return best_match

        return None

    def find_recipes(
        self,
        ingredients: List[str],
        difficulty: Optional[str] = None,
        max_prep_time: Optional[int] = None,
    ) -> List[Recipe]:
        """Find recipes containing any of the given ingredients"""
        where_clauses = []
        params = []

        # Build ingredients clause (OR logic for backward compatibility)
        ing_clauses = []
        for ing in ingredients:
            ing_name = ing["name"] if isinstance(ing, dict) else str(ing)
            ing_clauses.append("ingredients_text LIKE '%'||?||'%'")
            params.append(ing_name.lower())
        where_clauses.append(f"({' OR '.join(ing_clauses)})")

        if difficulty:
            where_clauses.append("difficulty = ?")
            params.append(difficulty)

        if max_prep_time:
            where_clauses.append("prep_time <= ?")
            params.append(max_prep_time)

        sql = "SELECT * FROM recipes"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        sql += " LIMIT 5"

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [self._row_to_recipe(row) for row in rows]
        finally:
            conn.close()

    def get_recipe_by_id(self, recipe_id: str) -> Optional[Recipe]:
        """Get a single recipe by ID"""
        # Check cache first
        if recipe_id in self._details_cache:
            print(f"Cache hit for recipe: {recipe_id}")
            return self._details_cache[recipe_id]

        print(f"Cache miss for recipe: {recipe_id}, fetching from DB...")
        conn = get_connection(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
            row = cur.fetchone()
            if row:
                recipe = self._row_to_recipe(row)
                self._details_cache[recipe_id] = recipe  # Cache it
                print(f"Cached recipe: {recipe_id}")
                return recipe
            return None
        finally:
            conn.close()

    def search_by_title(self, title: str) -> List[Recipe]:
        """Search recipes by title (case-insensitive partial match)"""
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM recipes WHERE lower(title) LIKE '%'||?||'%' LIMIT 5",
                (title.lower(),),
            )
            rows = cur.fetchall()
            return [self._row_to_recipe(row) for row in rows]
        finally:
            conn.close()

    def search_recipes(
        self,
        recipe_title: Optional[str] = None,
        ingredients: Optional[List[str]] = None,
        excluded_ingredients: Optional[List[str]] = None,
        max_total_time: Optional[int] = None,
        max_prep_time: Optional[int] = None,
        difficulty: Optional[str] = None,
        servings: Optional[int] = None,
        tags: Optional[List[str]] = None,
        require_all_ingredients: bool = False,
        limit: int = 5,
    ) -> List[Recipe]:
        """
        Main search method supporting all filter combinations
        Args:
            ingredients: List of ingredient names to include
            excluded_ingredients: List of ingredient names to exclude
            max_total_time: Maximum total time (prep + cook) in minutes
            max_prep_time: Maximum prep time in minutes
            difficulty: Recipe difficulty level
            servings: Minimum number of servings
            tags: List of tags to match
            require_all_ingredients: If True, recipes must contain ALL ingredients (AND).
                                     If False, recipes can contain ANY ingredient (OR).
            limit: Maximum number of results to return
        """
        where_clauses = []
        params = []

        if recipe_title:
            where_clauses.append("title LIKE '%'||?||'%'")
            params.append(recipe_title.lower())  # case-insensitive partial match

        if ingredients:
            # Match ingredients with AND or OR based on require_all_ingredients
            # Also check tags so "pasta" matches recipes tagged with "pasta"
            ing_clauses = []
            for ing in ingredients:
                ing_name = ing["name"] if isinstance(ing, dict) else str(ing)
                ing_clauses.append("(ingredients_text LIKE '%'||?||'%' OR tags LIKE '%'||?||'%')")
                params.append(ing_name.lower())  # for ingredients_text
                params.append(ing_name.lower())  # for tags
            join_op = ' AND ' if require_all_ingredients else ' OR '
            where_clauses.append(f"({join_op.join(ing_clauses)})")

        if excluded_ingredients:
            # Exclude these ingredients (AND NOT logic)
            for ing in excluded_ingredients:
                ing_name = ing["name"] if isinstance(ing, dict) else str(ing)
                where_clauses.append("ingredients_text NOT LIKE '%'||?||'%'")
                params.append(ing_name.lower())

        if max_total_time:
            where_clauses.append("(prep_time + cook_time) <= ?")
            params.append(max_total_time)

        if max_prep_time:
            where_clauses.append("prep_time <= ?")
            params.append(max_prep_time)

        if difficulty:
            where_clauses.append("difficulty = ?")
            params.append(difficulty)

        if servings:
            where_clauses.append("servings >= ?")
            params.append(servings)

        if tags and not recipe_title:
            # Match any of the tags (OR logic)
            tag_clauses = []
            for tag in tags:
                tag_clauses.append("tags LIKE '%'||?||'%'")
                params.append(tag.lower())
            where_clauses.append(f"({' OR '.join(tag_clauses)})")

        sql = "SELECT * FROM recipes"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        sql += f" LIMIT {limit}"

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [self._row_to_recipe(row) for row in rows]
        finally:
            conn.close()

    def _row_to_recipe(self, row: sqlite3.Row) -> Recipe:
        """Convert a database row to a Recipe model"""
        if not row:
            raise ValueError("Cannot convert None row to Recipe")

        # Parse JSON fields
        ingredients = json.loads(row["ingredients_json"])
        instructions = json.loads(row["instructions_json"])

        # For backward compatibility, ensure ingredients is List[str]
        ingredients_list = []
        for ing in ingredients:
            if isinstance(ing, dict):
                ingredients_list.append(
                    Ingredient(
                        name=ing["name"],
                        quantity=ing.get("quantity"),
                        unit=ing.get("unit"),
                    )
                )
            else:
                ingredients_list.append(Ingredient(name=str(ing)))
        tags = []
        if row["tags"]:
            tags = [t.strip() for t in row["tags"].split(',')]
        return Recipe(
            id=row["id"],
            title=row["title"],
            ingredients=ingredients_list,
            instructions=instructions,
            prep_time=row["prep_time"],
            cook_time=row["cook_time"],
            difficulty=row["difficulty"],
            servings=row["servings"],
            tags=tags,
        )
