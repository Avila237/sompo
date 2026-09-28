"""
Recomendacoes preventivas (S4-25): o que fazer diante do risco, e por que.

Regra deterministica, nunca texto gerado: cada recomendacao sai de uma
condicao explicita sobre a leitura e carrega o criterio que a disparou, com os
valores reais. As regras sao as interacoes de risco de docs/data schema.md
(secao 4.3), o conhecimento de dominio que gerou o dataset, mais a de
manutencao atrasada.

Garantia: toda avaliacao de faixa media ou alta recebe ao menos uma
recomendacao. Sem regra disparada, entra a do fator SHAP que mais empurrou o
risco para cima; sem fator positivo, a de monitoramento.
"""

from dataclasses import dataclass
from typing import Callable

PUBLICOS = ("operador", "gestor", "tecnico")


def _noturno(r: dict) -> bool:
    h = r.get("horario_operacao")
    return h is not None and (h >= 20 or h <= 5)


def _tem(r: dict, *campos: str) -> bool:
    return all(r.get(c) is not None for c in campos)


@dataclass(frozen=True)
class Regra:
    id: str
    publico: str
    acao: str
    condicao: Callable[[dict], bool]
    criterio: Callable[[dict], str]


# Ordem = prioridade de exibicao. Limiares iguais aos de docs/data schema.md 4.3.
REGRAS: tuple[Regra, ...] = (
    Regra(
        "solo_encharcado", "gestor",
        "Adiar a operação ou mudar de talhão: solo argiloso encharcado favorece atolamento.",
        lambda r: _tem(r, "precipitacao_mm") and r["precipitacao_mm"] > 30 and r.get("tipo_solo") == "argiloso",
        lambda r: f"precipitacao_mm={r['precipitacao_mm']:g} > 30 e tipo_solo=argiloso",
    ),
    Regra(
        "tombamento", "operador",
        "Reduzir a velocidade abaixo de 20 km/h neste terreno: risco de tombamento.",
        lambda r: _tem(r, "velocidade_kmh", "declividade") and r["velocidade_kmh"] > 20 and r["declividade"] > 15,
        lambda r: f"velocidade_kmh={r['velocidade_kmh']:g} > 20 e declividade={r['declividade']:g}% > 15",
    ),
    Regra(
        "margem_alagavel", "gestor",
        "Afastar a operação da margem até o solo secar: área alagável após chuva.",
        lambda r: _tem(r, "distancia_agua_m", "precipitacao_mm") and r["distancia_agua_m"] < 200 and r["precipitacao_mm"] > 25,
        lambda r: f"distancia_agua_m={r['distancia_agua_m']:g} < 200 e precipitacao_mm={r['precipitacao_mm']:g} > 25",
    ),
    Regra(
        "velocidade_noturna", "operador",
        "Reduzir a velocidade à noite para abaixo de 15 km/h: visibilidade reduzida.",
        lambda r: _noturno(r) and _tem(r, "velocidade_kmh") and r["velocidade_kmh"] > 15,
        lambda r: f"horario_operacao={r['horario_operacao']}h (noturno) e velocidade_kmh={r['velocidade_kmh']:g} > 15",
    ),
    Regra(
        "vibracao_equipamento_antigo", "tecnico",
        "Inspecionar o equipamento antes da próxima operação: vibração alta em máquina antiga antecede falha mecânica.",
        lambda r: _tem(r, "idade_equipamento", "vibracao_g") and r["idade_equipamento"] > 10 and r["vibracao_g"] > 2.0,
        lambda r: f"idade_equipamento={r['idade_equipamento']} anos > 10 e vibracao_g={r['vibracao_g']:g} > 2.0",
    ),
    Regra(
        "transporte_em_declive", "gestor",
        "Trocar a rota de transporte ou limitar a velocidade a 25 km/h: trajeto inclinado.",
        lambda r: r.get("tipo_operacao") == "transporte" and _tem(r, "velocidade_kmh", "declividade")
        and r["velocidade_kmh"] > 25 and r["declividade"] > 10,
        lambda r: f"transporte a velocidade_kmh={r['velocidade_kmh']:g} > 25 com declividade={r['declividade']:g}% > 10",
    ),
    Regra(
        "fadiga_noturna", "gestor",
        "Programar pausa ou troca de operador: jornada longa em horário noturno.",
        lambda r: _noturno(r) and _tem(r, "horas_operacao") and r["horas_operacao"] > 8,
        lambda r: f"horas_operacao={r['horas_operacao']:g} > 8 com horario_operacao={r['horario_operacao']}h (noturno)",
    ),
    Regra(
        "historico_e_jornada_longa", "gestor",
        "Limitar a jornada deste equipamento: histórico de sinistros somado a operação prolongada.",
        lambda r: _tem(r, "historico_sinistros", "horas_operacao") and r["historico_sinistros"] >= 4 and r["horas_operacao"] > 8,
        lambda r: f"historico_sinistros={r['historico_sinistros']} >= 4 e horas_operacao={r['horas_operacao']:g} > 8",
    ),
    Regra(
        "conducao_agressiva_na_chuva", "gestor",
        "Orientar o operador sobre velocidade em pista molhada: condução acima do recomendado com chuva.",
        lambda r: _tem(r, "pct_velocidade_acima_recomendada", "precipitacao_mm")
        and r["pct_velocidade_acima_recomendada"] > 30 and r["precipitacao_mm"] > 20,
        lambda r: f"pct_velocidade_acima_recomendada={r['pct_velocidade_acima_recomendada']:g}% > 30 "
        f"e precipitacao_mm={r['precipitacao_mm']:g} > 20",
    ),
    Regra(
        "manutencao_vencida_e_uso_intenso", "tecnico",
        "Fazer a manutenção antes de nova jornada longa: intervalo vencido com uso intenso.",
        lambda r: _tem(r, "atraso_manutencao_pct", "horas_operacao") and r["atraso_manutencao_pct"] > 1.2 and r["horas_operacao"] > 8,
        lambda r: f"atraso_manutencao_pct={r['atraso_manutencao_pct']:g} > 1.2 e horas_operacao={r['horas_operacao']:g} > 8",
    ),
    Regra(
        "escala_noturna_habitual", "gestor",
        "Revisar a escala deste operador: operação noturna frequente acumula fadiga.",
        lambda r: _noturno(r) and _tem(r, "pct_operacoes_noturnas") and r["pct_operacoes_noturnas"] > 50,
        lambda r: f"pct_operacoes_noturnas={r['pct_operacoes_noturnas']:g}% > 50 e operação atual noturna "
        f"({r['horario_operacao']}h)",
    ),
    Regra(
        "manutencao_atrasada", "tecnico",
        "Agendar a manutenção: o intervalo recomendado pelo fabricante foi ultrapassado.",
        lambda r: bool(r.get("manutencao_atrasada")),
        lambda r: f"manutencao_atrasada=true (atraso_manutencao_pct={r.get('atraso_manutencao_pct', 0):g} > 1.0)",
    ),
)

