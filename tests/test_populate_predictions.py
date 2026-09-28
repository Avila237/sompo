"""
Reexecutar scripts/populate_predictions.py nao duplica nem reescreve predicoes (S4-13).

O banco e um falso em memoria que imita o indice unico de predicoes, lido da
propria migration, e a semantica do upsert do PostgREST: com ignore_duplicates,
o par que ja existe fica como esta (ON CONFLICT DO NOTHING). Modelo e SHAP sao
stubs; nenhum teste abre rede nem le models/.
"""

import os
import re
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts import populate_predictions as pp  # noqa: E402

MIGRATION_INTEGRIDADE = os.path.join(
    PROJECT_ROOT, "supabase", "migrations", "20260928120000_sprint04_integridade.sql"
)
FEATURES = ["horas_operacao", "historico_sinistros"]


def _chave_unica_de_predicoes() -> set:
    with open(MIGRATION_INTEGRIDADE, encoding="utf-8") as f:
        sql = f.read()
    m = re.search(r"uq_predicoes_avaliacao_versao\s+ON\s+predicoes\s*\(([^)]*)\)", sql)
    assert m, "indice unico de predicoes nao encontrado na migration"
    return {c.strip() for c in m.group(1).split(",")}


class BancoFalso:
    def __init__(self, avaliacoes):
        self.avaliacoes = avaliacoes
        self.predicoes = []
        self.upserts = []
        self.apagou = False
        self.chave = _chave_unica_de_predicoes()

    def table(self, nome):
        return _Consulta(self, nome)

    def _existente(self, registro):
        chave = {c: registro[c] for c in self.chave}
        return next(
            (p for p in self.predicoes if all(p[c] == v for c, v in chave.items())), None
        )

    def _acrescentar(self, registro):
        self.predicoes.append({**registro, "predicao_id": len(self.predicoes) + 1})

    def upsert(self, registros, on_conflict, ignore_duplicates):
        self.upserts.append({"on_conflict": on_conflict, "ignore_duplicates": ignore_duplicates})
        # Postgres recusa ON CONFLICT sem indice unico com exatamente essas colunas.
        colunas = {c.strip() for c in (on_conflict or "").split(",") if c.strip()}
        if colunas != self.chave:
            raise AssertionError(f"sem indice unico para ON CONFLICT ({on_conflict})")
        for r in registros:
            existente = self._existente(r)
            if existente is None:
                self._acrescentar(r)
            elif not ignore_duplicates:
                existente.update(r)  # merge-duplicates: sobrescreveria o historico

    def insert(self, registros):
        for r in registros:
            if self._existente(r) is not None:
                raise AssertionError("duplicate key value violates uq_predicoes_avaliacao_versao")
            self._acrescentar(r)


class _Consulta:
    def __init__(self, banco, tabela):
        self.banco = banco
        self.tabela = tabela
        self.contar = False
        self.filtros = {}
        self.fatia = None
        self.escrita = None

    def select(self, *colunas, count=None):
        self.contar = count == "exact"
        return self

    def eq(self, coluna, valor):
        self.filtros[coluna] = valor
        return self

    def order(self, coluna):
        return self

    def range(self, inicio, fim):
        self.fatia = (inicio, fim + 1)
        return self

    def limit(self, n):
        return self

    def upsert(self, registros, on_conflict="", ignore_duplicates=False, **_):
        self.escrita = lambda: self.banco.upsert(list(registros), on_conflict, ignore_duplicates)
        return self

    def insert(self, registros):
        self.escrita = lambda: self.banco.insert(list(registros))
        return self

    def delete(self):
        self.banco.apagou = True
        return self

    def gte(self, *a):
        return self

    def execute(self):
        if self.escrita:
            self.escrita()
            return SimpleNamespace(data=[], count=None)
        linhas = self.banco.avaliacoes if self.tabela == "avaliacoes" else self.banco.predicoes
        linhas = [r for r in linhas if all(r.get(c) == v for c, v in self.filtros.items())]
        linhas = sorted(linhas, key=lambda r: r.get("avaliacao_id"))
        if self.fatia:
            linhas = linhas[self.fatia[0]:self.fatia[1]]
        return SimpleNamespace(data=linhas, count=len(linhas) if self.contar else None)


