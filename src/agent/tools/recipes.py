import json
import os
from typing import List, Optional
from ..schemas import Recipe

class RecipeTool:
    def __init__(self):
        self.data_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", "recipes.json")
        self.recipes = self._load_recipes()
    
    def _load_recipes(self) -> List[Recipe]:
        with open(self.data_file, 'r') as f:
            data = json.load(f)
        return [Recipe(**recipe) for recipe in data]
    
    def find_recipes(self, ingredients: List[str], difficulty: Optional[str] = None,
                    max_prep_time: Optional[int] = None) -> List[Recipe]:
        results = []
        ingredients_lower = [ing.lower() for ing in ingredients]
        
        for recipe in self.recipes:
            recipe_ingredients_lower = [ing.lower() for ing in recipe.ingredients]
            
            if any(ing in recipe_ingredients_lower for ing in ingredients_lower):
                if difficulty and recipe.difficulty != difficulty:
                    continue
                if max_prep_time and recipe.prep_time > max_prep_time:
                    continue
                    
                results.append(recipe)
        
        return results[:5]
    
    def get_recipe_by_id(self, recipe_id: str) -> Optional[Recipe]:
        for recipe in self.recipes:
            if recipe.id == recipe_id:
                return recipe
        return None
    
    def search_by_title(self, title: str) -> List[Recipe]:
        results = []
        title_lower = title.lower()
        
        for recipe in self.recipes:
            if title_lower in recipe.title.lower():
                results.append(recipe)
        
        return results[:5]