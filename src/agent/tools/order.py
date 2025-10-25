import uuid
from typing import Optional
from agent.schemas import Order
from agent.tools.restaurants import RestaurantTool

class OrderTool:
    def __init__(self):
        self.restaurant_tool = RestaurantTool()
        self.orders = {}

    def place_order(self, restaurant_id: str, meal_name: str) -> Order:
        restaurant = self.restaurant_tool.get_restaurant_by_id(restaurant_id)

        if not restaurant:
            raise ValueError(f"Restaurant with ID {restaurant_id} not found")

        if meal_name not in restaurant.meals:
            raise ValueError(f"Meal '{meal_name}' not available at {restaurant.name}")

        order_id = str(uuid.uuid4())
        order = Order(
            id=order_id,
            restaurant_id=restaurant_id,
            meal_id=meal_name,
            status="confirmed",
            total_price=self._calculate_price(restaurant.price_range),
        )

        self.orders[order_id] = order
        return order

    def get_order_status(self, order_id: str) -> Optional[Order]:
        return self.orders.get(order_id)

    def _calculate_price(self, price_range: str) -> float:
        price_map = {"$": 8.99, "$$": 15.99, "$$$": 24.99, "$$$$": 35.99}
        return price_map.get(price_range, 12.99)
