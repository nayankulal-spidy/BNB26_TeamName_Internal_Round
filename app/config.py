import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    groq_api_url: str = "https://api.groq.com/openai/v1/chat/completions"
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production-relearn")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./relearn.db")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    max_intervention_cycles: int = 3
    low_confidence_threshold: float = 0.55


settings = Settings()
