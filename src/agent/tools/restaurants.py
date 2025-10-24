import json
import os
from typing import List, Optional, Dict, Any
from agent.schemas import Restaurant, PlaceDetails
from agent.clients import PlacesClient


class RestaurantTool:
    def __init__(self):
        self.places_client = PlacesClient()
        self.last_search_results: List[Restaurant] = []
        self.last_place_data: List[Dict[str, Any]] = []  # Store full place data

    def search_restaurants(self, query: str) -> List[Restaurant]:
        results = []
        print(f"Searching restaurants with query: {query}")
        places = self.places_client.search_place(query)
        print(f"Found {len(places)} places")

        # Store full place data for later use
        self.last_place_data = places[:5]

        for place in places:
            try:
                restaurant = Restaurant(
                    name=place["displayName"]["text"],
                    id=place["name"],
                    location=place["formattedAddress"],
                    priceLevel=place.get("priceLevel", None),
                    description=place.get("editorial_summary", {"text": ""}).get(
                        "text", ""
                    ),
                )
                results.append(restaurant)
            except Exception as e:
                print(f"Error processing place {place}: {e}")
                results.append(place)
        self.last_search_results = results[:5]
        return self.last_search_results

    def get_last_search_results(self) -> List[Restaurant]:
        return self.last_search_results

    def get_restaurant_details_by_index(self, index: int) -> Optional[PlaceDetails]:
        """Get restaurant details by index from last search results"""
        if not self.last_place_data or index < 0 or index >= len(self.last_place_data):
            print(f"Invalid restaurant index: {index}")
            return None

        place_id = self.last_place_data[index]["name"]
        return self.get_restaurant_details(place_id)

    def get_restaurant_details_by_name(self, name: str) -> Optional[PlaceDetails]:
        """Get restaurant details by name matching from last search results"""
        if not self.last_place_data:
            print("No previous search results available")
            return None

        # Find restaurant by name (case-insensitive partial match)
        name_lower = name.lower()
        for i, place in enumerate(self.last_place_data):
            place_name = place.get("displayName", {}).get("text", "").lower()
            if name_lower in place_name or place_name in name_lower:
                print(f"Found restaurant by name match: {place_name} (index {i})")
                return self.get_restaurant_details_by_index(i)

        print(f"No restaurant found matching name: {name}")
        return None

    def get_restaurant_details(self, restaurant_id: str) -> Optional[PlaceDetails]:
        details = self.places_client.get_place_details(restaurant_id)
        if details:
            try:
                restaurant_detail = PlaceDetails(**details)
                return restaurant_detail
            except Exception as e:
                print(f"Error processing details for restaurant {restaurant_id}: {e}")
        return None
