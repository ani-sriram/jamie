import google.generativeai as genai
from typing import Optional
from config import Config
import requests
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout


class GeminiClient:
    _semaphore = threading.BoundedSemaphore(Config.LLM_MAX_CONCURRENCY)
    _executor = ThreadPoolExecutor(max_workers=Config.LLM_MAX_CONCURRENCY)
    _closed = False

    def __init__(self):
        Config.validate()
        genai.configure(api_key=Config.GEMINI_API_KEY)
        # Make generations deterministic for evaluations
        self.model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config={"temperature": 0},
        )
        print(
            f"[CONFIG] LLM_TIMEOUT_SECONDS={Config.LLM_TIMEOUT_SECONDS}, "
            f"LLM_MAX_CONCURRENCY={Config.LLM_MAX_CONCURRENCY}"
        )

    def _with_retry(self, func, max_attempts: int = 3, base_delay: float = 1.0):
        delay = base_delay
        for attempt in range(1, max_attempts + 1):
            try:
                return func()
            except FuturesTimeout:
                print(
                    f"[ERROR] LLM generation timed out "
                    f"(attempt {attempt}/{max_attempts})"
                )
                if attempt == max_attempts:
                    raise TimeoutError("LLM generation timed out")
                time.sleep(delay + random.uniform(0, 0.2))
                delay *= 2

    def generate_response(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        def call_model():
            with self._semaphore:
                # Use request_options timeout so the HTTP call itself aborts
                future = self._executor.submit(
                    self.model.generate_content,
                    full_prompt,
                    request_options={"timeout": Config.LLM_TIMEOUT_SECONDS},
                )
                try:
                    # Slight cushion over HTTP timeout to allow cleanup
                    return future.result(timeout=Config.LLM_TIMEOUT_SECONDS + 5.0)
                except FuturesTimeout:
                    # Ensure the background task does not keep occupying a worker
                    try:
                        future.cancel()
                    except Exception:
                        pass
                    raise

        response = self._with_retry(call_model)
        return response.text

    def generate_with_tools(
        self, prompt: str, tools: list, system_prompt: Optional[str] = None
    ) -> str:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        def call_model():
            with self._semaphore:
                future = self._executor.submit(
                    self.model.generate_content,
                    full_prompt,
                    tools=tools,
                    request_options={"timeout": Config.LLM_TIMEOUT_SECONDS},
                )
                try:
                    # Slight cushion over HTTP timeout to allow cleanup
                    return future.result(timeout=Config.LLM_TIMEOUT_SECONDS + 5.0)
                except FuturesTimeout:
                    # Ensure the background task does not keep occupying a worker
                    try:
                        future.cancel()
                    except Exception:
                        pass
                    raise

        response = self._with_retry(call_model)
        return response.text

    @classmethod
    def shutdown(cls):
        """Shut down the shared executor to cancel/stop in-flight LLM tasks."""
        if not cls._closed:
            try:
                cls._executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                # For older Python where cancel_futures is unavailable
                cls._executor.shutdown(wait=False)
            finally:
                cls._closed = True
                print("[SHUTDOWN] GeminiClient executor shut down")


class PlacesClient:
    def __init__(self):
        Config.validate()
        self.api_key = Config.PLACES_API_KEY
        self.base_url = "https://places.googleapis.com/v1"
        self.timeout = 10

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
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
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
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data
        except Exception as e:
            print(f"Error getting place details: {e}")
            return {}
