"""
Aplicacao FastAPI — orquestra entrada, banco, modelo e saida (RF-01).

O modelo e carregado no startup, uma vez por processo: reconstruir o
TreeExplainer por requisicao percorreria as 300 arvores a cada chamada.
"""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core import config
from backend.core.exceptions import BancoIndisponivel, SafeFieldError
from backend.core.logging import configurar as configurar_logging, novo_request_id, request_id_atual

logger = logging.getLogger("safefield.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configurar_logging()
    # Nao derruba o processo se o modelo faltar: /health reporta 'degradado'
    # e POST /avaliacoes responde 503 tratado (scoring.carregar_modelo).
    from backend.services import scoring

    status = scoring.status_modelo()
    if status["carregado"]:
        logger.info("modelo carregado (%d features)", status["n_features"])
    yield


app = FastAPI(
    title="SafeField API",
    description="Score de risco para equipamentos agricolas — Challenge Sompo",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.API_CORS_ORIGINS,
    # A autenticacao vai no header Authorization, nao em cookie: nao ha
    # credencial de navegador para liberar.
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    # Sem isto o navegador esconde o X-Request-ID do front, e um erro sem
    # request_id no corpo (503, 4xx) chega a tela sem o codigo para suporte.
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def correlacionar(request: Request, call_next):
    """Um request_id por requisicao, presente em toda linha de log e nos erros."""
    rid = novo_request_id()
    try:
        resposta = await call_next(request)
    except Exception:
        # Excecao nao tratada passaria por fora deste middleware e o 500 sairia
        # sem X-Request-ID. Montado aqui, o header acompanha o corpo.
        resposta = _resposta_500(request)
    resposta.headers["X-Request-ID"] = rid
    return resposta


def _resposta_500(request: Request) -> JSONResponse:
    logger.exception("erro nao tratado em %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Erro interno. Consulte os logs do servidor.",
            "request_id": request_id_atual(),
        },
    )


@app.exception_handler(SafeFieldError)
async def tratar_erro_dominio(request: Request, exc: SafeFieldError):
    """Excecoes de dominio viram resposta legivel — nunca stack trace."""
    logger.warning("%s em %s: %s", type(exc).__name__, request.url.path, exc.mensagem)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.mensagem})


@app.exception_handler(httpx.TransportError)
async def tratar_banco_inacessivel(request: Request, exc: httpx.TransportError):
    """
    Conexao com o Supabase recusada, sem rota ou estourando o tempo. O cliente
    do Supabase usa httpx; a Open-Meteo usa requests e tem fallback proprio.
    """
    logger.error("banco inacessivel em %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": BancoIndisponivel.mensagem})


@app.exception_handler(Exception)
async def tratar_erro_inesperado(request: Request, exc: Exception):
    """
    Ultimo recurso. Registra com stack completo no log e devolve mensagem
    generica ao cliente — detalhe interno nunca sai na resposta.
    """
    return _resposta_500(request)


from backend.api.routers import auth, avaliacoes, consultas, health  # noqa: E402

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(avaliacoes.router)
app.include_router(consultas.router)
