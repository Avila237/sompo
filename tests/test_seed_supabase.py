"""
Seed seguro (BRA-446 item 3, R4-04).

scripts/seed_supabase.py so carrega um banco vazio e nunca apaga: com linhas em
qualquer uma das quatro tabelas, recusa e sai com codigo diferente de zero. O
cliente Supabase e trocado por um banco falso em memoria; nenhum teste abre rede.
"""

import inspect
import os
import re
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts import seed_supabase  # noqa: E402

TABELAS = ["equipamentos", "operadores", "avaliacoes", "predicoes"]
MIGRATIONS_DIR = os.path.join(PROJECT_ROOT, "supabase", "migrations")
PREREQUISITO = "aplique as migrations de supabase/migrations/ em ordem"


class BancoFalso:
    """Cliente Supabase em memoria: conta linhas, registra insercoes e delecoes."""

    def __init__(self, contagens=None):
        self.contagens = {t: 0 for t in TABELAS}
        self.contagens.update(contagens or {})
        self.insercoes = []
        self.apagou = []

    def table(self, nome):
        return _Consulta(self, nome)

    def registros(self, tabela):
        return [r for t, lote in self.insercoes if t == tabela for r in lote]


class _Consulta:
    def __init__(self, banco, tabela):
        self.banco = banco
        self.tabela = tabela
        self.contar = False

    def select(self, *colunas, count=None):
        self.contar = count == "exact"
        return self

    def limit(self, n):
        return self

    def insert(self, registros):
        registros = list(registros)
        self.banco.insercoes.append((self.tabela, registros))
        self.banco.contagens[self.tabela] += len(registros)
        return self

    # Registra em vez de falhar: o assert sobre `apagou` diz o que aconteceu.
    def delete(self):
        self.banco.apagou.append(self.tabela)
        return self

    def gte(self, *a):
        return self

    def neq(self, *a):
        return self

    def execute(self):
        if self.contar:
            return SimpleNamespace(count=self.banco.contagens[self.tabela], data=[])
        return SimpleNamespace(count=None, data=[])


def _dataset():
    """Tres avaliacoes de dois equipamentos e dois operadores, no formato do parquet."""
    return pd.DataFrame({
        "equipamento_id": ["EQ-0001", "EQ-0001", "EQ-0002"],
        "tipo_equipamento": ["trator", "trator", "colheitadeira"],
        "modelo_equipamento": ["John Deere 7J195", "John Deere 7J195", "John Deere S790"],
        "categoria_manual": ["trator_operacao", "trator_operacao", "colheitadeira_operacao"],
        "idade_equipamento": [5, 5, 12],
        "historico_sinistros": [1, 1, 4],
        "tem_iot": [True, True, False],
        "intervalo_manut_recomendado_dias": [180, 180, 120],
        "intervalo_manut_recomendado_horas": [500, 500, 300],
        "operador_id": ["OP-0001", "OP-0002", "OP-0001"],
        "timestamp": pd.to_datetime(["2025-01-10 08:00", "2025-03-05 14:30", "2025-07-21 22:15"]),
        "horas_operacao": [6.0, 2.5, 11.0],
        "vibracao_g": [1.4, float("nan"), 0.8],
        "risco_score": [42.123, 12.0, 80.456],
        "faixa_risco": pd.Categorical(["medio", "baixo", "alto"]),
    })


def _rodar(monkeypatch, banco, *args, resposta=None):
    monkeypatch.setattr(seed_supabase, "get_supabase_client", lambda: banco)
    monkeypatch.setattr(seed_supabase, "load_dataset", _dataset)
    monkeypatch.setattr(sys, "argv", ["seed_supabase.py", *args])
    if resposta is not None:
        monkeypatch.setattr("builtins.input", lambda _prompt: resposta)
    seed_supabase.main()


