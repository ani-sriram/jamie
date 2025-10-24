import google.generativeai as genai
from typing import Optional
from config import Config
import requests


class GeminiClient:
    def __init__(self):
        Config.validate()
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def generate_response(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        response = self.model.generate_content(full_prompt)
        return response.text

    def generate_with_tools(
        self, prompt: str, tools: list, system_prompt: Optional[str] = None
    ) -> str:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        response = self.model.generate_content(full_prompt, tools=tools)
        return response.text


class PlacesClient:
    def __init__(self):
        Config.validate()
        self.api_key = Config.PLACES_API_KEY
        self.base_url = "https://places.googleapis.com/v1"

    def search_place(self, query: str) -> dict:
        url = f"{self.base_url}/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.priceLevel,places.editorialSummary,places.name",
        }
        payload = {
            "textQuery": query,
            "includedType": "restaurant",
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("places", [])
        except Exception as e:
            print(f"Error searching places: {e}")
            return {}

    def get_place_details(self, place_id: str) -> dict:
        url = f"{self.base_url}/{place_id}"
        field_mask = (
            "displayName,formattedAddress,priceLevel,editorialSummary,name,"
            "regularOpeningHours,googleMapsLinks,regularSecondaryOpeningHours"
        )
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask,
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data
        except Exception as e:
            print(f"Error getting place details: {e}")
            return {}
