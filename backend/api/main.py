"""
Aplicacao FastAPI — orquestra entrada, banco, modelo e saida (RF-01).

O modelo e carregado no startup, uma vez por processo: reconstruir o
TreeExplainer por requisicao percorreria as 300 arvores a cada chamada.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core import config
from backend.core.exceptions import SafeFieldError
from backend.core.logging import configurar as configurar_logging, novo_request_id, request_id_atual
from backend.ml.predictor import get_predictor

logger = logging.getLogger("safefield.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configurar_logging()
    try:
        p = get_predictor(config.MODELS_DIR)
        logger.info("modelo carregado (%d features)", len(p.features))
    except Exception as e:
        # Nao derruba o processo: /health reporta 'degradado' e as rotas de
        # scoring falham com 503 tratado, em vez de erro opaco no startup.
        logger.error("modelo indisponivel no startup: %s", e)
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
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def correlacionar(request: Request, call_next):
    """Um request_id por requisicao, presente em toda linha de log e nos erros."""
    rid = novo_request_id()
    resposta = await call_next(request)
    resposta.headers["X-Request-ID"] = rid
    return resposta


@app.exception_handler(SafeFieldError)
async def tratar_erro_dominio(request: Request, exc: SafeFieldError):
    """Excecoes de dominio viram resposta legivel — nunca stack trace."""
    logger.warning("%s em %s: %s", type(exc).__name__, request.url.path, exc.mensagem)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.mensagem})


@app.exception_handler(Exception)
async def tratar_erro_inesperado(request: Request, exc: Exception):
    """
    Ultimo recurso. Registra com stack completo no log e devolve mensagem
    generica ao cliente — detalhe interno nunca sai na resposta.
    """
    logger.exception("erro nao tratado em %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Erro interno. Consulte os logs do servidor.",
            "request_id": request_id_atual(),
        },
    )


from backend.api.routers import auth, avaliacoes, consultas, health  # noqa: E402

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(avaliacoes.router)
app.include_router(consultas.router)
