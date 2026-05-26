"""SafeField - Testes automatizados do dataset simulado. Execucao: pytest tests/test_dataset.py -v"""
import os, pytest, pandas as pd

DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dataset_safefield.parquet")

COLUNAS_ESPERADAS = [
    "equipamento_id", "timestamp",
    "temperatura_ar", "precipitacao_mm", "umidade_solo", "velocidade_vento", "condicao_clima",
    "latitude", "longitude", "tipo_solo", "distancia_agua_m", "declividade",
    "tipo_operacao", "velocidade_kmh", "vibracao_g", "temperatura_motor",
    "horas_operacao", "horario_operacao",
    "tipo_equipamento", "idade_equipamento", "historico_sinistros", "tem_iot",
    "modelo_equipamento", "categoria_manual",
    "operador_id", "pct_velocidade_acima_recomendada", "freq_eventos_bruscos",
    "pct_operacoes_noturnas", "score_operador_historico",
    "ultima_manutencao_dias", "ultima_manutencao_horas_op",
    "intervalo_manut_recomendado_dias", "intervalo_manut_recomendado_horas",
    "manutencao_atrasada", "atraso_manutencao_pct",
    "risco_score", "faixa_risco",
]

MODELOS_COLHEITADEIRA = {"John Deere S790", "Case IH A8810", "New Holland CR10.90"}
MODELOS_TRATOR = {"John Deere 7J195", "Massey Ferguson 7S.180", "New Holland T7.290"}
MODELOS_IMPLEMENTO = {"Jumil JM-1440", "Baldan BFNT-15", "Marchesan CAP-7"}
TODOS_MODELOS = MODELOS_COLHEITADEIRA | MODELOS_TRATOR | MODELOS_IMPLEMENTO

CATEGORIAS_MANUAL = {
    "colheitadeira_operacao", "colheitadeira_manutencao",
    "trator_operacao", "trator_manutencao",
    "implemento_operacao", "implemento_manutencao",
}


@pytest.fixture(scope="session")
def df():
    return pd.read_parquet(DATASET_PATH)


class TestDatasetSchema:
    def test_arquivo_existe(self):
        """Dataset parquet existe no path esperado"""
        assert os.path.exists(DATASET_PATH)

    def test_shape(self, df):
        """Dataset tem 5000 registros e 37 colunas"""
        assert df.shape == (5000, 37)

    def test_colunas_esperadas(self, df):
        """Todas as 37 colunas estao presentes com os nomes corretos e na ordem correta"""
        assert list(df.columns) == COLUNAS_ESPERADAS

    def test_tipos_numericos(self, df):
        """Colunas numericas tem tipos float/int corretos"""
        float_cols = [
            "temperatura_ar", "precipitacao_mm", "umidade_solo", "velocidade_vento",
            "latitude", "longitude", "distancia_agua_m", "declividade",
            "velocidade_kmh", "vibracao_g", "temperatura_motor", "horas_operacao",
            "risco_score",
            "pct_velocidade_acima_recomendada", "freq_eventos_bruscos",
            "pct_operacoes_noturnas", "score_operador_historico",
            "ultima_manutencao_horas_op", "atraso_manutencao_pct",
        ]
        int_cols = [
            "horario_operacao", "idade_equipamento", "historico_sinistros",
            "ultima_manutencao_dias", "intervalo_manut_recomendado_dias",
            "intervalo_manut_recomendado_horas",
        ]
        for c in float_cols:
            assert pd.api.types.is_float_dtype(df[c]), f"{c} should be float"
        for c in int_cols:
            assert pd.api.types.is_integer_dtype(df[c]), f"{c} should be int"

    def test_tipos_categoricos(self, df):
        """Colunas categoricas sao strings (object ou category)"""
        for col in [
            "equipamento_id", "condicao_clima", "tipo_solo", "tipo_operacao",
            "tipo_equipamento", "faixa_risco",
            "operador_id", "modelo_equipamento", "categoria_manual",
        ]:
            d = df[col].dtype
            assert pd.api.types.is_string_dtype(d) or isinstance(d, pd.CategoricalDtype), col

    def test_tipo_boolean(self, df):
        """tem_iot e manutencao_atrasada sao boolean"""
        assert df["tem_iot"].dtype == bool
        assert df["manutencao_atrasada"].dtype == bool

    def test_tipo_timestamp(self, df):
        """timestamp e datetime"""
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])

    def test_sem_duplicatas_completas(self, df):
        """Nao ha linhas 100% duplicadas"""
        assert df.duplicated().sum() == 0


