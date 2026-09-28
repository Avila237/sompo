"""
Agregacoes de leitura para o dashboard (RF-09).

A regra de alerta vive aqui, no servidor — antes era derivada no cliente por
buildAlertas(). Portada fielmente para nao mudar o comportamento da Visao Geral:
avaliacoes mais recentes primeiro, descartando faixa 'baixo'.
"""

from collections import defaultdict

from backend.db import repository as repo
from backend.ml.preprocess import derive_faixa
from backend.services.recomendacoes import recomendar

# Limites do territorio brasileiro, usados para projetar lat/long em 0..1.
LAT_MIN, LAT_MAX = -33.75, -2.50
LON_MIN, LON_MAX = -73.99, -34.79

# Colunas da idempotencia (S4-12): servem ao servidor, nao a quem le.
CAMPOS_INTERNOS = ("leitura_id", "payload_hash")

# LGPD, minimizacao: da avaliacao de outro operador, o operador nao recebe
# quem operou nem onde. Ver minimizar_para_operador().
CAMPOS_DE_OUTRO_OPERADOR = ("operador_id", "latitude", "longitude")


def _celula(latitude: float, longitude: float, graus: int = 3) -> tuple[int, int]:
    """Canto da celula geografica de `graus` graus que contem a coordenada."""
    return round(latitude / graus) * graus, round(longitude / graus) * graus


def _rotulo_celula(lat: int, lon: int) -> str:
    return f"{abs(lat):.0f}°S {abs(lon):.0f}°O"


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
                # A faixa gravada veio do score cru; recalcular sobre o score
                # gravado (2 casas) divergiria logo acima de 33 e de 66.
                "faixa_risco": ultima["faixa_risco"] if ultima else derive_faixa(score),
                "tendencia": round(score - float(anterior["risco_score"]), 2) if anterior else 0.0,
                "total_avaliacoes": len(avals),
                "operador_id": ultima["operador_id"] if ultima else None,
                "ultima_avaliacao": ultima["timestamp"] if ultima else None,
                "latitude": float(ultima["latitude"]) if ultima else None,
                "longitude": float(ultima["longitude"]) if ultima else None,
                # Manutencao da ultima avaliacao (S4-36): a tela do tecnico ordena
                # por ela. .get(): linha sem a coluna vira null, nao KeyError.
                "manutencao_atrasada": ultima.get("manutencao_atrasada") if ultima else None,
                "atraso_manutencao_pct": ultima.get("atraso_manutencao_pct") if ultima else None,
                "ultima_manutencao_dias": ultima.get("ultima_manutencao_dias") if ultima else None,
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
    if ultima is not None:
        ultima = {k: v for k, v in ultima.items() if k not in CAMPOS_INTERNOS}
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
        "recomendacoes": _recomendacoes(equipamento, ultima, predicao),
        "historico": historico,
    }


def _recomendacoes(equipamento: dict, ultima: dict | None, predicao: dict | None) -> list[dict]:
    if ultima is None:
        return []
    # A avaliacao nao repete o cadastral (idade, historico de sinistros):
    # as regras leem a leitura somada ao cadastro do equipamento.
    return recomendar(
        {**equipamento, **ultima},
        ultima["faixa_risco"],
        predicao["top_fatores_shap"] if predicao else [],
    )


def _sem_quem_nem_onde(registro: dict) -> dict:
    """Copia com os campos do operador em null. Nao cria campo que o registro nao tem."""
    return {k: None if k in CAMPOS_DE_OUTRO_OPERADOR else v for k, v in registro.items()}


