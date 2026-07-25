import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    NEXT_PUBLIC_ORIGIN: str | None = os.getenv("NEXT_PUBLIC_ORIGIN")


settings = Settings()
