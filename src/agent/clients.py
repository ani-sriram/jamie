import google.generativeai as genai
from typing import Optional
from ..config import Config
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

    def search_place(self, query: str) -> dict:
        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.priceLevel,places.editorialSummary",
        }
        payload = {
            "textQuery": query,
            "includedType": "restaurant",
        }
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("places", [])
