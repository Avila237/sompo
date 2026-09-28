"""Login contra a tabela `usuarios` (S4-18)."""

from functools import lru_cache

from backend.core.exceptions import CredenciaisInvalidas
from backend.core.security import gerar_hash, senha_confere
from backend.db import repository as repo


@lru_cache(maxsize=1)
def _hash_ficticio() -> str:
    return gerar_hash("usuario-inexistente")


def autenticar(usuario: str, senha: str) -> dict:
    """
    Devolve {"perfil", "operador_id"} ou levanta CredenciaisInvalidas.

    Usuario inexistente ou inativo tambem calcula um hash: sem isso, a resposta
    rapida revelaria pelo tempo quais usuarios existem.
    """
    registro = repo.buscar_usuario(usuario)
    if registro is None or not registro["ativo"]:
        senha_confere(senha, _hash_ficticio())
        raise CredenciaisInvalidas()
    if not senha_confere(senha, registro["senha_hash"]):
        raise CredenciaisInvalidas()
    return {"perfil": registro["perfil"], "operador_id": registro["operador_id"]}