class TestRangesNumericos:
    def test_temperatura_ar_range(self, df):
        assert df["temperatura_ar"].min() >= -5.0 and df["temperatura_ar"].max() <= 45.0

    def test_precipitacao_mm_range(self, df):
        assert df["precipitacao_mm"].min() >= 0.0 and df["precipitacao_mm"].max() <= 120.0

    def test_umidade_solo_range(self, df):
        assert df["umidade_solo"].min() >= 5.0 and df["umidade_solo"].max() <= 95.0

    def test_velocidade_vento_range(self, df):
        assert df["velocidade_vento"].min() >= 0.0 and df["velocidade_vento"].max() <= 80.0

    def test_latitude_range(self, df):
        assert df["latitude"].min() >= -33.75 and df["latitude"].max() <= -2.50

    def test_longitude_range(self, df):
        assert df["longitude"].min() >= -73.99 and df["longitude"].max() <= -34.79

    def test_distancia_agua_range(self, df):
        assert df["distancia_agua_m"].min() >= 10.0 and df["distancia_agua_m"].max() <= 5000.0

    def test_declividade_range(self, df):
        assert df["declividade"].min() >= 0.0 and df["declividade"].max() <= 45.0

    def test_velocidade_kmh_range(self, df):
        assert df["velocidade_kmh"].min() >= 0.0 and df["velocidade_kmh"].max() <= 40.0

    def test_vibracao_g_range(self, df):
        s = df["vibracao_g"].dropna()
        assert s.min() >= 0.1 and s.max() <= 4.0

    def test_temperatura_motor_range(self, df):
        s = df["temperatura_motor"].dropna()
        assert s.min() >= 50.0 and s.max() <= 120.0

    def test_horas_operacao_range(self, df):
        assert df["horas_operacao"].min() >= 0.0 and df["horas_operacao"].max() <= 24.0

    def test_horario_operacao_range(self, df):
        assert df["horario_operacao"].min() >= 0 and df["horario_operacao"].max() <= 23

    def test_idade_equipamento_range(self, df):
        assert df["idade_equipamento"].min() >= 0 and df["idade_equipamento"].max() <= 25

    def test_historico_sinistros_range(self, df):
        assert df["historico_sinistros"].min() >= 0 and df["historico_sinistros"].max() <= 10

    def test_risco_score_range(self, df):
        assert df["risco_score"].min() >= 0.0 and df["risco_score"].max() <= 100.0

    def test_pct_velocidade_acima_recomendada_range(self, df):
        """pct_velocidade_acima_recomendada entre 0 e 100"""
        assert df["pct_velocidade_acima_recomendada"].min() >= 0.0
        assert df["pct_velocidade_acima_recomendada"].max() <= 100.0

    def test_freq_eventos_bruscos_range(self, df):
        """freq_eventos_bruscos entre 0 e 20 eventos/hora"""
        assert df["freq_eventos_bruscos"].min() >= 0.0
        assert df["freq_eventos_bruscos"].max() <= 20.0

    def test_pct_operacoes_noturnas_range(self, df):
        """pct_operacoes_noturnas entre 0 e 100"""
        assert df["pct_operacoes_noturnas"].min() >= 0.0
        assert df["pct_operacoes_noturnas"].max() <= 100.0

    def test_score_operador_historico_range(self, df):
        """score_operador_historico entre 0 e 100"""
        assert df["score_operador_historico"].min() >= 0.0
        assert df["score_operador_historico"].max() <= 100.0

    def test_ultima_manutencao_dias_range(self, df):
        """ultima_manutencao_dias entre 0 e 365"""
        assert df["ultima_manutencao_dias"].min() >= 0
        assert df["ultima_manutencao_dias"].max() <= 365

    def test_ultima_manutencao_horas_op_range(self, df):
        """ultima_manutencao_horas_op entre 0 e 2000"""
        assert df["ultima_manutencao_horas_op"].min() >= 0.0
        assert df["ultima_manutencao_horas_op"].max() <= 2000.0

    def test_intervalo_manut_recomendado_dias_range(self, df):
        """intervalo_manut_recomendado_dias entre 90 e 365"""
        assert df["intervalo_manut_recomendado_dias"].min() >= 90
        assert df["intervalo_manut_recomendado_dias"].max() <= 365

    def test_intervalo_manut_recomendado_horas_range(self, df):
        """intervalo_manut_recomendado_horas entre 200 e 1500"""
        assert df["intervalo_manut_recomendado_horas"].min() >= 200
        assert df["intervalo_manut_recomendado_horas"].max() <= 1500

    def test_atraso_manutencao_pct_range(self, df):
        """atraso_manutencao_pct entre 0 e 3"""
        assert df["atraso_manutencao_pct"].min() >= 0.0
        assert df["atraso_manutencao_pct"].max() <= 3.0


