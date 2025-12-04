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
        self._details_cache: Dict[str, PlaceDetails] = (
            {}
        )  # Cache for restaurant details

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

    def clear_cache(self):
        """Clear the details cache"""
        self._details_cache.clear()
        print("Restaurant details cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cached_restaurants": len(self._details_cache),
            "cached_ids": list(self._details_cache.keys()),
        }

    def get_restaurant_details_by_index(self, index: int) -> Optional[PlaceDetails]:
        """Get restaurant details by index from last search results"""
        if not self.last_place_data or index < 0 or index >= len(self.last_place_data):
            print(f"Invalid restaurant index: {index}")
            return None

        place_id = self.last_place_data[index]["name"]
        return self.get_restaurant_details(place_id)

    def get_restaurant_details_by_name(self, name: str) -> Optional[PlaceDetails]:
        """Get restaurant details by name matching from last search results using fuzzy matching"""
        if not self.last_place_data:
            print("No previous search results available")
            return None

        # Normalize the search name
        name_lower = name.lower().strip()

        # First pass: exact match
        for i, place in enumerate(self.last_place_data):
            place_name = place.get("displayName", {}).get("text", "").lower()
            if name_lower == place_name:
                print(f"Found restaurant by exact match: {place_name} (index {i})")
                return self.get_restaurant_details_by_index(i)

        # Second pass: contains match
        for i, place in enumerate(self.last_place_data):
            place_name = place.get("displayName", {}).get("text", "").lower()
            if name_lower in place_name or place_name in name_lower:
                print(f"Found restaurant by partial match: {place_name} (index {i})")
                return self.get_restaurant_details_by_index(i)

        # Third pass: word overlap matching (fuzzy)
        name_words = set(name_lower.split())
        best_match_idx = -1
        best_match_score = 0

        for i, place in enumerate(self.last_place_data):
            place_name = place.get("displayName", {}).get("text", "").lower()
            place_words = set(place_name.split())
            # Calculate word overlap score
            overlap = len(name_words & place_words)
            if overlap > best_match_score:
                best_match_score = overlap
                best_match_idx = i

        if best_match_idx >= 0 and best_match_score > 0:
            matched_name = (
                self.last_place_data[best_match_idx]
                .get("displayName", {})
                .get("text", "")
            )
            print(
                f"Found restaurant by fuzzy match: {matched_name} (index {best_match_idx}, score {best_match_score})"
            )
            return self.get_restaurant_details_by_index(best_match_idx)

        print(f"No restaurant found matching name: {name}")
        return None

    def get_indexed_restaurant_list(self) -> str:
        """Return a formatted string of restaurants with indices for display"""
        if not self.last_search_results:
            return "No restaurants found."

        lines = []
        for i, restaurant in enumerate(self.last_search_results, start=1):
            lines.append(f"{i}. {restaurant.name} - {restaurant.location}")
        return "\n".join(lines)

    def get_restaurant_by_position(self, position: int) -> Optional[PlaceDetails]:
        """Get restaurant by 1-based position (e.g., 'the first one' = 1)"""
        index = position - 1  # Convert to 0-based index
        return self.get_restaurant_details_by_index(index)

    def get_restaurant_details(self, restaurant_id: str) -> Optional[PlaceDetails]:
        # Check cache first
        if restaurant_id in self._details_cache:
            print(f"Cache hit for restaurant: {restaurant_id}")
            return self._details_cache[restaurant_id]

        print(f"Cache miss for restaurant: {restaurant_id}, fetching from API...")
        details = self.places_client.get_place_details(restaurant_id)
        if details:
            try:
                restaurant_detail = PlaceDetails(**details)
                # Store in cache
                self._details_cache[restaurant_id] = restaurant_detail
                print(f"Cached details for restaurant: {restaurant_id}")
                return restaurant_detail
            except Exception as e:
                print(f"Error processing details for restaurant {restaurant_id}: {e}")
        return None
