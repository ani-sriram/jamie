import google.generativeai as genai
from typing import Optional
from config import Config

class GeminiClient:
    def __init__(self):
        Config.validate()
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        try:
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            print(f"[DEBUG] Sending prompt to LLM:\n{full_prompt}")
            response = self.model.generate_content(full_prompt)
            print(f"[DEBUG] LLM Response:\n{response.text}")
            return response.text
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[ERROR] LLM generation failed:\n{error_trace}")
            print(f"[ERROR] Prompt was:\n{full_prompt}")
            raise
    
    def generate_with_tools(self, prompt: str, tools: list, system_prompt: Optional[str] = None) -> str:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        response = self.model.generate_content(
            full_prompt,
            tools=tools
        )
        return response.text