class ModeloFalso:
    def __init__(self, scores):
        self.scores = np.asarray(scores, dtype=float)

    def predict(self, X):
        return self.scores[: len(X)]


@pytest.fixture
def banco():
    # Tres avaliacoes do seed e uma de telemetria, que o script nao pode parear.
    return BancoFalso([
        {"avaliacao_id": 10, "fonte": "seed"},
        {"avaliacao_id": 11, "fonte": "seed"},
        {"avaliacao_id": 12, "fonte": "seed"},
        {"avaliacao_id": 13, "fonte": "telemetria"},
    ])


@pytest.fixture
def rodar(monkeypatch, tmp_path, banco):
    caminho = tmp_path / "dataset.parquet"
    pd.DataFrame({"horas_operacao": [6.0, 2.5, 11.0], "historico_sinistros": [1, 0, 4]}).to_parquet(caminho)
    monkeypatch.setattr(pp, "DATA_PATH", str(caminho))
    monkeypatch.setattr(pp, "preprocess_features", lambda X, encoder: X)
    monkeypatch.setattr(pp, "compute_shap_values", lambda model, X: np.tile([2.0, -1.0], (len(X), 1)))
    monkeypatch.setattr(pp, "get_supabase_client", lambda: banco)
    monkeypatch.setattr(sys, "argv", ["populate_predictions.py"])

    def _rodar(scores, versao="xgboost-v1-baseline"):
        monkeypatch.setattr(pp, "load_artifacts", lambda: (ModeloFalso(scores), None, FEATURES))
        monkeypatch.setattr(pp, "MODELO_VERSAO", versao)
        pp.main()

    return _rodar


class TestReexecucao:
    def test_segunda_execucao_nao_duplica(self, rodar, banco):
        rodar([20.0, 50.0, 90.0])
        rodar([20.0, 50.0, 90.0])
        assert len(banco.predicoes) == 3
        assert sorted(p["avaliacao_id"] for p in banco.predicoes) == [10, 11, 12]

    def test_segunda_execucao_nao_reescreve_o_que_existe(self, rodar, banco):
        rodar([20.0, 50.0, 90.0])
        antes = [dict(p) for p in banco.predicoes]
        # Mesma versao, scores diferentes: o que ja esta gravado fica como esta.
        rodar([21.0, 51.0, 91.0])
        assert banco.predicoes == antes
        assert [p["risco_score_predito"] for p in banco.predicoes] == [20.0, 50.0, 90.0]

    def test_versao_nova_acrescenta_sem_tocar_na_anterior(self, rodar, banco):
        rodar([20.0, 50.0, 90.0])
        rodar([21.0, 51.0, 91.0], versao="xgboost-v2")
        assert len(banco.predicoes) == 6
        por_versao = {}
        for p in banco.predicoes:
            por_versao.setdefault(p["modelo_versao"], []).append(p["risco_score_predito"])
        assert por_versao == {"xgboost-v1-baseline": [20.0, 50.0, 90.0], "xgboost-v2": [21.0, 51.0, 91.0]}

    def test_sem_reset_nunca_apaga(self, rodar, banco):
        rodar([20.0, 50.0, 90.0])
        rodar([20.0, 50.0, 90.0])
        assert banco.apagou is False


class TestUpsert:
    def test_usa_on_conflict_do_par_e_ignora_duplicata(self, rodar, banco):
        rodar([20.0, 50.0, 90.0])
        rodar([20.0, 50.0, 90.0])
        assert banco.upserts
        assert all(
            u == {"on_conflict": "avaliacao_id,modelo_versao", "ignore_duplicates": True}
            for u in banco.upserts
        ), banco.upserts

    def test_on_conflict_bate_com_o_indice_unico_da_migration(self):
        assert _chave_unica_de_predicoes() == {"avaliacao_id", "modelo_versao"}
