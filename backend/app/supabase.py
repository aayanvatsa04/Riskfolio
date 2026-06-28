from supabase import Client, create_client

from app.settings import settings

supabase: Client | None = None

if settings.SUPABASE_URL and settings.SUPABASE_KEY:
    supabase = create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_KEY,
    )
