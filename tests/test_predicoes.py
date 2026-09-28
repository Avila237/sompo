"""Testes da tabela predicoes — contagem, integridade, distribuicao, SHAP, consistencia."""
import os
import sys

import pytest
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

SKIP_MSG = "Credenciais Supabase nao configuradas no .env"
VALID_GROUPS = {"ambiental", "geografico", "operacional", "equipamento", "operador", "manutencao"}


def has_credentials():
    return bool(
        os.getenv("SUPABASE_URL")
        and (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY"))
    )


pytestmark = [
    pytest.mark.rede,
    pytest.mark.skipif(not has_credentials(), reason=SKIP_MSG),
]


@pytest.fixture(scope="module")
def client():
    from backend.db.supabase_client import get_supabase_client

    return get_supabase_client()


def fetch_all(client, table, columns, order_by=None, eq=None):
    all_data = []
    page_size = 1000
    offset = 0
    while True:
        query = client.table(table).select(columns)
        # Filtros de igualdade opcionais, ex.: {"fonte": "seed"}.
        for column, value in (eq or {}).items():
            query = query.eq(column, value)
        if order_by:
            query = query.order(order_by)
        result = query.range(offset, offset + page_size - 1).execute()
        all_data.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    return all_data


@pytest.fixture(scope="module")
def sample_predicoes(client):
    result = client.table("predicoes").select("top_fatores_shap,modelo_versao").limit(50).execute()
    return result.data


# ---------------------------------------------------------------------------
# Contagem
# ---------------------------------------------------------------------------


class TestContagem:
    @pytest.mark.seed
    def test_predicoes_5000(self, client):
        result = client.table("predicoes").select("*", count="exact").limit(0).execute()
        assert result.count == 5000


# ---------------------------------------------------------------------------
# Integridade referencial
# ---------------------------------------------------------------------------


class TestIntegridade:
    def test_avaliacao_ids_existem(self, client):
        pred_ids = {r["avaliacao_id"] for r in fetch_all(client, "predicoes", "avaliacao_id")}
        aval_ids = {r["avaliacao_id"] for r in fetch_all(client, "avaliacoes", "avaliacao_id")}
        # Sem predicoes, a diferenca e vazia e o teste passaria sem verificar nada.
        assert pred_ids, "predicoes vazia: integridade referencial nao verificada"
        orphans = pred_ids - aval_ids
        assert len(orphans) == 0, f"avaliacao_ids orfaos em predicoes: {orphans}"


# ---------------------------------------------------------------------------
# Distribuicao das faixas preditas
# ---------------------------------------------------------------------------


class TestDistribuicao:
    # O denominador e a contagem real da tabela, nao 5000 fixo: cada POST na
    # API acrescenta uma predicao e deslocaria o percentual.
    def test_faixa_predita_baixo(self, client):
        total = client.table("predicoes").select("*", count="exact").limit(0).execute().count
        assert total > 0, "predicoes vazia: distribuicao indefinida"
        result = (
            client.table("predicoes")
            .select("*", count="exact")
            .eq("faixa_predita", "baixo")
            .limit(0)
            .execute()
        )
        pct = result.count / total * 100
        assert 30 <= pct <= 50, f"baixo: {pct:.1f}% (esperado ~40%)"

    def test_faixa_predita_medio(self, client):
        total = client.table("predicoes").select("*", count="exact").limit(0).execute().count
        assert total > 0, "predicoes vazia: distribuicao indefinida"
        result = (
            client.table("predicoes")
            .select("*", count="exact")
            .eq("faixa_predita", "medio")
            .limit(0)
            .execute()
        )
        pct = result.count / total * 100
        assert 25 <= pct <= 45, f"medio: {pct:.1f}% (esperado ~35%)"

    def test_faixa_predita_alto(self, client):
        total = client.table("predicoes").select("*", count="exact").limit(0).execute().count
        assert total > 0, "predicoes vazia: distribuicao indefinida"
        result = (
            client.table("predicoes")
            .select("*", count="exact")
            .eq("faixa_predita", "alto")
            .limit(0)
            .execute()
        )
        pct = result.count / total * 100
        assert 15 <= pct <= 35, f"alto: {pct:.1f}% (esperado ~25%)"


# ---------------------------------------------------------------------------
# SHAP JSON — estrutura e grupos validos
# ---------------------------------------------------------------------------


class TestShapJson:
    # Amostra vazia (ou lista de fatores vazia) faria os loops passarem sem
    # nenhum assert: o nao-vazio e checado antes de iterar.
    def test_top_fatores_tem_5_elementos(self, sample_predicoes):
        assert sample_predicoes, "Amostra de predicoes vazia"
        for r in sample_predicoes:
            fatores = r["top_fatores_shap"]
            assert len(fatores) == 5, f"Esperado 5 fatores, obteve {len(fatores)}"

    def test_fatores_tem_campos_obrigatorios(self, sample_predicoes):
        assert sample_predicoes, "Amostra de predicoes vazia"
        for r in sample_predicoes:
            assert r["top_fatores_shap"], "top_fatores_shap vazio"
            for fator in r["top_fatores_shap"]:
                assert "feature" in fator, "Campo 'feature' ausente"
                assert "shap_value" in fator, "Campo 'shap_value' ausente"
                assert "group" in fator, "Campo 'group' ausente"

    def test_grupos_validos(self, sample_predicoes):
        assert sample_predicoes, "Amostra de predicoes vazia"
        for r in sample_predicoes:
            assert r["top_fatores_shap"], "top_fatores_shap vazio"
            for fator in r["top_fatores_shap"]:
                assert fator["group"] in VALID_GROUPS, (
                    f"Grupo invalido: {fator['group']}"
                )


# ---------------------------------------------------------------------------
# Modelo versao
# ---------------------------------------------------------------------------


class TestModeloVersao:
    def test_todos_tem_modelo_versao(self, client):
        result = (
            client.table("predicoes")
            .select("*", count="exact")
            .is_("modelo_versao", "null")
            .limit(0)
            .execute()
        )
        assert result.count == 0, "Existem registros sem modelo_versao"

    def test_modelo_versao_preenchida(self, sample_predicoes):
        assert sample_predicoes, "Amostra de predicoes vazia"
        for r in sample_predicoes:
            assert r["modelo_versao"] and len(r["modelo_versao"]) > 0


# ---------------------------------------------------------------------------
# Consistencia score — correlacao entre real e predito
# ---------------------------------------------------------------------------


class TestConsistenciaScore:
    def test_correlacao_alta(self, client):
        import numpy as np

        pred_data = fetch_all(client, "predicoes", "avaliacao_id,risco_score_predito", order_by="avaliacao_id")
        # So avaliacoes do seed. Na ingestao pela API (fonte='telemetria') o
        # target risco_score e gravado igual a propria predicao
        # (backend/services/scoring.py), o que empurra a correlacao para 1.
        aval_data = fetch_all(
            client, "avaliacoes", "avaliacao_id,risco_score",
            order_by="avaliacao_id", eq={"fonte": "seed"},
        )

        aval_map = {r["avaliacao_id"]: float(r["risco_score"]) for r in aval_data}

        reais = []
        preditos = []
        for r in pred_data:
            aid = r["avaliacao_id"]
            if aid in aval_map:
                reais.append(aval_map[aid])
                preditos.append(float(r["risco_score_predito"]))

        # corrcoef exige ao menos 2 pares; com menos, devolve nan.
        assert len(reais) >= 2, f"Pares seed insuficientes para correlacao: {len(reais)}"
        corr = float(np.corrcoef(reais, preditos)[0, 1])
        assert corr > 0.90, f"Correlacao {corr:.4f} abaixo de 0.90"