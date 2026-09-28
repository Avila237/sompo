"""
Coleta climatica fiel (S4-20).

- Precipitacao e a soma das ultimas 24 horas, nao o total do dia anterior.
- Clima medido em campo (payload completo) prevalece; a Open-Meteo so preenche
  o que falta, e os campos derivados (umidade, condicao) seguem a chuva final.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.core.exceptions import ClimaIndisponivel  # noqa: E402
from backend.services import clima  # noqa: E402
from backend.services.scoring import resolver_clima  # noqa: E402


def _resposta_open_meteo(chuva_por_hora, temperatura=24.0, vento=10.0):
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = {
        "current": {"temperature_2m": temperatura, "wind_speed_10m": vento},
        "hourly": {
            "time": [f"h{i}" for i in range(len(chuva_por_hora))],
            "precipitation": chuva_por_hora,
        },
    }
    return r


class TestBuscar:
    def test_soma_a_chuva_das_ultimas_24_horas(self):
        horas = [0.0] * 20 + [1.5, 2.0, None, 0.5]
        with patch.object(clima.requests, "get", return_value=_resposta_open_meteo(horas)) as get:
            dados = clima.buscar(-12.5, -55.7, "argiloso")
        assert dados["precipitacao_mm"] == 4.0
        params = get.call_args.kwargs["params"]
        assert params["hourly"] == "precipitation"
        assert params["past_hours"] == 24 and params["forecast_hours"] == 0
        assert "daily" not in params

    def test_derivados_seguem_a_chuva_somada(self):
        with patch.object(clima.requests, "get", return_value=_resposta_open_meteo([2.0] * 24)):
            dados = clima.buscar(-12.5, -55.7, "argiloso")
        assert dados["precipitacao_mm"] == 48.0
        assert dados["condicao_clima"] == clima.derivar_condicao_clima(48.0)
        assert dados["umidade_solo"] == clima.derivar_umidade_solo(48.0, "argiloso")

    def test_sem_serie_horaria_e_resposta_malformada(self):
        r = _resposta_open_meteo([])
        del r.json.return_value["hourly"]
        with patch.object(clima.requests, "get", return_value=r):
            assert clima.buscar(-12.5, -55.7, "argiloso") is None


LEITURA = {
    "equipamento_id": "EQ-0001",
    "latitude": -12.5,
    "longitude": -55.7,
    "tipo_solo": "argiloso",
}
CLIMA_CAMPO = {
    "temperatura_ar": 30.0,
    "precipitacao_mm": 10.0,
    "umidade_solo": 30.0,
    "velocidade_vento": 5.0,
    "condicao_clima": "nublado",
}
# Como o clima.buscar() real devolve: umidade e condicao derivadas da chuva.
CLIMA_API = {
    "temperatura_ar": 22.0,
    "precipitacao_mm": 60.0,
    "umidade_solo": clima.derivar_umidade_solo(60.0, "argiloso"),
    "velocidade_vento": 20.0,
    "condicao_clima": clima.derivar_condicao_clima(60.0),
}


class TestPrecedencia:
    def test_payload_completo_prevalece_e_nem_consulta_a_api(self):
        with patch.object(clima, "buscar") as buscar:
            leitura, origem = resolver_clima({**LEITURA, **CLIMA_CAMPO})
        buscar.assert_not_called()
        assert origem == "payload"
        assert {c: leitura[c] for c in CLIMA_CAMPO} == CLIMA_CAMPO

    def test_sem_clima_no_payload_usa_a_api(self):
        with patch.object(clima, "buscar", return_value=CLIMA_API):
            leitura, origem = resolver_clima(dict(LEITURA))
        assert origem == "open-meteo"
        assert {c: leitura[c] for c in CLIMA_API} == CLIMA_API

    def test_payload_parcial_e_completado_pela_api(self):
        """A chuva medida vale; umidade e condicao seguem a chuva final, nao a da API."""
        with patch.object(clima, "buscar", return_value=CLIMA_API):
            leitura, origem = resolver_clima({**LEITURA, "precipitacao_mm": 10.0})
        assert origem == "misto"
        assert leitura["precipitacao_mm"] == 10.0
        assert leitura["temperatura_ar"] == CLIMA_API["temperatura_ar"]
        assert leitura["velocidade_vento"] == CLIMA_API["velocidade_vento"]
        assert leitura["condicao_clima"] == clima.derivar_condicao_clima(10.0)
        assert leitura["umidade_solo"] == clima.derivar_umidade_solo(10.0, "argiloso")

    def test_payload_parcial_mantem_o_que_foi_medido(self):
        with patch.object(clima, "buscar", return_value=CLIMA_API):
            leitura, _ = resolver_clima({**LEITURA, "temperatura_ar": 31.0})
        assert leitura["temperatura_ar"] == 31.0
        assert leitura["precipitacao_mm"] == CLIMA_API["precipitacao_mm"]

    def test_payload_parcial_e_api_fora_recusa(self):
        with patch.object(clima, "buscar", return_value=None), \
             pytest.raises(ClimaIndisponivel):
            resolver_clima({**LEITURA, "precipitacao_mm": 10.0})
