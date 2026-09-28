"""
Usuarios ficticios para os testes (S4-18).

O login le a tabela `usuarios`; aqui ela e trocada por um dicionario com hashes
reais, calculados uma vez. As senhas sao ficticias e so existem nos testes.
"""

import os
import sys
from unittest.mock import patch

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.core.security import gerar_hash  # noqa: E402
from backend.db import repository  # noqa: E402

SENHAS = {
    "analista": "senha-ficticia-analista",
    "gestor": "senha-ficticia-gestor",
    "tecnico": "senha-ficticia-tecnico",
    "operador": "senha-ficticia-operador",
    "joão": "coração-1",
    "desligado": "senha-ficticia-desligado",
}
_CADASTRO = {
    "analista": ("analista", None, True),
    "gestor": ("gestor", None, True),
    "tecnico": ("tecnico", None, True),
    "operador": ("operador", "OP-0015", True),
    "joão": ("gestor", None, True),
    "desligado": ("analista", None, False),
}
USUARIOS = {
    nome: {
        "usuario": nome,
        "senha_hash": gerar_hash(SENHAS[nome]),
        "perfil": perfil,
        "operador_id": operador_id,
        "ativo": ativo,
    }
    for nome, (perfil, operador_id, ativo) in _CADASTRO.items()
}


@pytest.fixture(autouse=True)
def tabela_de_usuarios_ficticia():
    with patch.object(repository, "buscar_usuario", side_effect=lambda u: USUARIOS.get(u)):
        yield
