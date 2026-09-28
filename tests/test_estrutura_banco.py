"""
Indices de avaliacoes conferidos no SQL versionado, sem rede.

O TestIndexes antigo (test_supabase.py) consultava o banco e so checava que a
resposta era uma lista: passava com ou sem indice. Aqui a checagem e estatica:
os indices de avaliacoes em equipamento_id, operador_id, timestamp e
faixa_risco tem de estar declarados no SQL que monta o banco. Hoje
ultima_avaliacao() (backend/db/repository.py) filtra por equipamento_id e
ordena por timestamp; os recortes por operador e por faixa ainda rodam em
memoria, e os dois indices ficam para quando descerem ao banco.

Fontes, na ordem em que se aplicam: backend/db/schema.sql, enquanto existir,
e depois supabase/migrations/*.sql por nome. O teste vale com ou sem o
schema.sql, para sobreviver a troca dele por uma migration de base. Nao prova
que o banco remoto tem os indices: isso so uma consulta a pg_indexes diria.
"""
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COLUNAS_INDEXADAS = ("equipamento_id", "operador_id", "timestamp", "faixa_risco")

_COMENTARIO = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
# Cobre o formato escrito a mao e o do pg_dump/supabase db dump
# (public.avaliacoes, USING "btree", identificadores entre aspas).
_CREATE_INDEX = re.compile(
    r"""CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?
        (?P<nome>[\w."]+\s+)?
        ON\s+(?:ONLY\s+)?(?P<tabela>[\w."]+)\s*
        (?:USING\s+"?\w+"?\s*)?
        \((?P<colunas>[^)]*)\)""",
    re.IGNORECASE | re.VERBOSE,
)
_DROP_INDEX = re.compile(
    r"DROP\s+INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+EXISTS\s+)?(?P<nomes>[^;]+)",
    re.IGNORECASE,
)


def _ident(bruto: str) -> str:
    """'"public"."Avaliacoes"' -> 'avaliacoes': sem aspas, sem schema."""
    return bruto.strip().replace('"', "").split(".")[-1].lower()


def fontes_sql(raiz: Path = PROJECT_ROOT) -> list[Path]:
    """schema.sql legado (se existir) antes das migrations, na ordem de aplicacao."""
    legado = raiz / "backend" / "db" / "schema.sql"
    migrations = sorted((raiz / "supabase" / "migrations").glob("*.sql"), key=lambda p: p.name)
    return ([legado] if legado.is_file() else []) + migrations


def indices_declarados(textos: list[str]) -> set[tuple[str, str]]:
    """
    Pares (tabela, coluna lider) dos indices que sobram depois de aplicar, em
    ordem, cada CREATE INDEX e DROP INDEX. So a coluna lider conta: e a unica
    que um indice composto serve sozinha.
    """
    vivos: dict[str, tuple[str, str]] = {}
    for n_texto, texto in enumerate(textos):
        sql = _COMENTARIO.sub(" ", texto)
        eventos = [(m.start(), "create", m) for m in _CREATE_INDEX.finditer(sql)]
        eventos += [(m.start(), "drop", m) for m in _DROP_INDEX.finditer(sql)]
        for pos, tipo, m in sorted(eventos, key=lambda e: e[0]):
            if tipo == "drop":
                for nome in m["nomes"].split(","):
                    nome = re.sub(r"\s+(CASCADE|RESTRICT)\s*$", "", nome, flags=re.I)
                    vivos.pop(_ident(nome), None)
                continue
            lider = m["colunas"].split(",")[0].split()[0]
            # Indice sem nome nao pode ser dropado por nome: chave pela posicao.
            nome = _ident(m["nome"]) if m["nome"] else f"#{n_texto}:{pos}"
            vivos[nome] = (_ident(m["tabela"]), _ident(lider))
    return set(vivos.values())


# ---------------------------------------------------------------------------
# O SQL versionado do repositorio
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def indices_do_repo():
    fontes = fontes_sql()
    # Sem nenhum arquivo, o conjunto sai vazio e o erro apontaria o indice,
    # nao a causa: falha antes, dizendo onde procurou.
    assert fontes, "Nenhum SQL em backend/db/schema.sql nem em supabase/migrations/"
    return indices_declarados([p.read_text(encoding="utf-8-sig") for p in fontes])


@pytest.mark.parametrize("coluna", COLUNAS_INDEXADAS)
def test_indice_de_avaliacoes_declarado(indices_do_repo, coluna):
    assert ("avaliacoes", coluna) in indices_do_repo, (
        f"Nenhum indice de avaliacoes com '{coluna}' como coluna lider no SQL versionado"
    )


# ---------------------------------------------------------------------------
# O leitor de SQL: sem estes, um regex frouxo passaria em qualquer arquivo
# ---------------------------------------------------------------------------


def test_so_migrations_formato_dump_sem_schema_legado(tmp_path):
    # O estado depois da troca: schema.sql removido, base numa migration no
    # formato que o supabase db dump gera.
    migrations = tmp_path / "supabase" / "migrations"
    migrations.mkdir(parents=True)
    (migrations / "20260801000000_base.sql").write_text(
        'CREATE INDEX "idx_eq" ON "public"."avaliacoes" USING "btree" ("equipamento_id");\n'
        "CREATE INDEX idx_op ON public.avaliacoes USING btree (operador_id);\n"
        'CREATE INDEX IF NOT EXISTS idx_ts ON avaliacoes ("timestamp" DESC);\n'
        "create index on avaliacoes(faixa_risco, timestamp);\n",
        encoding="utf-8",
    )
    fontes = fontes_sql(tmp_path)
    assert [p.name for p in fontes] == ["20260801000000_base.sql"]
    indices = indices_declarados([p.read_text(encoding="utf-8") for p in fontes])
    assert {("avaliacoes", c) for c in COLUNAS_INDEXADAS} <= indices


def test_schema_legado_vem_antes_das_migrations(tmp_path):
    (tmp_path / "backend" / "db").mkdir(parents=True)
    (tmp_path / "backend" / "db" / "schema.sql").write_text("", encoding="utf-8")
    migrations = tmp_path / "supabase" / "migrations"
    migrations.mkdir(parents=True)
    for nome in ("20260928120000_b.sql", "20260824120000_a.sql"):
        (migrations / nome).write_text("", encoding="utf-8")
    assert [p.name for p in fontes_sql(tmp_path)] == [
        "schema.sql", "20260824120000_a.sql", "20260928120000_b.sql",
    ]


def test_ignora_comentado_outra_tabela_coluna_nao_lider_e_dropado():
    base = (
        "-- CREATE INDEX idx_a ON avaliacoes(timestamp);\n"
        "/* CREATE INDEX idx_b ON avaliacoes(operador_id); */\n"
        "CREATE INDEX idx_c ON predicoes(faixa_risco);\n"
        "CREATE INDEX idx_d ON avaliacoes(equipamento_id, timestamp);\n"
        "CREATE INDEX idx_e ON avaliacoes(faixa_risco);\n"
    )
    # Dropado numa migration posterior, com schema no nome: nao conta mais.
    posterior = "DROP INDEX IF EXISTS public.idx_e CASCADE;\n"
    assert indices_declarados([base, posterior]) == {
        ("predicoes", "faixa_risco"),
        ("avaliacoes", "equipamento_id"),
    }
