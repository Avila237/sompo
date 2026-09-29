"""
Acesso a dados. Unica camada que fala com o Supabase.

Usa a service_role: com RLS habilitada e sem policy para 'anon', este e o unico
caminho de leitura e escrita. Nenhum cliente toca o banco diretamente.
"""

from functools import lru_cache

from postgrest.exceptions import APIError
from supabase import Client, create_client

from backend.core import config
from backend.core.exceptions import LeituraReutilizada

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


# Grupo 0 do PostgREST: ele esta de pe, mas sem conexao com o Postgres
# (PGRST000-002 respondem 503; PGRST003, fila do pool esgotada, 504).
_POSTGREST_SEM_BANCO = frozenset({"PGRST000", "PGRST001", "PGRST002", "PGRST003"})
# SQLSTATE: classe 08 (conexao) e 57P01-03 (Postgres desligando ou subindo).
_SQLSTATE_SEM_BANCO = ("08", "57P01", "57P02", "57P03")


def banco_indisponivel(erro: APIError) -> bool:
    """
    True quando o APIError e falta de banco, nao erro de dado.

    O postgrest-py (2.31) poe em `code` o codigo do PostgREST ou o SQLSTATE,
    como texto, quando o corpo e o JSON de erro do PostgREST; o status HTTP
    dessa resposta nao chega ao APIError. Quando o corpo e outro (o gateway na
    frente do PostgREST devolvendo HTML ou JSON sem `code`), `code` e o
    status HTTP, como int. Erro de dado (23505, PT409, constraint, 4xx) fica
    de fora: repetir nao resolve.
    """
    codigo = erro.code
    if isinstance(codigo, int):
        return 500 <= codigo <= 599
    if not isinstance(codigo, str):
        return False
    return codigo in _POSTGREST_SEM_BANCO or codigo.startswith(_SQLSTATE_SEM_BANCO)


def _chamar_registrar(avaliacao: dict, predicao: dict) -> tuple[int, bool]:
    try:
        r = get_client().rpc(
            "registrar_avaliacao", {"p_avaliacao": avaliacao, "p_predicao": predicao}
        ).execute()
    except APIError as e:
        if e.code == "PT409":
            raise LeituraReutilizada(avaliacao.get("leitura_id")) from e
        raise
    if not r.data:
        raise RuntimeError("registrar_avaliacao nao devolveu o registro criado.")
    return int(r.data[0]["avaliacao_id"]), bool(r.data[0]["reenvio"])


def registrar_avaliacao(avaliacao: dict, predicao: dict) -> tuple[int, bool]:
    """
    Grava avaliacao e predicao numa transacao so, pela funcao SQL de mesmo
    nome (supabase/migrations/20260928120000_sprint04_integridade.sql).
    Devolve (avaliacao_id, reenvio); reenvio=True quando o leitura_id ja
    existia com o mesmo payload e nada foi gravado.
    """
    try:
        return _chamar_registrar(avaliacao, predicao)
    except APIError as e:
        # Dois envios simultaneos da mesma leitura: o segundo bate no UNIQUE
        # de leitura_id. Na nova chamada a linha ja existe e vira reenvio.
        if e.code == "23505" and avaliacao.get("leitura_id"):
            return _chamar_registrar(avaliacao, predicao)
        raise


def buscar_por_leitura(leitura_id: str) -> dict | None:
    r = (
        get_client().table("avaliacoes")
        .select("avaliacao_id,payload_hash")
        .eq("leitura_id", leitura_id)
        .execute()
    )
    return r.data[0] if r.data else None


def buscar_avaliacao(avaliacao_id: int) -> dict | None:
    r = get_client().table("avaliacoes").select("*").eq("avaliacao_id", avaliacao_id).execute()
    return r.data[0] if r.data else None


def buscar_usuario(usuario: str) -> dict | None:
    r = (
        get_client().table("usuarios")
        .select("usuario,senha_hash,perfil,operador_id,ativo")
        .eq("usuario", usuario)
        .execute()
    )
    return r.data[0] if r.data else None


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
            "timestamp,latitude,longitude,tipo_operacao,"
            # estado de manutencao da leitura: a lista da frota ordena por ele (S4-36)
            "manutencao_atrasada,atraso_manutencao_pct,ultima_manutencao_dias"
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


def inserir_auditoria(registro: dict) -> None:
    get_client().table("auditoria").insert(registro).execute()


def predicao_de(avaliacao_id: int) -> dict | None:
    r = (
        get_client().table("predicoes")
        .select(
            "avaliacao_id,risco_score_predito,faixa_predita,top_fatores_shap,"
            "modelo_versao,contribuicoes_por_grupo"
        )
        .eq("avaliacao_id", avaliacao_id)
        # Com mais de uma versao de modelo, a predicao mais recente.
        .order("timestamp_predicao", desc=True)
        .limit(1)
        .execute()
    )
    return r.data[0] if r.data else None
