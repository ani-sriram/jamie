import json
import sqlite3
import os
from typing import List, Optional
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
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
            row = cur.fetchone()
            return self._row_to_recipe(row) if row else None
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
            limit: Maximum number of results to return
        """
        where_clauses = []
        params = []

        if recipe_title:
            where_clauses.append("title LIKE '%'||?||'%'")
            params.append(recipe_title.lower())  # case-insensitive partial match

        if ingredients:
            # Match any of the ingredients (OR logic)
            ing_clauses = []
            for ing in ingredients:
                ing_name = ing["name"] if isinstance(ing, dict) else str(ing)
                ing_clauses.append("ingredients_text LIKE '%'||?||'%'")
                params.append(ing_name.lower())
            where_clauses.append(f"({' OR '.join(ing_clauses)})")

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

        return Recipe(
            id=row["id"],
            title=row["title"],
            ingredients=ingredients_list,
            instructions=instructions,
            prep_time=row["prep_time"],
            cook_time=row["cook_time"],
            difficulty=row["difficulty"],
            servings=row["servings"],
        )
