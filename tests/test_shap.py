import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.ml.shap_explainer import (
    FEATURE_GROUPS,
    _FEATURE_TO_GROUP,
    compute_shap_values,
    explain_record,
    group_contributions,
    load_artifacts,
    save_plots,
    save_shap_values,
    top_features_global,
)
from backend.ml.train import derive_faixa, preprocess_features

MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "dataset_safefield.parquet")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def artifacts():
    return load_artifacts(MODELS_DIR)


@pytest.fixture(scope="module")
def features(artifacts):
    return artifacts[2]


@pytest.fixture(scope="module")
def X_sample(artifacts):
    _, encoder, feats = artifacts
    df = pd.read_parquet(DATA_PATH)
    sample = df.sample(200, random_state=42).reset_index(drop=True)
    return preprocess_features(sample[feats].copy(), encoder)


@pytest.fixture(scope="module")
def y_pred(artifacts, X_sample):
    model, _, _ = artifacts
    return model.predict(X_sample)


@pytest.fixture(scope="module")
def shap_vals(artifacts, X_sample):
    model, _, _ = artifacts
    return compute_shap_values(model, X_sample)


@pytest.fixture(scope="module")
def shap_npy_path(shap_vals):
    return save_shap_values(shap_vals, MODELS_DIR)


@pytest.fixture(scope="module")
def saved_plots_list(artifacts, shap_vals, X_sample, y_pred, features):
    model, _, _ = artifacts
    return save_plots(model, shap_vals, X_sample, y_pred, features, DATA_DIR)


# ---------------------------------------------------------------------------
# Mapeamento de grupos
# ---------------------------------------------------------------------------

class TestMapeamentoGrupos:
    def test_todos_os_6_grupos_presentes(self):
        assert set(FEATURE_GROUPS.keys()) == {
            "ambiental", "geografico", "operacional",
            "equipamento", "operador", "manutencao",
        }

    def test_todas_features_mapeadas_em_algum_grupo(self, features):
        for feat in features:
            assert feat in _FEATURE_TO_GROUP, f"Feature '{feat}' nao mapeada em nenhum grupo"

    def test_nenhuma_feature_duplicada_entre_grupos(self):
        all_feats = [f for feats in FEATURE_GROUPS.values() for f in feats]
        assert len(all_feats) == len(set(all_feats)), "Ha features duplicadas entre grupos"

    def test_total_features_nos_grupos_e_30(self):
        total = sum(len(v) for v in FEATURE_GROUPS.values())
        assert total == 30, f"Esperado 30 features nos grupos, encontrado {total}"

    def test_grupos_cobrem_exatamente_as_features_do_modelo(self, features):
        feature_set = set(features)
        grouped = {f for feats in FEATURE_GROUPS.values() for f in feats}
        diff = feature_set.symmetric_difference(grouped)
        assert diff == set(), f"Discrepancia entre features do modelo e grupos: {diff}"


# ---------------------------------------------------------------------------
# SHAP values
# ---------------------------------------------------------------------------

class TestSHAPValues:
    def test_calcula_sem_erro(self, shap_vals):
        assert shap_vals is not None

    def test_shape_correto(self, shap_vals, X_sample, features):
        assert shap_vals.shape == (len(X_sample), len(features))

    def test_dtype_e_float(self, shap_vals):
        assert shap_vals.dtype.kind == "f", f"Esperado float, encontrado {shap_vals.dtype}"

    def test_sem_nan(self, shap_vals):
        assert not np.isnan(shap_vals).any(), "SHAP values contem NaN"

    def test_valores_nao_todos_zero(self, shap_vals):
        assert np.abs(shap_vals).sum() > 0, "Todos os SHAP values sao zero"


# ---------------------------------------------------------------------------
# Contribuicoes por grupo
# ---------------------------------------------------------------------------

class TestContribuicoesPorGrupo:
    def test_retorna_dataframe(self, shap_vals, features):
        assert isinstance(group_contributions(shap_vals, features), pd.DataFrame)

    def test_6_colunas(self, shap_vals, features):
        assert group_contributions(shap_vals, features).shape[1] == 6

    def test_colunas_sao_nomes_dos_grupos(self, shap_vals, features):
        df = group_contributions(shap_vals, features)
        assert set(df.columns) == set(FEATURE_GROUPS.keys())

    def test_numero_de_registros(self, shap_vals, features, X_sample):
        assert len(group_contributions(shap_vals, features)) == len(X_sample)

    def test_valores_nao_negativos(self, shap_vals, features):
        df = group_contributions(shap_vals, features)
        assert (df >= 0).all().all(), "Contribuicoes por grupo devem ser nao-negativas"

    def test_soma_grupos_igual_total_abs_shap(self, shap_vals, features):
        group_df = group_contributions(shap_vals, features)
        group_sum = group_df.sum(axis=1).values
        total_abs = np.abs(shap_vals).sum(axis=1)
        diff = np.abs(group_sum - total_abs)
        assert diff.max() < 0.01, f"Diferenca maxima: {diff.max():.6f}"


# ---------------------------------------------------------------------------
# Explicacao individual
# ---------------------------------------------------------------------------

