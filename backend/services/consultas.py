"""
Agregacoes de leitura para o dashboard (RF-09).

A regra de alerta vive aqui, no servidor — antes era derivada no cliente por
buildAlertas(). Portada fielmente para nao mudar o comportamento da Visao Geral:
avaliacoes mais recentes primeiro, descartando faixa 'baixo'.
"""

from collections import defaultdict

from backend.db import repository as repo

# Limites do territorio brasileiro, usados para projetar lat/long em 0..1.
LAT_MIN, LAT_MAX = -33.75, -2.50
LON_MIN, LON_MAX = -73.99, -34.79


def _faixa(score: float) -> str:
    if score <= 33:
        return "baixo"
    if score <= 66:
        return "medio"
    return "alto"


def normalizar_fatores_shap(fatores: list | None) -> list[dict]:
    """
    Uniformiza o JSONB de top_fatores_shap.

    As 5.000 predicoes do seed foram gravadas por populate_predictions.py com
    as chaves {feature, group, shap_value}. As geradas pela API usam
    {feature, grupo, shap_value, valor}. A API sempre devolve o formato em
    portugues; 'valor' vem nulo quando a predicao e do seed, que nao o gravou.

    Normalizar na leitura evita migrar 5.000 linhas e protege o cliente de
    quebrar em silencio ao encontrar um registro legado.
    """
    if not fatores:
        return []
    saida = []
    for f in fatores:
        saida.append(
            {
                "feature": f.get("feature"),
                "valor": f.get("valor"),
                "shap_value": f.get("shap_value"),
                "grupo": f.get("grupo") or f.get("group") or "outros",
            }
        )
    return saida


def _por_equipamento() -> dict[str, list[dict]]:
    agrupado: dict[str, list[dict]] = defaultdict(list)
    for a in repo.listar_avaliacoes_resumo():
        agrupado[a["equipamento_id"]].append(a)
    for lista in agrupado.values():
        lista.sort(key=lambda x: x["timestamp"], reverse=True)
    return agrupado


def listar_equipamentos() -> list[dict]:
    """Uma linha por equipamento, com o score da avaliacao mais recente."""
    agrupado = _por_equipamento()
    saida = []
    for eq in repo.listar_equipamentos():
        avals = agrupado.get(eq["equipamento_id"], [])
        ultima = avals[0] if avals else None
        anterior = avals[1] if len(avals) > 1 else None
        score = float(ultima["risco_score"]) if ultima else 0.0
        media = sum(float(a["risco_score"]) for a in avals) / len(avals) if avals else 0.0
        saida.append(
            {
                "equipamento_id": eq["equipamento_id"],
                "modelo_equipamento": eq["modelo_equipamento"],
                "tipo_equipamento": eq["tipo_equipamento"],
                "idade_equipamento": eq["idade_equipamento"],
                "historico_sinistros": eq["historico_sinistros"],
                "tem_iot": eq["tem_iot"],
                "risco_score": round(score, 2),
                "score_medio": round(media, 2),
                "faixa_risco": _faixa(score),
                "tendencia": round(score - float(anterior["risco_score"]), 2) if anterior else 0.0,
                "total_avaliacoes": len(avals),
                "operador_id": ultima["operador_id"] if ultima else None,
                "ultima_avaliacao": ultima["timestamp"] if ultima else None,
                "latitude": float(ultima["latitude"]) if ultima else None,
                "longitude": float(ultima["longitude"]) if ultima else None,
            }
        )
    saida.sort(key=lambda e: e["risco_score"], reverse=True)
    return saida


def detalhe_equipamento(equipamento_id: str) -> dict | None:
    """Ultima avaliacao, predicao com SHAP e serie historica de score."""
    equipamento = repo.buscar_equipamento(equipamento_id)
    if equipamento is None:
        return None

    ultima = repo.ultima_avaliacao(equipamento_id)
    predicao = repo.predicao_de(ultima["avaliacao_id"]) if ultima else None
    if predicao is not None:
        predicao["top_fatores_shap"] = normalizar_fatores_shap(
            predicao.get("top_fatores_shap")
        )

    historico = [
        {"timestamp": a["timestamp"], "risco_score": float(a["risco_score"])}
        for a in repo.listar_avaliacoes_resumo()
        if a["equipamento_id"] == equipamento_id
    ]
    historico.sort(key=lambda h: h["timestamp"])

    return {
        "equipamento": equipamento,
        "ultima_avaliacao": ultima,
        "predicao": predicao,
        "historico": historico,
    }


