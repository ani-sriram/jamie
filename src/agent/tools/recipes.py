import json
from typing import Any, Dict, List, Optional
from google.cloud import firestore
from agent.schemas import Recipe, Ingredient


class RecipeTool:
    def __init__(self, db_path: Optional[str] = None):
        """Initialize RecipeTool with Firestore client"""
        self.db = firestore.Client()
        self.collection = self.db.collection("recipes")
        self.last_search_results: List[Recipe] = []
        self._details_cache: Dict[str, Recipe] = {}

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
        query = self.collection
        
        ingredient_names = [ing["name"] if isinstance(ing, dict) else str(ing) for ing in ingredients]
        ingredient_names_lower = [name.lower() for name in ingredient_names]
        
        if difficulty:
            query = query.where("difficulty", "==", difficulty)
        
        if max_prep_time is not None:
            query = query.where("prep_time", "<=", max_prep_time)
        
        docs = query.limit(50).stream()
        results = []
        
        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue
            
            ingredients_text = data.get("ingredients_text", "").lower()
            if any(ing.lower() in ingredients_text for ing in ingredient_names):
                results.append(self._doc_to_recipe(doc.id, data))
                if len(results) >= 5:
                    break
        
        return results

    def get_recipe_by_id(self, recipe_id: str) -> Optional[Recipe]:
        """Get a single recipe by ID"""
        if recipe_id in self._details_cache:
            print(f"Cache hit for recipe: {recipe_id}")
            return self._details_cache[recipe_id]

        print(f"Cache miss for recipe: {recipe_id}, fetching from DB...")
        doc = self.collection.document(recipe_id).get()
        if not doc.exists:
            return None
        
        recipe = self._doc_to_recipe(doc.id, doc.to_dict())
        self._details_cache[recipe_id] = recipe
        print(f"Cached recipe: {recipe_id}")
        return recipe

    def search_by_title(self, title: str) -> List[Recipe]:
        """Search recipes by title (case-insensitive partial match)"""
        title_lower = title.lower()
        docs = self.collection.limit(50).stream()
        results = []
        
        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue
            
            if title_lower in data.get("title", "").lower():
                results.append(self._doc_to_recipe(doc.id, data))
                if len(results) >= 5:
                    break
        
        return results

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
        query = self.collection
        
        if difficulty:
            query = query.where("difficulty", "==", difficulty)
        
        if max_prep_time is not None:
            query = query.where("prep_time", "<=", max_prep_time)
        
        if servings is not None:
            query = query.where("servings", ">=", servings)
        
        if tags:
            query = query.where("tags", "array_contains_any", [tag.lower() for tag in tags])
        
        docs = query.limit(100).stream()
        results = []
        title_lower = recipe_title.lower() if recipe_title else None
        
        ingredient_names = []
        if ingredients:
            ingredient_names = [ing["name"] if isinstance(ing, dict) else str(ing) for ing in ingredients]
            ingredient_names_lower = [name.lower() for name in ingredient_names]
        
        excluded_names_lower = []
        if excluded_ingredients:
            excluded_names_lower = [ing["name"].lower() if isinstance(ing, dict) else str(ing).lower() for ing in excluded_ingredients]
        
        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue
            
            if title_lower and title_lower not in data.get("title", "").lower():
                continue
            
            ingredients_text = data.get("ingredients_text", "").lower()
            tags_text = ",".join(data.get("tags", [])).lower() if isinstance(data.get("tags"), list) else (data.get("tags", "") or "").lower()
            
            if ingredient_names:
                ingredient_matches = []
                for ing in ingredient_names:
                    ing_lower = ing.lower()
                    matches_ingredient = ing_lower in ingredients_text
                    matches_tag = ing_lower in tags_text
                    ingredient_matches.append(matches_ingredient or matches_tag)
                
                if require_all_ingredients:
                    if not all(ingredient_matches):
                        continue
                else:
                    if not any(ingredient_matches):
                        continue
            
            if excluded_names_lower and any(excluded in ingredients_text for excluded in excluded_names_lower):
                continue
            
            if max_total_time is not None:
                total_time = data.get("prep_time", 0) + data.get("cook_time", 0)
                if total_time > max_total_time:
                    continue
            
            results.append(self._doc_to_recipe(doc.id, data))
            if len(results) >= limit:
                break
        
        self.last_search_results = results
        return results

    def _doc_to_recipe(self, doc_id: str, data: dict) -> Recipe:
        """Convert a Firestore document to a Recipe model"""
        if not data:
            raise ValueError("Cannot convert None data to Recipe")
        
        ingredients_data = data.get("ingredients", [])
        if isinstance(ingredients_data, str):
            ingredients_data = json.loads(ingredients_data)
        
        instructions = data.get("instructions", [])
        if isinstance(instructions, str):
            instructions = json.loads(instructions)
        
        ingredients_list = []
        for ing in ingredients_data:
            if isinstance(ing, dict):
                ingredients_list.append(
                    Ingredient(
                        name=ing["name"],
                        quantity=ing.get("quantity"),
                        unit=ing.get("unit"),
                        calories=ing.get("calories"),
                    )
                )
            else:
                ingredients_list.append(Ingredient(name=str(ing)))
        
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",")] if tags else []
        
        return Recipe(
            id=doc_id,
            title=data.get("title", ""),
            ingredients=ingredients_list,
            instructions=instructions,
            prep_time=data.get("prep_time", 0),
            cook_time=data.get("cook_time", 0),
            difficulty=data.get("difficulty", ""),
            servings=data.get("servings", 0),
            tags=tags,
        )