import json
from typing import List, Optional
from google.cloud import firestore
from agent.schemas import Recipe, Ingredient


class RecipeTool:
    def __init__(self, db_path: Optional[str] = None):
        """Initialize RecipeTool with Firestore client"""
        self.db = firestore.Client()
        self.collection = self.db.collection("recipes")

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
        doc = self.collection.document(recipe_id).get()
        if not doc.exists:
            return None
        return self._doc_to_recipe(doc.id, doc.to_dict())

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
            
            if ingredient_names and not any(ing.lower() in ingredients_text for ing in ingredient_names):
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
