"""Cliente Supabase encapsulado — le credenciais do .env."""
import os

from dotenv import load_dotenv
from supabase import create_client, Client


def get_supabase_client() -> Client:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL e SUPABASE_KEY devem estar definidos no .env"
        )
    return create_client(url, key)