def minimizar_para_operador(resposta: dict, operador_id: str) -> dict:
    """
    LGPD, minimizacao (S4-18): o operador ve os equipamentos que ja operou, mas
    a avaliacao de um deles pode ser de outro operador. Dessa, operador_id,
    latitude e longitude saem null; as do proprio operador saem intactas.

    Ponto unico da regra, chamado na borda das rotas de leitura so para o
    perfil operador. Cobre os dois formatos: lista em `itens` (GET
    /equipamentos, GET /alertas) e o detalhe (GET /equipamentos/{id}).
    Devolve copia; a resposta recebida nao e alterada.
    """
    saida = dict(resposta)
    if "itens" in saida:
        saida["itens"] = [
            _sem_quem_nem_onde(r) if r.get("operador_id") != operador_id else r
            for r in saida["itens"]
        ]

    ultima = saida.get("ultima_avaliacao")
    if ultima is None or ultima.get("operador_id") == operador_id:
        return saida
    saida["ultima_avaliacao"] = _sem_quem_nem_onde(ultima)
    predicao = saida.get("predicao")
    if predicao is not None:
        # latitude e longitude sao features: o 'valor' do fator SHAP repetiria a posicao.
        saida["predicao"] = {
            **predicao,
            "top_fatores_shap": [
                {**f, "valor": None} if f["feature"] in CAMPOS_DE_OUTRO_OPERADOR else f
                for f in predicao["top_fatores_shap"]
            ],
        }
    # Refeitas sobre a avaliacao mascarada: o criterio do fator dominante citaria a posicao.
    saida["recomendacoes"] = _recomendacoes(
        saida["equipamento"], saida["ultima_avaliacao"], saida["predicao"]
    )
    return saida


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
        por_faixa[a["faixa_risco"]] += 1

    operadores = {a["operador_id"] for a in avals if a.get("operador_id")}

    return {
        "total_equipamentos": total_eq,
        "total_operadores": len(operadores),
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
        if a["faixa_risco"] == "alto":
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
        chave = _celula(e["latitude"], e["longitude"], celula_graus)
        celulas[chave]["soma"] += e["risco_score"]
        celulas[chave]["n"] += 1

    saida = []
    for (lat, lon), v in celulas.items():
        saida.append(
            {
                "nome": _rotulo_celula(lat, lon),
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


def equipamentos_do_operador(operador_id: str) -> set[str]:
    """Equipamentos que o operador ja operou: o recorte do perfil operador (S4-18)."""
    return {
        a["equipamento_id"] for a in repo.listar_avaliacoes_resumo()
        if a["operador_id"] == operador_id
    }


def alertas(
    limite: int = 7, faixa_minima: str = "medio", equipamentos: set[str] | None = None
) -> list[dict]:
    """
    Regra de alerta (portada de buildAlertas, que rodava no cliente):
    avaliacoes ordenadas da mais recente para a mais antiga, descartando as de
    faixa abaixo de `faixa_minima`, limitadas a `limite`.

    faixa_minima='medio' reproduz o comportamento anterior (faixa != 'baixo').
    `equipamentos` restringe a um recorte, filtrado antes do limite.
    """
    ordem = {"baixo": 0, "medio": 1, "alto": 2}
    corte = ordem.get(faixa_minima, 1)

    recentes = sorted(
        repo.listar_avaliacoes_resumo(), key=lambda a: a["timestamp"], reverse=True
    )
    saida = []
    for a in recentes:
        score = float(a["risco_score"])
        faixa = a["faixa_risco"]
        if ordem[faixa] < corte:
            continue
        if equipamentos is not None and a["equipamento_id"] not in equipamentos:
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


def tendencia(dias: int = 30) -> list[dict]:
    """
    Media diaria de score nos ultimos `dias` COM DADOS.

    A janela conta dias que tem avaliacao, nao dias corridos. O seed cobre 2025
    e a ingestao grava em 2026: ancorar num intervalo de calendario devolveria
    uma serie de um ponto so, porque nao ha nada entre as duas pontas.

    Antes vivia no cliente (buildTrend), que precisava baixar as 5.000
    avaliacoes para calcular. Passou para o servidor com as demais agregacoes.
    """
    avals = repo.listar_avaliacoes_resumo()
    if not avals:
        return []

    por_dia: dict[str, list[float]] = defaultdict(list)
    for a in avals:
        por_dia[a["timestamp"][:10]].append(float(a["risco_score"]))

    ultimos = sorted(por_dia)[-dias:]
    return [
        {
            "dia": dia,
            "score_medio": round(sum(por_dia[dia]) / len(por_dia[dia]), 2),
            "avaliacoes": len(por_dia[dia]),
        }
        for dia in ultimos
    ]


EIXOS_TENDENCIA = ("equipamento", "regiao", "operacao")


def _chave_do_eixo(avaliacao: dict, eixo: str) -> str | None:
    """Grupo da avaliacao no eixo pedido; None tira a avaliacao da serie."""
    if eixo == "equipamento":
        return avaliacao["equipamento_id"]
    if eixo == "operacao":
        return avaliacao.get("tipo_operacao") or "desconhecida"
    # regiao: a posicao da propria avaliacao, nao a ultima do equipamento
    # (como em agregado_por_regiao): cada ponto e a regiao onde ela aconteceu.
    if avaliacao.get("latitude") is None or avaliacao.get("longitude") is None:
        return None
    return _rotulo_celula(*_celula(float(avaliacao["latitude"]), float(avaliacao["longitude"])))


def tendencias(eixo: str, dias: int = 30, limite: int = 5, chave: str | None = None) -> dict:
    """
    Serie de score medio diario por grupo, num dos tres eixos.

    Contrato em docs/contrato-api.md (GET /tendencias). A janela sao os ultimos
    `dias` dias COM DADOS na base inteira, como em tendencia(): todas as series
    dividem o mesmo eixo X. Dia sem avaliacao do grupo nao vira ponto (lacuna,
    nao zero). Entram os `limite` grupos de maior score medio na janela, ou so
    o grupo `chave`.
    """
    avals = repo.listar_avaliacoes_resumo()
    dias_da_base = sorted({a["timestamp"][:10] for a in avals})
    janela = set(dias_da_base[-dias:])

    # grupo -> dia -> scores
    por_grupo: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for a in avals:
        dia = a["timestamp"][:10]
        if dia not in janela:
            continue
        grupo = _chave_do_eixo(a, eixo)
        if grupo is None or (chave is not None and grupo != chave):
            continue
        por_grupo[grupo][dia].append(float(a["risco_score"]))

    series = []
    for grupo, por_dia in por_grupo.items():
        todos = [v for scores in por_dia.values() for v in scores]
        series.append(
            {
                "chave": grupo,
                "rotulo": grupo,
                "score_medio": round(sum(todos) / len(todos), 2),
                "avaliacoes": len(todos),
                "pontos": [
                    {
                        "dia": dia,
                        "score_medio": round(sum(por_dia[dia]) / len(por_dia[dia]), 2),
                        "avaliacoes": len(por_dia[dia]),
                    }
                    for dia in sorted(por_dia)
                ],
            }
        )
    series.sort(key=lambda s: (s["score_medio"], s["avaliacoes"]), reverse=True)
    if chave is None:
        series = series[:limite]

    ordenados = sorted(janela)
    return {
        "eixo": eixo,
        "dias": dias,
        "janela": {
            "inicio": ordenados[0] if ordenados else None,
            "fim": ordenados[-1] if ordenados else None,
            "dias_com_dados": len(ordenados),
            # eixo X comum: nem toda data da janela aparece nos pontos das series devolvidas
            "datas": ordenados,
        },
        "series": series,
    }
