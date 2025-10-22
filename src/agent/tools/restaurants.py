import json
import os
from typing import List, Optional
from ..schemas import Restaurant, Recipe, Order

class RestaurantTool:
    def __init__(self):
        self.data_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", "restaurants.json")
        self.restaurants = self._load_restaurants()
    
    def _load_restaurants(self) -> List[Restaurant]:
        with open(self.data_file, 'r') as f:
            data = json.load(f)
        return [Restaurant(**restaurant) for restaurant in data]
    
    def search_restaurants(self, query: str, cuisine_type: Optional[str] = None, 
                          price_range: Optional[str] = None) -> List[Restaurant]:
        results = []
        query_lower = query.lower()
        
        for restaurant in self.restaurants:
            if (query_lower in restaurant.name.lower() or 
                query_lower in restaurant.cuisine_type.lower() or
                any(query_lower in meal.lower() for meal in restaurant.meals)):
                
                if cuisine_type and restaurant.cuisine_type.lower() != cuisine_type.lower():
                    continue
                if price_range and restaurant.price_range != price_range:
                    continue
                    
                results.append(restaurant)
        
        return results[:5]
    
    def get_restaurant_by_id(self, restaurant_id: str) -> Optional[Restaurant]:
        for restaurant in self.restaurants:
            if restaurant.id == restaurant_id:
                return restaurant
        return None