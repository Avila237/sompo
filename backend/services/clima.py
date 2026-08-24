"""
Enriquecimento climatico via Open-Meteo (RF-05).

A Open-Meteo e a fonte preferencial. Se falhar ou estourar o timeout, o fluxo
cai para os valores climaticos do proprio payload e registra a procedencia na
coluna clima_origem — nunca falha em silencio, e a auditoria consegue
distinguir clima real de clima simulado.

umidade_solo e condicao_clima nao vem da API: sao derivadas pelas Regras 3 e 5
de docs/data schema.md, as mesmas usadas na geracao do dataset. Usar outra
convencao aqui daria ao modelo uma feature com distribuicao diferente da que
ele viu no treino.
"""

import logging

import requests

from backend.core import config

logger = logging.getLogger("safefield.clima")

FATOR_SOLO = {"argiloso": 1.3, "misto": 1.0, "arenoso": 0.7}


def derivar_umidade_solo(precipitacao_mm: float, tipo_solo: str) -> float:
    """Regra 3: argiloso retem mais agua que arenoso para a mesma chuva."""
    base = precipitacao_mm * 0.5 + 10.0
    return round(min(95.0, max(5.0, base * FATOR_SOLO.get(tipo_solo, 1.0))), 1)


def derivar_condicao_clima(precipitacao_mm: float) -> str:
    """Regra 5: a condicao acompanha a precipitacao acumulada."""
    if precipitacao_mm <= 2:
        return "ensolarado"
    if precipitacao_mm <= 20:
        return "nublado"
    if precipitacao_mm <= 50:
        return "chuvoso"
    return "tempestade"


def buscar(latitude: float, longitude: float, tipo_solo: str) -> dict | None:
    """
    Devolve o bloco climatico da coordenada, ou None se a API nao responder.

    None nao e erro engolido: quem chama registra o incidente e cai para o
    payload, marcando clima_origem='payload'.
    """
    url = f"{config.OPENMETEO_BASE_URL}/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,wind_speed_10m",
        "daily": "precipitation_sum",
        "past_days": 1,
        "forecast_days": 1,
        "timezone": "UTC",
    }
    try:
        r = requests.get(url, params=params, timeout=config.OPENMETEO_TIMEOUT_S)
        r.raise_for_status()
        dados = r.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning(
            "Open-Meteo indisponivel para (%.4f, %.4f): %s — usando o payload",
            latitude, longitude, e,
        )
        return None

    try:
        atual = dados["current"]
        chuva_24h = float(dados["daily"]["precipitation_sum"][0] or 0.0)
        temperatura = float(atual["temperature_2m"])
        vento = float(atual["wind_speed_10m"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        logger.warning("resposta da Open-Meteo em formato inesperado: %s", e)
        return None

    # Clampa nos dominios que o modelo viu no treino.
    temperatura = max(-5.0, min(45.0, temperatura))
    chuva_24h = max(0.0, min(120.0, chuva_24h))
    vento = max(0.0, min(80.0, vento))

    return {
        "temperatura_ar": round(temperatura, 1),
        "precipitacao_mm": round(chuva_24h, 1),
        "velocidade_vento": round(vento, 1),
        "umidade_solo": derivar_umidade_solo(chuva_24h, tipo_solo),
        "condicao_clima": derivar_condicao_clima(chuva_24h),
    }
