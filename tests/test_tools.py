import pytest
import json
import os
from pathlib import Path
from agent.tools.restaurants import RestaurantTool
from agent.tools.recipes import RecipeTool
from agent.tools.order import OrderTool
from agent.schemas import IntentType, Ingredient

class TestRestaurantTool:
    def test_search_restaurants(self):
        tool = RestaurantTool()
        results = tool.search_restaurants("pizza")
        assert len(results) > 0
        assert any("pizza" in meal.lower() for restaurant in results for meal in restaurant.meals)
    
    def test_get_restaurant_by_id(self):
        tool = RestaurantTool()
        restaurant = tool.get_restaurant_by_id("rest_001")
        assert restaurant is not None
        assert restaurant.name == "Mario's Italian Kitchen"

class TestRecipeTool:
    @pytest.fixture
    def recipe_tool(self, tmp_path):
        """Create a RecipeTool instance with a temporary test database"""
        # Create temp DB path
        db_path = tmp_path / "test_recipes.db"
        
        # Import the migration script
        from scripts import migrate_db
        
        # Run migration with temp DB
        migrate_db.migrate_recipes(
            Path(__file__).parent.parent / "src" / "data" / "recipes.json",
            db_path
        )
        
        # Create tool instance with test DB
        tool = RecipeTool(str(db_path))
        return tool
    
    def test_find_recipes(self, recipe_tool):
        results = recipe_tool.find_recipes(["chicken"])
        assert len(results) > 0
        assert any("chicken" in [ing.name.lower() for ing in r.ingredients] for r in results)
        
        # Test with difficulty filter
        results = recipe_tool.find_recipes(["chicken"], difficulty="easy")
        assert all(r.difficulty == "easy" for r in results)
        
        # Test with prep time filter
        results = recipe_tool.find_recipes(["chicken"], max_prep_time=20)
        assert all(r.prep_time <= 20 for r in results)
    
    def test_search_by_title(self, recipe_tool):
        results = recipe_tool.search_by_title("carbonara")
        assert len(results) > 0
        assert "carbonara" in results[0].title.lower()
    
    def test_search_recipes(self, recipe_tool):
        # Test ingredient search
        results = recipe_tool.search_recipes(
            ingredients=[{"name": "chicken"}],
            max_total_time=45,
            difficulty="easy"
        )
        assert len(results) > 0
        assert all(r.difficulty == "easy" for r in results)
        assert all((r.prep_time + r.cook_time) <= 45 for r in results)
        
        # Test tag search
        results = recipe_tool.search_recipes(tags=["italian"])
        assert len(results) > 0
        assert all("italian" in r.tags for r in results)
        
        # Test excluded ingredients
        results = recipe_tool.search_recipes(
            ingredients=[{"name": "pasta"}],
            excluded_ingredients=["seafood"]
        )
        assert len(results) > 0
        assert all("seafood" not in [ing.name.lower() for ing in r.ingredients] for r in results)
    
    def test_get_recipe_by_id(self, recipe_tool):
        # Get a recipe we know exists
        recipe = recipe_tool.get_recipe_by_id("recipe_001")
        assert recipe is not None
        assert recipe.id == "recipe_001"
        assert recipe.title == "Classic Spaghetti Carbonara"
        
        # Test nonexistent recipe
        recipe = recipe_tool.get_recipe_by_id("nonexistent")
        assert recipe is None

class TestOrderTool:
    def test_place_order(self):
        order_tool = OrderTool()
        order = order_tool.place_order("rest_001", "Margherita Pizza")
        assert order.status == "confirmed"
        assert order.restaurant_id == "rest_001"
        assert order.meal_id == "Margherita Pizza"
    
    def test_get_order_status(self):
        order_tool = OrderTool()
        order = order_tool.place_order("rest_001", "Margherita Pizza")
        retrieved_order = order_tool.get_order_status(order.id)
        assert retrieved_order is not None
        assert retrieved_order.id == order.id

if __name__ == "__main__":
    pytest.main([__file__])