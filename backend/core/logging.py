"""
Log estruturado para stdout (RF-08).

Cada linha carrega um request_id que correlaciona a entrada, a decisao do
modelo e um eventual erro. Nenhum dado sensivel de segurado vai para o log.
"""

import logging
import sys
import uuid
from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def novo_request_id() -> str:
    rid = uuid.uuid4().hex[:12]
    _request_id.set(rid)
    return rid


def request_id_atual() -> str:
    return _request_id.get()


class _FiltroRequestId(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_atual()
        return True


def configurar(nivel: str = "INFO") -> None:
    """Idempotente: chamada no startup da API."""
    raiz = logging.getLogger("safefield")
    if raiz.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.addFilter(_FiltroRequestId())
    raiz.addHandler(handler)
    raiz.setLevel(nivel)
    raiz.propagate = False