class TestExplicacaoIndividual:
    def test_retorna_lista(self, shap_vals, features):
        assert isinstance(explain_record(shap_vals, features, idx=0), list)

    def test_tamanho_top_n(self, shap_vals, features):
        for n in (3, 5, 8):
            assert len(explain_record(shap_vals, features, idx=0, top_n=n)) == n

    def test_chaves_obrigatorias(self, shap_vals, features):
        for factor in explain_record(shap_vals, features, idx=0):
            assert {"feature", "shap_value", "group"} <= factor.keys()

    def test_feature_e_string(self, shap_vals, features):
        for factor in explain_record(shap_vals, features, idx=0):
            assert isinstance(factor["feature"], str)

    def test_shap_value_e_float(self, shap_vals, features):
        for factor in explain_record(shap_vals, features, idx=0):
            assert isinstance(factor["shap_value"], float)

    def test_group_e_valido(self, shap_vals, features):
        valid = set(FEATURE_GROUPS.keys())
        for factor in explain_record(shap_vals, features, idx=0):
            assert factor["group"] in valid, f"Grupo invalido: {factor['group']}"

    def test_ordenado_por_importancia_decrescente(self, shap_vals, features):
        result = explain_record(shap_vals, features, idx=0, top_n=8)
        abs_vals = [abs(f["shap_value"]) for f in result]
        assert abs_vals == sorted(abs_vals, reverse=True)


# ---------------------------------------------------------------------------
# Top features global
# ---------------------------------------------------------------------------

class TestTopFeaturesGlobal:
    def test_retorna_n_elementos(self, shap_vals, features):
        for n in (5, 10, 15):
            assert len(top_features_global(shap_vals, features, top_n=n)) == n

    def test_tipo_dos_elementos(self, shap_vals, features):
        for feat, imp in top_features_global(shap_vals, features):
            assert isinstance(feat, str)
            assert isinstance(imp, float)

    def test_importancias_decrescentes(self, shap_vals, features):
        imps = [imp for _, imp in top_features_global(shap_vals, features)]
        assert imps == sorted(imps, reverse=True)

    def test_features_pertencem_ao_modelo(self, shap_vals, features):
        feature_set = set(features)
        for feat, _ in top_features_global(shap_vals, features):
            assert feat in feature_set


# ---------------------------------------------------------------------------
# Consistencia SHAP x score
# ---------------------------------------------------------------------------

class TestConsistencia:
    def test_todas_faixas_representadas_na_amostra(self, y_pred):
        bands = {derive_faixa(float(p)) for p in y_pred}
        assert bands == {"baixo", "medio", "alto"}, f"Faixas ausentes: {bands}"

    def test_score_alto_tem_shap_sum_positiva(self, shap_vals, y_pred):
        high_mask = y_pred > 66
        assert high_mask.sum() > 0, "Nenhum registro de score alto na amostra"
        pct_positive = (shap_vals[high_mask].sum(axis=1) > 0).mean()
        assert pct_positive >= 0.90, f"Apenas {pct_positive:.0%} de alto com SHAP sum > 0"

    def test_score_baixo_tem_shap_sum_menor_que_alto(self, shap_vals, y_pred):
        low_mask = y_pred < 33
        high_mask = y_pred > 66
        if low_mask.sum() > 0 and high_mask.sum() > 0:
            low_mean = shap_vals[low_mask].sum(axis=1).mean()
            high_mean = shap_vals[high_mask].sum(axis=1).mean()
            assert low_mean < high_mean, "Scores baixos tem SHAP sum media maior que scores altos"


# ---------------------------------------------------------------------------
# Artefatos salvos
# ---------------------------------------------------------------------------

class TestArtefatos:
    def test_save_shap_values_cria_arquivo(self, shap_npy_path):
        assert os.path.isfile(shap_npy_path), f"Arquivo nao criado: {shap_npy_path}"

    def test_shap_npy_carrega_com_shape_correto(self, shap_npy_path, shap_vals):
        loaded = np.load(shap_npy_path)
        assert loaded.shape == shap_vals.shape

    def test_save_plots_retorna_lista_nao_vazia(self, saved_plots_list):
        assert isinstance(saved_plots_list, list)
        assert len(saved_plots_list) >= 3

    def test_todos_png_existem(self, saved_plots_list):
        for path in saved_plots_list:
            assert os.path.isfile(path), f"PNG nao encontrado: {path}"

    def test_beeswarm_png_salvo(self, saved_plots_list):
        names = [os.path.basename(p) for p in saved_plots_list]
        assert "shap_summary_beeswarm.png" in names

    def test_bar_png_salvo(self, saved_plots_list):
        names = [os.path.basename(p) for p in saved_plots_list]
        assert "shap_summary_bar.png" in names

    def test_group_contributions_png_salvo(self, saved_plots_list):
        names = [os.path.basename(p) for p in saved_plots_list]
        assert "shap_group_contributions.png" in names

    def test_waterfall_plots_salvos(self, saved_plots_list):
        names = [os.path.basename(p) for p in saved_plots_list]
        waterfall_count = sum(1 for n in names if "waterfall" in n)
        assert waterfall_count >= 1, "Nenhum waterfall plot gerado"