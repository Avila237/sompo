"""Testes do Supabase — conexao, contagens, integridade, distribuicao, tipos e indexes."""
import os
import sys

import pytest
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

SKIP_MSG = "Credenciais Supabase nao configuradas no .env"


def has_credentials():
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))


pytestmark = pytest.mark.skipif(not has_credentials(), reason=SKIP_MSG)


@pytest.fixture(scope="module")
def client():
    from backend.db.supabase_client import get_supabase_client

    return get_supabase_client()


def fetch_all_column(client, table: str, column: str) -> list:
    all_values = []
    page_size = 1000
    offset = 0
    while True:
        result = (
            client.table(table)
            .select(column)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        all_values.extend(r[column] for r in result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    return all_values


# ---------------------------------------------------------------------------
# Conexao
# ---------------------------------------------------------------------------


class TestConexao:
    def test_cliente_conecta(self, client):
        result = (
            client.table("equipamentos")
            .select("equipamento_id", count="exact")
            .limit(1)
            .execute()
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Contagens
# ---------------------------------------------------------------------------


class TestContagens:
    def test_equipamentos_aprox_200(self, client):
        result = client.table("equipamentos").select("*", count="exact").limit(0).execute()
        assert 190 <= result.count <= 210

    def test_operadores_aprox_80(self, client):
        result = client.table("operadores").select("*", count="exact").limit(0).execute()
        assert 70 <= result.count <= 90

    @pytest.mark.seed
    def test_avaliacoes_exatamente_5000(self, client):
        result = client.table("avaliacoes").select("*", count="exact").limit(0).execute()
        assert result.count == 5000

    @pytest.mark.seed
    def test_predicoes_5000(self, client):
        result = client.table("predicoes").select("*", count="exact").limit(0).execute()
        assert result.count == 5000


# ---------------------------------------------------------------------------
# Integridade referencial
# ---------------------------------------------------------------------------


class TestIntegridade:
    def test_avaliacoes_equipamento_ids_existem(self, client):
        equip_ids = set(fetch_all_column(client, "equipamentos", "equipamento_id"))
        aval_equip_ids = set(fetch_all_column(client, "avaliacoes", "equipamento_id"))
        orphans = aval_equip_ids - equip_ids
        assert len(orphans) == 0, f"Equipamento IDs orfaos: {orphans}"

    def test_avaliacoes_operador_ids_existem(self, client):
        ops_ids = set(fetch_all_column(client, "operadores", "operador_id"))
        aval_ops_ids = set(fetch_all_column(client, "avaliacoes", "operador_id"))
        orphans = aval_ops_ids - ops_ids
        assert len(orphans) == 0, f"Operador IDs orfaos: {orphans}"


# ---------------------------------------------------------------------------
# Distribuicao de faixa_risco
# ---------------------------------------------------------------------------


class TestDistribuicao:
    def test_faixa_risco_baixo(self, client):
        result = (
            client.table("avaliacoes")
            .select("*", count="exact")
            .eq("faixa_risco", "baixo")
            .limit(0)
            .execute()
        )
        pct = result.count / 5000 * 100
        assert 32 <= pct <= 48, f"baixo: {pct:.1f}% (esperado ~40%)"

    def test_faixa_risco_medio(self, client):
        result = (
            client.table("avaliacoes")
            .select("*", count="exact")
            .eq("faixa_risco", "medio")
            .limit(0)
            .execute()
        )
        pct = result.count / 5000 * 100
        assert 27 <= pct <= 43, f"medio: {pct:.1f}% (esperado ~35%)"

    def test_faixa_risco_alto(self, client):
        result = (
            client.table("avaliacoes")
            .select("*", count="exact")
            .eq("faixa_risco", "alto")
            .limit(0)
            .execute()
        )
        pct = result.count / 5000 * 100
        assert 17 <= pct <= 33, f"alto: {pct:.1f}% (esperado ~25%)"


# ---------------------------------------------------------------------------
# Tipos e nulls
# ---------------------------------------------------------------------------


class TestTipos:
    def test_vibracao_g_tem_nulls(self, client):
        result = (
            client.table("avaliacoes")
            .select("*", count="exact")
            .is_("vibracao_g", "null")
            .limit(0)
            .execute()
        )
        assert result.count > 0, "vibracao_g deveria ter valores null"

    def test_temperatura_motor_tem_nulls(self, client):
        result = (
            client.table("avaliacoes")
            .select("*", count="exact")
            .is_("temperatura_motor", "null")
            .limit(0)
            .execute()
        )
        assert result.count > 0, "temperatura_motor deveria ter valores null"

    def test_vibracao_g_tem_valores_nao_null(self, client):
        total = client.table("avaliacoes").select("*", count="exact").limit(0).execute().count
        nulls = (
            client.table("avaliacoes")
            .select("*", count="exact")
            .is_("vibracao_g", "null")
            .limit(0)
            .execute()
            .count
        )
        assert total - nulls > 0, "vibracao_g deveria ter valores nao-null tambem"

    def test_temperatura_motor_tem_valores_nao_null(self, client):
        total = client.table("avaliacoes").select("*", count="exact").limit(0).execute().count
        nulls = (
            client.table("avaliacoes")
            .select("*", count="exact")
            .is_("temperatura_motor", "null")
            .limit(0)
            .execute()
            .count
        )
        assert total - nulls > 0, "temperatura_motor deveria ter valores nao-null tambem"


# ---------------------------------------------------------------------------
# Indexes (verifica que consultas indexadas retornam sem erro)
# ---------------------------------------------------------------------------


class TestIndexes:
    def test_consulta_por_equipamento_id(self, client):
        result = (
            client.table("avaliacoes")
            .select("avaliacao_id")
            .eq("equipamento_id", "EQ-0001")
            .limit(1)
            .execute()
        )
        assert isinstance(result.data, list)

    def test_consulta_por_operador_id(self, client):
        result = (
            client.table("avaliacoes")
            .select("avaliacao_id")
            .eq("operador_id", "OP-0001")
            .limit(1)
            .execute()
        )
        assert isinstance(result.data, list)

    def test_consulta_por_timestamp(self, client):
        result = (
            client.table("avaliacoes")
            .select("avaliacao_id")
            .gte("timestamp", "2025-01-01")
            .limit(1)
            .execute()
        )
        assert isinstance(result.data, list)

    def test_consulta_por_faixa_risco(self, client):
        result = (
            client.table("avaliacoes")
            .select("avaliacao_id")
            .eq("faixa_risco", "alto")
            .limit(1)
            .execute()
        )
        assert isinstance(result.data, list)