def kpis() -> dict:
    """Indicadores da Visao Geral."""
    avals = repo.listar_avaliacoes_resumo()
    equipamentos = listar_equipamentos()
    total_aval = len(avals)
    soma = sum(float(a["risco_score"]) for a in avals)
    risco_alto = sum(1 for e in equipamentos if e["faixa_risco"] == "alto")
    total_eq = len(equipamentos)

    por_faixa: dict[str, int] = {"baixo": 0, "medio": 0, "alto": 0}
    for a in avals:
        por_faixa[_faixa(float(a["risco_score"]))] += 1

    return {
        "total_equipamentos": total_eq,
        "total_avaliacoes": total_aval,
        "score_medio": round(soma / total_aval, 2) if total_aval else 0.0,
        "equipamentos_risco_alto": risco_alto,
        "pct_risco_alto": round(risco_alto / total_eq * 100, 2) if total_eq else 0.0,
        "avaliacoes_por_faixa": por_faixa,
    }


def agregado_por_operacao() -> list[dict]:
    """
    Agregacao por tipo de operacao — o enunciado pede as tres visoes
    (equipamento, operacao, regiao) e esta era a que faltava.
    """
    acumulado: dict[str, dict] = defaultdict(lambda: {"soma": 0.0, "n": 0, "alto": 0})
    for a in repo.listar_avaliacoes_resumo():
        op = a.get("tipo_operacao") or "desconhecida"
        score = float(a["risco_score"])
        acumulado[op]["soma"] += score
        acumulado[op]["n"] += 1
        if _faixa(score) == "alto":
            acumulado[op]["alto"] += 1

    saida = [
        {
            "tipo_operacao": op,
            "total_avaliacoes": v["n"],
            "score_medio": round(v["soma"] / v["n"], 2) if v["n"] else 0.0,
            "avaliacoes_risco_alto": v["alto"],
        }
        for op, v in acumulado.items()
    ]
    saida.sort(key=lambda x: x["score_medio"], reverse=True)
    return saida


def agregado_por_regiao(celula_graus: int = 3, limite: int = 14) -> list[dict]:
    """Agrupa por celula geografica, projetando lat/long em 0..1 para o mapa."""
    celulas: dict[tuple[int, int], dict] = defaultdict(lambda: {"soma": 0.0, "n": 0})
    for e in listar_equipamentos():
        if e["latitude"] is None or e["longitude"] is None:
            continue
        chave = (
            round(e["latitude"] / celula_graus) * celula_graus,
            round(e["longitude"] / celula_graus) * celula_graus,
        )
        celulas[chave]["soma"] += e["risco_score"]
        celulas[chave]["n"] += 1

    saida = []
    for (lat, lon), v in celulas.items():
        saida.append(
            {
                "nome": f"{abs(lat):.0f}°S {abs(lon):.0f}°O",
                "latitude": lat,
                "longitude": lon,
                "x": max(0.04, min(0.96, (lon - LON_MIN) / (LON_MAX - LON_MIN))),
                "y": max(0.04, min(0.96, (LAT_MAX - lat) / (LAT_MAX - LAT_MIN))),
                "total_equipamentos": v["n"],
                "score_medio": round(v["soma"] / v["n"], 2),
            }
        )
    saida.sort(key=lambda r: r["total_equipamentos"], reverse=True)
    return saida[:limite]


def alertas(limite: int = 7, faixa_minima: str = "medio") -> list[dict]:
    """
    Regra de alerta (portada de buildAlertas, que rodava no cliente):
    avaliacoes ordenadas da mais recente para a mais antiga, descartando as de
    faixa abaixo de `faixa_minima`, limitadas a `limite`.

    faixa_minima='medio' reproduz o comportamento anterior (faixa != 'baixo').
    """
    ordem = {"baixo": 0, "medio": 1, "alto": 2}
    corte = ordem.get(faixa_minima, 1)

    recentes = sorted(
        repo.listar_avaliacoes_resumo(), key=lambda a: a["timestamp"], reverse=True
    )
    saida = []
    for a in recentes:
        score = float(a["risco_score"])
        faixa = _faixa(score)
        if ordem[faixa] < corte:
            continue
        saida.append(
            {
                "avaliacao_id": a["avaliacao_id"],
                "equipamento_id": a["equipamento_id"],
                "operador_id": a["operador_id"],
                "risco_score": round(score, 2),
                "faixa_risco": faixa,
                "tipo_operacao": a.get("tipo_operacao"),
                "timestamp": a["timestamp"],
                "mensagem": f"{a['equipamento_id']} · score {round(score)} · risco {faixa}",
            }
        )
        if len(saida) >= limite:
            break
    return saida
