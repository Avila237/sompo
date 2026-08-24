"""
Acesso a dados. Unica camada que fala com o Supabase.

Usa a service_role: com RLS habilitada e sem policy para 'anon', este e o unico
caminho de leitura e escrita. Nenhum cliente toca o banco diretamente.
"""

from functools import lru_cache

from supabase import Client, create_client

from backend.core import config

PAGINA = 1000


@lru_cache(maxsize=1)
def get_client() -> Client:
    """Cliente unico por processo."""
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)


def buscar_equipamento(equipamento_id: str) -> dict | None:
    """Dados cadastrais do equipamento. None se nao existir."""
    r = (
        get_client().table("equipamentos")
        .select("*")
        .eq("equipamento_id", equipamento_id)
        .limit(1)
        .execute()
    )
    return r.data[0] if r.data else None


def operador_existe(operador_id: str) -> bool:
    r = (
        get_client().table("operadores")
        .select("operador_id")
        .eq("operador_id", operador_id)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def inserir_avaliacao(registro: dict) -> int:
    """Grava a leitura recebida e devolve o avaliacao_id gerado."""
    r = get_client().table("avaliacoes").insert(registro).execute()
    if not r.data:
        raise RuntimeError("Insercao em 'avaliacoes' nao retornou o registro criado.")
    return int(r.data[0]["avaliacao_id"])


def inserir_predicao(registro: dict) -> int:
    """Grava a predicao. Append-only: nunca sobrescreve historico (RF-04)."""
    r = get_client().table("predicoes").insert(registro).execute()
    if not r.data:
        raise RuntimeError("Insercao em 'predicoes' nao retornou o registro criado.")
    return int(r.data[0]["predicao_id"])


def remover_avaliacao(avaliacao_id: int) -> None:
    """
    Compensacao: se a predicao falhar depois da avaliacao gravada, o registro
    nao pode ficar em limbo (RF-03). Chamado apenas no caminho de erro.
    """
    get_client().table("avaliacoes").delete().eq("avaliacao_id", avaliacao_id).execute()


def contar(tabela: str) -> int:
    r = get_client().table(tabela).select("*", count="exact").limit(0).execute()
    return int(r.count or 0)


# --- Leitura agregada -----------------------------------------------------
#
# O PostgREST nao faz GROUP BY, entao a agregacao acontece em memoria. O
# conjunto e pequeno e estavel (5 mil linhas), e o cache e invalidado a cada
# escrita — ver invalidar_cache().

_cache: dict[str, list[dict]] = {}


def invalidar_cache() -> None:
    """Chamado apos toda escrita, para a leitura nao servir dado velho."""
    _cache.clear()


def _paginado(tabela: str, colunas: str, ordem: str) -> list[dict]:
    linhas: list[dict] = []
    inicio = 0
    while True:
        r = (
            get_client().table(tabela)
            .select(colunas)
            .order(ordem)
            .range(inicio, inicio + PAGINA - 1)
            .execute()
        )
        lote = r.data or []
        linhas.extend(lote)
        if len(lote) < PAGINA:
            break
        inicio += PAGINA
    return linhas


def listar_equipamentos() -> list[dict]:
    if "equipamentos" not in _cache:
        _cache["equipamentos"] = _paginado("equipamentos", "*", "equipamento_id")
    return _cache["equipamentos"]


def listar_avaliacoes_resumo() -> list[dict]:
    if "avaliacoes" not in _cache:
        colunas = (
            "avaliacao_id,equipamento_id,operador_id,risco_score,faixa_risco,"
            "timestamp,latitude,longitude,tipo_operacao"
        )
        _cache["avaliacoes"] = _paginado("avaliacoes", colunas, "avaliacao_id")
    return _cache["avaliacoes"]


def ultima_avaliacao(equipamento_id: str) -> dict | None:
    r = (
        get_client().table("avaliacoes")
        .select("*")
        .eq("equipamento_id", equipamento_id)
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )
    return r.data[0] if r.data else None


def predicao_de(avaliacao_id: int) -> dict | None:
    r = (
        get_client().table("predicoes")
        .select("avaliacao_id,risco_score_predito,faixa_predita,top_fatores_shap,modelo_versao")
        .eq("avaliacao_id", avaliacao_id)
        .limit(1)
        .execute()
    )
    return r.data[0] if r.data else None
