import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "http://localhost:54321")
    SUPABASE_KEY: str | None = os.getenv("SUPABASE_KEY")
    NEXT_PUBLIC_ORIGIN: str | None = os.getenv("NEXT_PUBLIC_ORIGIN")


settings = Settings()
