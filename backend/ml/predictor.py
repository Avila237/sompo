"""
Carga do modelo e inferencia com explicabilidade.

Os artefatos e o TreeExplainer sao carregados UMA vez, no startup da API.
Reconstrui-los por requisicao inviabiliza a latencia: o TreeExplainer percorre
as 300 arvores do modelo a cada construcao.
"""

import json
import os
from dataclasses import dataclass, field

import joblib
import numpy as np
import pandas as pd
import shap

from backend.ml.preprocess import FEATURE_TO_GROUP, derive_faixa, preprocess_features


@dataclass
class Explicacao:
    """Resultado de uma predicao, sempre acompanhada da sua decomposicao (RF-10)."""

    risco_score: float
    faixa_risco: str
    contribuicoes_por_grupo: dict[str, float] = field(default_factory=dict)
    top_fatores: list[dict] = field(default_factory=list)


class Predictor:
    """Encapsula modelo, encoder e explainer. Instanciar uma vez por processo."""

    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        caminho_modelo = os.path.join(models_dir, "xgboost_model.joblib")
        caminho_encoder = os.path.join(models_dir, "encoder.joblib")
        caminho_features = os.path.join(models_dir, "features.json")

        faltando = [
            c for c in (caminho_modelo, caminho_encoder, caminho_features)
            if not os.path.isfile(c)
        ]
        if faltando:
            raise FileNotFoundError(
                "Artefatos do modelo ausentes: "
                + ", ".join(faltando)
                + ". Rode 'python backend/ml/train.py' antes de subir a API."
            )

        self.model = joblib.load(caminho_modelo)
        self.encoder = joblib.load(caminho_encoder)
        with open(caminho_features) as f:
            self.features: list[str] = json.load(f)
        self.explainer = shap.TreeExplainer(self.model)

    def preparar(self, registro: dict) -> pd.DataFrame:
        """Monta o vetor de features na ordem exata em que o modelo foi treinado."""
        faltando = [f for f in self.features if f not in registro]
        if faltando:
            raise ValueError(f"Features ausentes no registro: {', '.join(faltando)}")
        df = pd.DataFrame([{f: registro[f] for f in self.features}])
        return preprocess_features(df, self.encoder)

    def prever(self, registro: dict, top_n: int = 5) -> Explicacao:
        """
        Prediz o score e devolve a decomposicao SHAP junto — nunca o score sozinho.

        As contribuicoes por grupo sao somadas COM SINAL (positivo aumenta o risco,
        negativo reduz), que e a semantica que a interface exibe. Difere de
        shap_explainer.group_contributions(), que soma |SHAP| para medir magnitude.
        """
        X = self.preparar(registro)
        score = float(self.model.predict(X)[0])
        score = float(np.clip(score, 0, 100))

        valores = self.explainer.shap_values(X)[0]

        grupos: dict[str, float] = {}
        for feature, valor in zip(self.features, valores):
            grupo = FEATURE_TO_GROUP.get(feature, "outros")
            grupos[grupo] = grupos.get(grupo, 0.0) + float(valor)

        indices = np.argsort(np.abs(valores))[::-1][:top_n]
        top = [
            {
                "feature": self.features[i],
                "valor": _py(X.iloc[0][self.features[i]]),
                "shap_value": round(float(valores[i]), 4),
                "grupo": FEATURE_TO_GROUP.get(self.features[i], "outros"),
            }
            for i in indices
        ]

        return Explicacao(
            risco_score=round(score, 2),
            faixa_risco=derive_faixa(score),
            contribuicoes_por_grupo={g: round(v, 4) for g, v in grupos.items()},
            top_fatores=top,
        )


def _py(valor):
    """Converte tipos numpy/pandas para tipos nativos serializaveis em JSON."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return None
    if hasattr(valor, "item"):
        return valor.item()
    return valor


_predictor: Predictor | None = None


def get_predictor(models_dir: str = "models") -> Predictor:
    """Singleton por processo. Carregado no startup da API."""
    global _predictor
    if _predictor is None:
        _predictor = Predictor(models_dir)
    return _predictor