class TestRecusaComDados:
    @pytest.mark.parametrize("tabela", TABELAS)
    def test_qualquer_tabela_com_linhas_recusa(self, monkeypatch, capsys, tabela):
        banco = BancoFalso({tabela: 3})
        with pytest.raises(SystemExit) as saida:
            _rodar(monkeypatch, banco, "--force")
        assert saida.value.code not in (0, None)
        assert banco.insercoes == []
        assert banco.apagou == []
        erro = capsys.readouterr().err
        assert "RECUSADO" in erro
        assert f"{tabela}: 3 linhas" in erro

    def test_contagem_indisponivel_conta_como_ocupada(self, monkeypatch, capsys):
        # Sem prova de que a tabela esta vazia, o seed nao grava.
        banco = BancoFalso({"avaliacoes": None})
        with pytest.raises(SystemExit) as saida:
            _rodar(monkeypatch, banco, "--force")
        assert saida.value.code not in (0, None)
        assert banco.insercoes == []
        assert "avaliacoes: contagem indisponivel" in capsys.readouterr().err

    def test_confirmar_no_prompt_nao_passa_por_cima_da_recusa(self, monkeypatch):
        banco = BancoFalso({"predicoes": 5000})
        with pytest.raises(SystemExit) as saida:
            _rodar(monkeypatch, banco, resposta="s")
        assert saida.value.code not in (0, None)
        assert banco.insercoes == []
        assert banco.apagou == []


class TestBancoVazio:
    def test_carrega_as_tres_tabelas_em_ordem(self, monkeypatch):
        banco = BancoFalso()
        _rodar(monkeypatch, banco, "--force")
        # Ordem das FKs: avaliacoes referencia equipamentos e operadores.
        assert [t for t, _ in banco.insercoes] == ["equipamentos", "operadores", "avaliacoes"]
        assert len(banco.registros("equipamentos")) == 2
        assert len(banco.registros("operadores")) == 2
        assert len(banco.registros("avaliacoes")) == 3
        assert banco.apagou == []

    def test_avaliacoes_do_seed_levam_fonte_seed(self, monkeypatch):
        # populate_predictions.py so pareia avaliacoes com fonte='seed'.
        banco = BancoFalso()
        _rodar(monkeypatch, banco, "--force")
        assert {r["fonte"] for r in banco.registros("avaliacoes")} == {"seed"}

    def test_resposta_negativa_no_prompt_nao_grava(self, monkeypatch):
        banco = BancoFalso()
        with pytest.raises(SystemExit) as saida:
            _rodar(monkeypatch, banco, resposta="n")
        assert saida.value.code == 0
        assert banco.insercoes == []

    def test_imprime_o_prerequisito_das_migrations(self, monkeypatch, capsys):
        _rodar(monkeypatch, BancoFalso(), "--force")
        assert PREREQUISITO in capsys.readouterr().out


class TestNuncaApaga:
    def test_modulo_nao_tem_caminho_de_delete(self):
        fonte = inspect.getsource(seed_supabase)
        assert ".delete(" not in fonte
        assert not hasattr(seed_supabase, "clear_tables")

    def test_docstring_manda_aplicar_as_migrations_e_nao_o_schema_antigo(self):
        assert PREREQUISITO in seed_supabase.__doc__
        assert "schema.sql" not in inspect.getsource(seed_supabase)


class TestMigrationBase:
    """O pre-requisito do seed: a estrutura vem so de supabase/migrations/."""

    @staticmethod
    def _sql_da_base():
        bases = [f for f in os.listdir(MIGRATIONS_DIR) if f.endswith("_base.sql")]
        assert len(bases) == 1, bases
        with open(os.path.join(MIGRATIONS_DIR, bases[0]), encoding="utf-8") as f:
            return bases[0], re.sub(r"--[^\n]*", "", f.read())

    def test_schema_destrutivo_nao_existe_mais(self):
        assert not os.path.exists(os.path.join(PROJECT_ROOT, "backend", "db", "schema.sql"))

    def test_base_e_a_primeira_na_ordem(self):
        nome, _ = self._sql_da_base()
        migrations = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))
        assert migrations[0] == nome

    def test_base_nao_apaga_nada(self):
        _, sql = self._sql_da_base()
        assert not re.search(r"\b(DROP|DELETE|TRUNCATE)\b", sql, re.IGNORECASE)

    def test_todo_create_da_base_e_idempotente(self):
        _, sql = self._sql_da_base()
        create = r"\bCREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX)\b"
        # As 4 tabelas e os 6 indices que backend/db/schema.sql criava.
        assert len(re.findall(create, sql)) == 10
        assert re.findall(create + r"(?!\s+IF\s+NOT\s+EXISTS\b)", sql) == []

    @pytest.mark.parametrize("tabela", TABELAS)
    def test_base_cria_as_tabelas_que_o_seed_confere(self, tabela):
        _, sql = self._sql_da_base()
        assert re.search(rf"CREATE TABLE IF NOT EXISTS {tabela} \(", sql)
