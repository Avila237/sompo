"""
Testes da leitura de configuracao (S4-07).

O segredo JWT assina todos os tokens: se ele for publico (o placeholder do
.env.example) ou curto, qualquer um forja um token de qualquer perfil. A API
precisa recusar subir nesses casos, em vez de rodar com seguranca de fachada.
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.core.config import SEGREDO_JWT_MINIMO, validar_segredo_jwt  # noqa: E402

SEGREDO_BOM = "a" * SEGREDO_JWT_MINIMO


class TestSegredoJwt:
    def test_aceita_segredo_no_tamanho_minimo(self):
        assert validar_segredo_jwt(SEGREDO_BOM) == SEGREDO_BOM

    def test_aceita_segredo_longo(self):
        segredo = "f3" * 32
        assert validar_segredo_jwt(segredo) == segredo

    def test_recusa_um_byte_abaixo_do_minimo(self):
        with pytest.raises(EnvironmentError, match="JWT_SECRET_KEY"):
            validar_segredo_jwt("a" * (SEGREDO_JWT_MINIMO - 1))

    @pytest.mark.parametrize("valor", ["", " ", None])
    def test_recusa_vazio_ou_ausente(self, valor):
        with pytest.raises(EnvironmentError, match="JWT_SECRET_KEY"):
            validar_segredo_jwt(valor)

    def test_recusa_placeholder_antigo_do_env_example(self):
        """Quem copiou o exemplo antes desta correcao tem este valor no .env."""
        with pytest.raises(EnvironmentError, match="JWT_SECRET_KEY"):
            validar_segredo_jwt("trocar-em-producao")

    def test_placeholder_do_env_example_e_recusado(self):
        """O valor que vem no .env.example nunca pode subir a API."""
        caminho = os.path.join(PROJECT_ROOT, ".env.example")
        with open(caminho, encoding="utf-8-sig") as f:
            linhas = [l for l in f if l.startswith("JWT_SECRET_KEY=")]
        assert linhas, ".env.example precisa declarar JWT_SECRET_KEY"
        valor = linhas[0].split("=", 1)[1].strip()
        with pytest.raises(EnvironmentError):
            validar_segredo_jwt(valor)

    def test_mede_em_bytes_nao_em_caracteres(self):
        # 16 caracteres de 2 bytes em UTF-8 = 32 bytes: aceito.
        segredo = "ç" * (SEGREDO_JWT_MINIMO // 2)
        assert validar_segredo_jwt(segredo) == segredo


class TestEnvExample:
    def test_declara_toda_variavel_obrigatoria(self):
        """Quem copia o exemplo e preenche os placeholders sobe a API."""
        caminho = os.path.join(PROJECT_ROOT, ".env.example")
        with open(caminho, encoding="utf-8-sig") as f:
            declaradas = {
                l.split("=", 1)[0].strip()
                for l in f
                if "=" in l and not l.lstrip().startswith("#")
            }
        obrigatorias = {"SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "JWT_SECRET_KEY"}
        assert obrigatorias <= declaradas, f"faltando: {obrigatorias - declaradas}"
