"""
Cadastra ou atualiza um usuario da API (tabela `usuarios`, S4-18).

A senha e pedida no terminal, sem eco, e nunca passa por argumento de linha de
comando (que fica no historico do shell e na lista de processos).

Uso:
    python scripts/criar_usuario.py analista --perfil analista
    python scripts/criar_usuario.py joao --perfil operador --operador OP-0015
    python scripts/criar_usuario.py joao --desativar
"""

import argparse
import getpass
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.core.config import PERFIS_VALIDOS  # noqa: E402
from backend.core.security import gerar_hash  # noqa: E402
from backend.db.repository import get_client  # noqa: E402

SENHA_MINIMA = 12


def pedir_senha() -> str:
    senha = getpass.getpass("Senha: ")
    if len(senha) < SENHA_MINIMA:
        raise SystemExit(f"Senha curta: minimo de {SENHA_MINIMA} caracteres.")
    if getpass.getpass("Repita a senha: ") != senha:
        raise SystemExit("As senhas nao conferem.")
    return senha


def main() -> None:
    p = argparse.ArgumentParser(description="Cadastra ou atualiza um usuario da API")
    p.add_argument("usuario")
    p.add_argument("--perfil", choices=PERFIS_VALIDOS)
    p.add_argument("--operador", help="operador_id (obrigatorio para o perfil operador)")
    p.add_argument("--desativar", action="store_true", help="bloqueia o login sem apagar")
    args = p.parse_args()

    tabela = get_client().table("usuarios")
    if args.desativar:
        r = tabela.update({"ativo": False}).eq("usuario", args.usuario).execute()
        if not r.data:
            raise SystemExit(f"Usuario '{args.usuario}' nao existe.")
        print(f"Usuario '{args.usuario}' desativado.")
        return

    if not args.perfil:
        raise SystemExit("--perfil e obrigatorio para cadastrar.")
    if (args.perfil == "operador") != bool(args.operador):
        raise SystemExit("--operador vai junto com o perfil operador, e so com ele.")

    registro = {
        "usuario": args.usuario,
        "senha_hash": gerar_hash(pedir_senha()),
        "perfil": args.perfil,
        "operador_id": args.operador,
        "ativo": True,
    }
    # Upsert: rodar de novo com o mesmo usuario troca a senha e o perfil.
    tabela.upsert(registro, on_conflict="usuario").execute()
    print(f"Usuario '{args.usuario}' salvo com perfil {args.perfil}.")


if __name__ == "__main__":
    main()
