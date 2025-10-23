import json
import os
from typing import List, Optional
from ..schemas import Restaurant, Recipe, Order
from ..clients import PlacesClient
class RestaurantTool:
    def __init__(self):
        self.places_client = PlacesClient()
    
    def search_restaurants(self, query: str) -> List[Restaurant]:
        results = []
        print(f"Searching restaurants with query: {query}")
        places = self.places_client.search_place(query)
        print(f"Found {len(places)} places")
        for place in places:
            try:
                restaurant = Restaurant(
                    name=place["displayName"]['text'],
                    location=place["formattedAddress"],
                    priceLevel=place.get("priceLevel", None),
                    description=place.get("editorial_summary",{"text":""}).get("text", "")
                )
                print(f"Found restaurant: {restaurant.name} at {restaurant.location}")
                results.append(restaurant)
            except Exception as e:
                print(f"Error processing place {place}: {e}")
                results.append(place)
        return results[:5]