# Quem age sobre cada grupo de fatores, e o que fazer, quando nenhuma regra
# de interacao dispara e a recomendacao vem do fator dominante.
_POR_GRUPO: dict[str, tuple[str, str]] = {
    "ambiental": ("gestor", "Reavaliar a operação diante das condições climáticas."),
    "geografico": ("gestor", "Revisar a área e a rota: terreno, solo e proximidade de água pesam no risco."),
    "operacional": ("operador", "Reduzir velocidade e duração da operação."),
    "equipamento": ("tecnico", "Inspecionar o equipamento e acompanhar seu histórico antes de operar."),
    "operador": ("gestor", "Orientar o operador sobre o padrão de condução."),
    "manutencao": ("tecnico", "Antecipar a manutenção preventiva."),
}


def _fator_dominante(registro: dict, faixa: str, top_fatores: list[dict]) -> dict:
    positivos = [f for f in top_fatores if (f.get("shap_value") or 0) > 0]
    if not positivos:
        return {
            "id": "monitorar",
            "publico": "gestor",
            "acao": "Acompanhar este equipamento nas próximas avaliações.",
            "criterio": f"faixa_risco={faixa} sem fator isolado que eleve o risco",
        }
    fator = max(positivos, key=lambda f: f["shap_value"])
    feature = fator["feature"]
    publico, acao = _POR_GRUPO.get(fator.get("grupo"), ("gestor", "Revisar o fator de maior peso no risco."))
    # O valor legivel vem da leitura; o de top_fatores e o codificado para o modelo.
    valor = registro.get(feature, fator.get("valor"))
    return {
        "id": "fator_dominante",
        "publico": publico,
        "acao": acao,
        "criterio": f"maior contribuição para o risco: {feature}={valor} (+{fator['shap_value']:.1f} pontos)",
    }


def recomendar(registro: dict, faixa: str, top_fatores: list[dict]) -> list[dict]:
    """
    Recomendacoes para uma avaliacao. `registro` traz as features da leitura
    somadas ao cadastro do equipamento; campo ausente nunca dispara regra.
    """
    recs = [
        {"id": r.id, "publico": r.publico, "acao": r.acao, "criterio": r.criterio(registro)}
        for r in REGRAS
        if r.condicao(registro)
    ]
    if not recs and faixa in ("medio", "alto"):
        recs.append(_fator_dominante(registro, faixa, top_fatores))
    return recs