class TestValoresCategoricos:
    def test_tipo_equipamento_valores(self, df):
        assert set(df["tipo_equipamento"].astype(str).unique()) <= {"colheitadeira", "trator", "implemento"}

    def test_tipo_operacao_valores(self, df):
        assert set(df["tipo_operacao"].astype(str).unique()) <= {"colheita", "plantio", "pulverizacao", "transporte", "parado"}

    def test_tipo_solo_valores(self, df):
        assert set(df["tipo_solo"].astype(str).unique()) <= {"arenoso", "argiloso", "misto"}

    def test_condicao_clima_valores(self, df):
        assert set(df["condicao_clima"].astype(str).unique()) <= {"ensolarado", "nublado", "chuvoso", "tempestade"}

    def test_faixa_risco_valores(self, df):
        assert set(df["faixa_risco"].astype(str).unique()) <= {"baixo", "medio", "alto"}

    def test_modelo_equipamento_valores(self, df):
        """modelo_equipamento pertence ao conjunto de modelos simulados definidos (Regra 15)"""
        assert set(df["modelo_equipamento"].unique()) <= TODOS_MODELOS

    def test_categoria_manual_valores(self, df):
        """categoria_manual pertence as 6 categorias validas de manuais tecnicos"""
        assert set(df["categoria_manual"].unique()) <= CATEGORIAS_MANUAL


