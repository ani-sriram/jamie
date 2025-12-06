import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the project root directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
from dotenv import load_dotenv
load_dotenv() 

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    PLACES_API_KEY = os.getenv("PLACES_API_KEY")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    # Timeouts and concurrency
    LLM_TIMEOUT_SECONDS = float(os.getenv("JAMIE_LLM_TIMEOUT_SECONDS", "30"))
    LLM_MAX_CONCURRENCY = int(os.getenv("JAMIE_LLM_MAX_CONCURRENCY", "2"))
    GCS_TIMEOUT_SECONDS = float(os.getenv("JAMIE_GCS_TIMEOUT_SECONDS", "20"))

    # GCP Storage Configuration
    BASE_BUCKET = os.getenv("BASE_BUCKET")

    @classmethod
    def validate(cls):
        if not cls.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        if not cls.BASE_BUCKET:
            raise ValueError("BASE_BUCKET environment variable is required")

        if not cls.PLACES_API_KEY:
            raise ValueError("PLACES_API_KEY environment variable is required")
