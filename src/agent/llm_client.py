import google.generativeai as genai
from typing import Optional
from config import Config
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

class GeminiClient:
    _semaphore = threading.BoundedSemaphore(Config.LLM_MAX_CONCURRENCY)
    _executor = ThreadPoolExecutor(max_workers=Config.LLM_MAX_CONCURRENCY)

    def __init__(self):
        Config.validate()
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            'gemini-2.5-flash',
            generation_config={"temperature": 0},
        )
    
    def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        try:
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            print(f"[DEBUG] Sending prompt to LLM:\n{full_prompt}")
            with self._semaphore:
                future = self._executor.submit(self.model.generate_content, full_prompt)
                response = future.result(timeout=Config.LLM_TIMEOUT_SECONDS)
                print(f"[DEBUG] LLM Response:\n{response.text}")
                return response.text
        except FuturesTimeout:
            print("[ERROR] LLM generation timed out")
            raise TimeoutError("LLM generation timed out")
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[ERROR] LLM generation failed:\n{error_trace}")
            print(f"[ERROR] Prompt was:\n{full_prompt}")
            raise
    
    def generate_with_tools(self, prompt: str, tools: list, system_prompt: Optional[str] = None) -> str:
        try:
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            with self._semaphore:
                future = self._executor.submit(self.model.generate_content, full_prompt, tools=tools)
                response = future.result(timeout=Config.LLM_TIMEOUT_SECONDS)
                return response.text
        except FuturesTimeout:
            print("[ERROR] LLM generation (tools) timed out")
            raise TimeoutError("LLM generation timed out")