class TestRegrasConsistencia:
    def test_regra1_sem_iot_temperatura_motor_null(self, df):
        assert ((~df["tem_iot"]) & df["temperatura_motor"].notna()).sum() == 0

    def test_regra1_com_iot_temperatura_motor_preenchido(self, df):
        """Equipamentos com IoT devem ter temperatura_motor preenchido EXCETO implementos (Regra 10)"""
        mask = df["tem_iot"] & (df["tipo_equipamento"] != "implemento")
        assert (mask & df["temperatura_motor"].isna()).sum() == 0

    def test_regra1_vibracao_com_iot_range(self, df):
        s = df.loc[df["tem_iot"], "vibracao_g"].dropna()
        assert s.min() >= 0.1 and s.max() <= 4.0

    def test_regra1_vibracao_sem_iot_range(self, df):
        s = df.loc[~df["tem_iot"], "vibracao_g"].dropna()
        assert s.min() >= 0.1 and s.max() <= 2.0

    def test_regra2_faixa_baixo(self, df):
        mask = df["risco_score"] <= 33.0
        assert (mask & (df["faixa_risco"].astype(str) != "baixo")).sum() == 0

    def test_regra2_faixa_medio(self, df):
        mask = (df["risco_score"] > 33.0) & (df["risco_score"] <= 66.0)
        assert (mask & (df["faixa_risco"].astype(str) != "medio")).sum() == 0

    def test_regra2_faixa_alto(self, df):
        mask = df["risco_score"] > 66.0
        assert (mask & (df["faixa_risco"].astype(str) != "alto")).sum() == 0

    def test_regra4_parado_velocidade_zero(self, df):
        assert ((df["tipo_operacao"] == "parado") & (df["velocidade_kmh"] != 0.0)).sum() == 0

    def test_regra4_colheita_velocidade_range(self, df):
        s = df.loc[df["tipo_operacao"] == "colheita", "velocidade_kmh"]
        assert s.min() >= 3.0 and s.max() <= 8.0

    def test_regra4_plantio_velocidade_range(self, df):
        s = df.loc[df["tipo_operacao"] == "plantio", "velocidade_kmh"]
        assert s.min() >= 3.0 and s.max() <= 8.0

    def test_regra4_pulverizacao_velocidade_range(self, df):
        s = df.loc[df["tipo_operacao"] == "pulverizacao", "velocidade_kmh"]
        assert s.min() >= 8.0 and s.max() <= 15.0

    def test_regra4_transporte_velocidade_range(self, df):
        s = df.loc[df["tipo_operacao"] == "transporte", "velocidade_kmh"]
        assert s.min() >= 15.0 and s.max() <= 40.0

    def test_regra5_sem_chuva_nao_tempestade(self, df):
        assert ((df["precipitacao_mm"] <= 2.0) & (df["condicao_clima"] == "tempestade")).sum() == 0

    def test_regra5_chuva_forte_nao_ensolarado(self, df):
        assert ((df["precipitacao_mm"] > 20.0) & (df["condicao_clima"] == "ensolarado")).sum() == 0

    def test_regra10_implemento_sem_temperatura_motor(self, df):
        assert ((df["tipo_equipamento"] == "implemento") & df["temperatura_motor"].notna()).sum() == 0

    def test_regra12_velhos_mais_atrasados_que_novos(self, df):
        """Equipamentos >10 anos tem taxa de manutencao_atrasada maior que <3 anos (Regra 12)"""
        taxa_velhos = df.loc[df["idade_equipamento"] > 10, "manutencao_atrasada"].mean()
        taxa_novos = df.loc[df["idade_equipamento"] < 3, "manutencao_atrasada"].mean()
        assert taxa_velhos > taxa_novos, f"velhos: {taxa_velhos:.1%}, novos: {taxa_novos:.1%}"

    def test_regra13_score_operador_consistente_por_id(self, df):
        """Variacao de score_operador_historico por operador_id e limitada (std<=10 por operador)"""
        max_std = df.groupby("operador_id")["score_operador_historico"].std().max()
        assert max_std <= 10, f"Desvio padrao maximo: {max_std:.2f} (esperado <=10)"

    def test_regra14_atraso_pct_e_derivado(self, df):
        """atraso_manutencao_pct = max(dias/int_dias, horas/int_horas) arredondado (Regra 14)"""
        recalc = (
            df["ultima_manutencao_dias"] / df["intervalo_manut_recomendado_dias"]
        ).combine(
            df["ultima_manutencao_horas_op"] / df["intervalo_manut_recomendado_horas"],
            max,
        ).round(3)
        diff = (df["atraso_manutencao_pct"] - recalc).abs()
        assert (diff < 0.01).all(), f"Maior divergencia: {diff.max():.4f}"

    def test_regra14_manutencao_atrasada_derivada_do_pct(self, df):
        """manutencao_atrasada e exatamente (atraso_manutencao_pct > 1.0), sem excecoes"""
        esperado = df["atraso_manutencao_pct"] > 1.0
        assert (df["manutencao_atrasada"] == esperado).all()

    def test_regra15_modelo_compativel_com_tipo(self, df):
        """modelo_equipamento corresponde ao tipo_equipamento (Regra 15)"""
        def tipo_esperado_do_modelo(modelo):
            if modelo in MODELOS_COLHEITADEIRA:
                return "colheitadeira"
            if modelo in MODELOS_TRATOR:
                return "trator"
            return "implemento"

        erros = df.apply(
            lambda r: tipo_esperado_do_modelo(r["modelo_equipamento"]) != r["tipo_equipamento"],
            axis=1,
        ).sum()
        assert erros == 0, f"{erros} registros com modelo incompativel com tipo"

    def test_regra16_ops_por_equipamento(self, df):
        """Cada equipamento tem entre 1 e 3 operadores distintos no dataset (Regra 16)"""
        ops_por_equip = df.groupby("equipamento_id")["operador_id"].nunique()
        assert ops_por_equip.min() >= 1
        assert ops_por_equip.max() <= 3, f"Max operadores/equip: {ops_por_equip.max()}"

    def test_regra16_equips_por_operador(self, df):
        """Cada operador opera no maximo 5 equipamentos distintos (tolerancia +1 para fallback)"""
        equips_por_op = df.groupby("operador_id")["equipamento_id"].nunique()
        assert equips_por_op.min() >= 1
        assert equips_por_op.max() <= 6, f"Max equips/operador: {equips_por_op.max()}"


