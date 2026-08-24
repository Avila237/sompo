"""
Simulador de telemetria — alimenta a API com leituras de campo (RF-05).

Representa a origem dos dados que, em producao, viria do app movel e do
ESP32 via BLE. Cobre as tres fontes que o enunciado exige: telemetria
(vibracao, temperatura de motor, velocidade), operacao (tipo, horario,
manutencao declarada) e ambiente (deixado a cargo da Open-Meteo).

Uso:
    python scripts/simulate_telemetry.py --n 10
    python scripts/simulate_telemetry.py --n 5 --intervalo 2 --cenario critico
    python scripts/simulate_telemetry.py --n 3 --sem-clima-externo
"""

import argparse
import os
import random
import sys
import time

import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.core import config  # noqa: E402
from backend.db import repository as repo  # noqa: E402

# Regioes agricolas reais, para as coordenadas caírem em terra e a Open-Meteo
# devolver clima plausivel.
REGIOES = [
    ("Sorriso/MT", -12.5453, -55.7114),
    ("Rio Verde/GO", -17.7975, -50.9264),
    ("Maracaju/MS", -21.6140, -55.1686),
    ("Cascavel/PR", -24.9555, -53.4552),
    ("Barreiras/BA", -12.1530, -44.9900),
    ("Passo Fundo/RS", -28.2620, -52.4069),
]

VELOCIDADE = {
    "parado": (0.0, 0.0),
    "colheita": (3.0, 8.0),
    "plantio": (3.0, 8.0),
    "pulverizacao": (8.0, 15.0),
    "transporte": (15.0, 40.0),
}

VIBRACAO = {
    "parado": (0.1, 0.3),
    "colheita": (0.8, 2.5),
    "plantio": (0.5, 1.5),
    "pulverizacao": (0.3, 1.0),
    "transporte": (0.4, 2.0),
}


def gerar_leitura(equipamentos: list[dict], cenario: str) -> tuple[dict, str]:
    eq = random.choice(equipamentos)
    regiao, lat, lon = random.choice(REGIOES)

    if cenario == "critico":
        operacao = random.choice(["transporte", "colheita"])
        horario = random.choice([21, 22, 23, 2, 3])
        dist_agua = round(random.uniform(10, 180), 1)
        declividade = round(random.uniform(12, 30), 1)
        manut_dias = random.randint(280, 365)
        pct_acima = round(random.uniform(40, 90), 1)
    else:
        operacao = random.choice(list(VELOCIDADE))
        horario = random.randint(6, 18)
        dist_agua = round(random.uniform(200, 4000), 1)
        declividade = round(random.uniform(0, 12), 1)
        manut_dias = random.randint(0, 200)
        pct_acima = round(random.uniform(0, 40), 1)

    v_min, v_max = VELOCIDADE[operacao]
    vib_min, vib_max = VIBRACAO[operacao]

    leitura = {
        "equipamento_id": eq["equipamento_id"],
        "operador_id": random.choice(operadores_de(eq)),
        "latitude": round(lat + random.uniform(-0.3, 0.3), 6),
        "longitude": round(lon + random.uniform(-0.3, 0.3), 6),
        "tipo_solo": random.choice(["argiloso", "misto", "arenoso"]),
        "distancia_agua_m": dist_agua,
        "declividade": declividade,
        "tipo_operacao": operacao,
        "velocidade_kmh": round(random.uniform(v_min, v_max), 1),
        "horas_operacao": round(random.uniform(0.5, 14.0), 1),
        "horario_operacao": horario,
        "vibracao_g": round(random.uniform(vib_min, vib_max), 2),
        # Regra 1: so equipamento com IoT tem sensor de temperatura de motor,
        # e implemento nao tem motor proprio.
        "temperatura_motor": (
            round(random.uniform(60, 115), 1)
            if eq["tem_iot"] and eq["tipo_equipamento"] != "implemento"
            else None
        ),
        "pct_velocidade_acima_recomendada": pct_acima,
        "freq_eventos_bruscos": round(random.uniform(0, 12), 2),
        "pct_operacoes_noturnas": round(random.uniform(0, 80), 1),
        "score_operador_historico": round(random.uniform(10, 90), 1),
        "ultima_manutencao_dias": manut_dias,
        "ultima_manutencao_horas_op": round(random.uniform(50, 1400), 1),
    }
    return leitura, regiao


_OPERADORES: list[str] = []


