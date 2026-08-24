"""
Contratos de entrada e saida da API (docs/spec-implementacao-entrega-03.md, secao 5).

O cliente envia apenas o que observa em campo. O que e cadastral (tipo, idade,
historico de sinistros, intervalos de manutencao) vem do banco, e o que e
derivado (atraso de manutencao, faixa de risco) e calculado pelo servidor —
nunca aceito do cliente.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoOperacao = Literal["colheita", "plantio", "pulverizacao", "transporte", "parado"]
TipoSolo = Literal["arenoso", "argiloso", "misto"]
CondicaoClima = Literal["ensolarado", "nublado", "chuvoso", "tempestade"]


class LeituraTelemetria(BaseModel):
    """Uma leitura de campo: telemetria + ambiente + operacao."""

    # Rejeita campo desconhecido em vez de descarta-lo em silencio. Sem isto, um
    # cliente que enviasse 'atraso_manutencao_pct' ou 'faixa_risco' — ambos
    # derivados no servidor — receberia 201 achando que definiu o valor.
    model_config = ConfigDict(extra="forbid")

    equipamento_id: str = Field(..., pattern=r"^EQ-\d{4}$")
    operador_id: str = Field(..., pattern=r"^OP-\d{4}$")

    # Geografico
    latitude: float = Field(..., ge=-33.75, le=-2.50)
    longitude: float = Field(..., ge=-73.99, le=-34.79)
    tipo_solo: TipoSolo
    distancia_agua_m: float = Field(..., ge=10.0, le=5000.0)
    declividade: float = Field(..., ge=0.0, le=45.0)

    # Operacional
    tipo_operacao: TipoOperacao
    velocidade_kmh: float = Field(..., ge=0.0, le=40.0)
    horas_operacao: float = Field(..., ge=0.0, le=24.0)
    horario_operacao: int = Field(..., ge=0, le=23)
    vibracao_g: float | None = Field(None, ge=0.1, le=4.0)
    temperatura_motor: float | None = Field(None, ge=50.0, le=120.0)

    # Operador
    pct_velocidade_acima_recomendada: float = Field(..., ge=0.0, le=100.0)
    freq_eventos_bruscos: float = Field(..., ge=0.0, le=20.0)
    pct_operacoes_noturnas: float = Field(..., ge=0.0, le=100.0)
    score_operador_historico: float = Field(..., ge=0.0, le=100.0)

    # Manutencao declarada (o atraso e derivado no servidor — Regra 14)
    ultima_manutencao_dias: int = Field(..., ge=0, le=365)
    ultima_manutencao_horas_op: float = Field(..., ge=0.0, le=2000.0)

    # Ambiental — opcional. Quando ausente, o servidor busca na Open-Meteo pela
    # coordenada. Quando presente, serve de fallback se a API externa falhar.
    temperatura_ar: float | None = Field(None, ge=-5.0, le=45.0)
    precipitacao_mm: float | None = Field(None, ge=0.0, le=120.0)
    umidade_solo: float | None = Field(None, ge=5.0, le=95.0)
    velocidade_vento: float | None = Field(None, ge=0.0, le=80.0)
    condicao_clima: CondicaoClima | None = None


class FatorSHAP(BaseModel):
    feature: str
    valor: float | None
    shap_value: float
    grupo: str


class RespostaScore(BaseModel):
    """O score nunca viaja sozinho: sempre com faixa e decomposicao (RF-10)."""

    avaliacao_id: int
    equipamento_id: str
    risco_score: float
    faixa_risco: Literal["baixo", "medio", "alto"]
    clima_origem: str
    contribuicoes_por_grupo: dict[str, float]
    top_fatores: list[FatorSHAP]
    modelo_versao: str
    timestamp: str


class TokenRequest(BaseModel):
    usuario: str
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    perfil: str
    expira_em_minutos: int
