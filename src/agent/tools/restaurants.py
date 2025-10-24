import json
import os
from typing import List, Optional
from ..schemas import Restaurant, PlaceDetails
from ..clients import PlacesClient
class RestaurantTool:
    def __init__(self):
        self.places_client = PlacesClient()
        self.last_search_results: List[Restaurant] = []
    
    def search_restaurants(self, query: str) -> List[Restaurant]:
        results = []
        print(f"Searching restaurants with query: {query}")
        places = self.places_client.search_place(query)
        print(f"Found {len(places)} places")
        for place in places:
            try:
                restaurant = Restaurant(
                    name=place["displayName"]['text'],
                    id=place["name"],
                    location=place["formattedAddress"],
                    priceLevel=place.get("priceLevel", None),
                    description=place.get("editorial_summary",{"text":""}).get("text", "")
                )
                results.append(restaurant)
            except Exception as e:
                print(f"Error processing place {place}: {e}")
                results.append(place)
        self.last_search_results = results[:5]
        return self.last_search_results
    
    def get_last_search_results(self) -> List[Restaurant]:
        return self.last_search_results
    
    def get_restaurant_details(self, restaurant_id: str) -> PlaceDetails:
        details = self.places_client.get_place_details(restaurant_id)
        if details:
            try:
                restaurant_detail = PlaceDetails(**details)
                return restaurant_detail
            except Exception as e:
                print(f"Error processing details for restaurant {restaurant_id}: {e}")
        return None