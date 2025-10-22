import pytest
import json
import os
from src.agent.tools.restaurants import RestaurantTool
from src.agent.tools.recipes import RecipeTool
from src.agent.tools.order import OrderTool
from src.agent.schemas import IntentType

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
    def test_find_recipes(self):
        tool = RecipeTool()
        results = tool.find_recipes(["chicken", "pasta"])
        assert len(results) > 0
    
    def test_search_by_title(self):
        tool = RecipeTool()
        results = tool.search_by_title("carbonara")
        assert len(results) > 0

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