class TestDistribuicoes:
    def test_distribuicao_faixa_risco(self, df):
        """Distribuicao de faixas: ~40% baixo, ~35% medio, ~25% alto (margem +-8%)"""
        prop = df["faixa_risco"].astype(str).value_counts(normalize=True)
        pct_b, pct_m, pct_a = prop.get("baixo", 0), prop.get("medio", 0), prop.get("alto", 0)
        assert 0.32 <= pct_b <= 0.48, f"baixo: {pct_b:.1%}"
        assert 0.27 <= pct_m <= 0.43, f"medio: {pct_m:.1%}"
        assert 0.17 <= pct_a <= 0.33, f"alto: {pct_a:.1%}"

    def test_distribuicao_tipo_equipamento(self, df):
        """Distribuicao: ~45% trator, ~35% colheitadeira, ~20% implemento (margem +-8%)"""
        prop = df["tipo_equipamento"].value_counts(normalize=True)
        assert 0.37 <= prop.get("trator", 0) <= 0.53
        assert 0.27 <= prop.get("colheitadeira", 0) <= 0.43
        assert 0.12 <= prop.get("implemento", 0) <= 0.28

    def test_distribuicao_tipo_operacao(self, df):
        """Distribuicao: colheita ~30%, transporte ~25%, plantio ~20%, pulverizacao ~15%, parado ~10%"""
        prop = df["tipo_operacao"].value_counts(normalize=True)
        assert 0.22 <= prop.get("colheita", 0) <= 0.38
        assert 0.17 <= prop.get("transporte", 0) <= 0.33
        assert 0.12 <= prop.get("plantio", 0) <= 0.28
        assert 0.07 <= prop.get("pulverizacao", 0) <= 0.23
        assert 0.02 <= prop.get("parado", 0) <= 0.18

    def test_distribuicao_tem_iot(self, df):
        """~30% com IoT, ~70% sem IoT (margem +-8%)"""
        pct = df["tem_iot"].mean()
        assert 0.22 <= pct <= 0.38, f"IoT: {pct:.1%}"

    def test_equipamentos_unicos(self, df):
        """Deve haver ~200 equipamentos unicos (margem +-20)"""
        n = df["equipamento_id"].nunique()
        assert 180 <= n <= 220, f"Equipamentos unicos: {n}"

    def test_media_avaliacoes_por_equipamento(self, df):
        """Media de ~25 avaliacoes por equipamento (margem +-10)"""
        m = df.groupby("equipamento_id").size().mean()
        assert 15 <= m <= 35, f"Media avaliacoes: {m:.1f}"

    def test_operadores_unicos(self, df):
        """Deve haver ~80 operadores unicos (margem +-10)"""
        n = df["operador_id"].nunique()
        assert 70 <= n <= 90, f"Operadores unicos: {n} (esperado 70-90)"

    def test_manutencao_atrasada_distribuicao(self, df):
        """Alguma proporcao de manutencoes atrasadas deve existir (10%-60%)"""
        pct = df["manutencao_atrasada"].mean()
        assert 0.10 <= pct <= 0.60, f"manutencao_atrasada: {pct:.1%}"