def operadores_de(equipamento: dict) -> list[str]:
    """Qualquer operador cadastrado — o vinculo real vive no historico."""
    return _OPERADORES


def obter_token(api: str, usuario: str, senha: str) -> str:
    r = requests.post(
        f"{api}/auth/token", json={"usuario": usuario, "senha": senha}, timeout=10
    )
    if r.status_code != 200:
        raise SystemExit(f"Falha na autenticacao ({r.status_code}): {r.text}")
    return r.json()["access_token"]


def main() -> None:
    p = argparse.ArgumentParser(description="Simulador de telemetria SafeField")
    p.add_argument("--n", type=int, default=5, help="quantidade de leituras")
    p.add_argument("--intervalo", type=float, default=1.0, help="segundos entre envios")
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--usuario", default="operador")
    p.add_argument("--senha", default=None, help="por padrao, le do .env")
    p.add_argument(
        "--cenario", choices=["normal", "critico"], default="normal",
        help="'critico' gera operacao noturna, perto de agua e manutencao atrasada",
    )
    p.add_argument(
        "--sem-clima-externo", action="store_true",
        help="envia o clima no payload em vez de deixar a API buscar na Open-Meteo",
    )
    p.add_argument("--seed", type=int, default=None)
    args = p.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    senha = args.senha or config.DEMO_USERS.get(args.usuario, {}).get("senha")
    if not senha:
        raise SystemExit(f"Usuario '{args.usuario}' nao esta em DEMO_USERS.")

    print("=" * 62)
    print("SafeField — Simulador de Telemetria")
    print("=" * 62)
    print(f"  API      : {args.api}")
    print(f"  Usuario  : {args.usuario}")
    print(f"  Cenario  : {args.cenario}")
    print(f"  Clima    : {'payload' if args.sem_clima_externo else 'Open-Meteo'}")
    print()

    token = obter_token(args.api, args.usuario, senha)
    cabecalho = {"Authorization": f"Bearer {token}"}

    equipamentos = repo.listar_equipamentos()
    _OPERADORES.extend(o["operador_id"] for o in repo.get_client()
                       .table("operadores").select("operador_id").execute().data)
    if not equipamentos or not _OPERADORES:
        raise SystemExit("Banco sem equipamentos ou operadores. Rode o seed antes.")

    enviadas, falhas = 0, 0
    for i in range(1, args.n + 1):
        leitura, regiao = gerar_leitura(equipamentos, args.cenario)
        if args.sem_clima_externo:
            chuva = round(random.uniform(0, 90), 1)
            leitura.update({
                "temperatura_ar": round(random.uniform(12, 38), 1),
                "precipitacao_mm": chuva,
                "umidade_solo": round(min(95, max(5, chuva * 0.6 + 12)), 1),
                "velocidade_vento": round(random.uniform(0, 45), 1),
                "condicao_clima": (
                    "ensolarado" if chuva <= 2 else
                    "nublado" if chuva <= 20 else
                    "chuvoso" if chuva <= 50 else "tempestade"
                ),
            })

        try:
            r = requests.post(
                f"{args.api}/avaliacoes", json=leitura, headers=cabecalho, timeout=30
            )
        except requests.RequestException as e:
            falhas += 1
            print(f"  [{i}/{args.n}] FALHA de rede: {e}")
            continue

        if r.status_code == 201:
            d = r.json()
            enviadas += 1
            marca = {"baixo": "  ", "medio": "! ", "alto": "!!"}[d["faixa_risco"]]
            print(
                f"  [{i}/{args.n}] {marca} {d['equipamento_id']} {regiao:<16} "
                f"{leitura['tipo_operacao']:<13} {leitura['horario_operacao']:02d}h  "
                f"score {d['risco_score']:>6.2f} [{d['faixa_risco']:<5}] "
                f"clima={d['clima_origem']}"
            )
            topo = d["top_fatores"][0]
            print(f"          fator principal: {topo['feature']} ({topo['shap_value']:+.2f})")
        else:
            falhas += 1
            print(f"  [{i}/{args.n}] HTTP {r.status_code}: {r.text[:160]}")

        if i < args.n:
            time.sleep(args.intervalo)

    print()
    print("=" * 62)
    print(f"Enviadas com sucesso: {enviadas}  |  falhas: {falhas}")
    if falhas:
        sys.exit(1)


if __name__ == "__main__":
    main()
