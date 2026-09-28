"""Cliente Supabase dos scripts de carga — le credenciais do .env."""
import os

from dotenv import load_dotenv
from supabase import create_client, Client


def get_supabase_client() -> Client:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    # Mesma chave que a API usa (core/config.py). SUPABASE_KEY e o nome antigo.
    # Com a anon key a RLS nega tudo: delete apagaria zero linhas em silencio.
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem estar definidos no .env"
        )
    return create_client(url, key)
