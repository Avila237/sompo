"""SafeField - Testes automatizados do dataset simulado. Execucao: pytest tests/test_dataset.py -v"""
import os, pytest, pandas as pd
DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dataset_safefield.parquet")
COLUNAS_ESPERADAS = ["equipamento_id","timestamp","temperatura_ar","precipitacao_mm","umidade_solo","velocidade_vento","condicao_clima","latitude","longitude","tipo_solo","distancia_agua_m","declividade","tipo_operacao","velocidade_kmh","vibracao_g","temperatura_motor","horas_operacao","horario_operacao","tipo_equipamento","idade_equipamento","historico_sinistros","tem_iot","risco_score","faixa_risco"]
@pytest.fixture(scope="session")
def df(): return pd.read_parquet(DATASET_PATH)

class TestDatasetSchema:
    def test_arquivo_existe(self):
        """Dataset parquet existe no path esperado"""
        assert os.path.exists(DATASET_PATH)
    def test_shape(self, df):
        """Dataset tem 5000 registros e 24 colunas"""
        assert df.shape == (5000, 24)
    def test_colunas_esperadas(self, df):
        """Todas as 24 colunas estao presentes com os nomes corretos e na ordem correta"""
        assert list(df.columns) == COLUNAS_ESPERADAS
    def test_tipos_numericos(self, df):
        """Colunas numericas tem tipos float/int corretos"""
        for c in ["temperatura_ar","precipitacao_mm","umidade_solo","velocidade_vento","latitude","longitude","distancia_agua_m","declividade","velocidade_kmh","vibracao_g","temperatura_motor","horas_operacao","risco_score"]:
            assert pd.api.types.is_float_dtype(df[c]), c
        for c in ["horario_operacao","idade_equipamento","historico_sinistros"]:
            assert pd.api.types.is_integer_dtype(df[c]), c
    def test_tipos_categoricos(self, df):
        """Colunas categoricas sao strings (object ou category)"""
        for col in ["equipamento_id","condicao_clima","tipo_solo","tipo_operacao","tipo_equipamento","faixa_risco"]:
            d = df[col].dtype
            assert pd.api.types.is_string_dtype(d) or isinstance(d, pd.CategoricalDtype), col
    def test_tipo_boolean(self, df):
        """tem_iot e boolean"""
        assert df["tem_iot"].dtype == bool
    def test_tipo_timestamp(self, df):
        """timestamp e datetime"""
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    def test_sem_duplicatas_completas(self, df):
        """Nao ha linhas 100% duplicadas"""
        assert df.duplicated().sum() == 0

class TestRangesNumericos:
    def test_temperatura_ar_range(self, df):
        """temperatura_ar entre -5 e 45"""
        assert df["temperatura_ar"].min() >= -5.0 and df["temperatura_ar"].max() <= 45.0
    def test_precipitacao_mm_range(self, df):
        """precipitacao_mm entre 0 e 120"""
        assert df["precipitacao_mm"].min() >= 0.0 and df["precipitacao_mm"].max() <= 120.0
    def test_umidade_solo_range(self, df):
        """umidade_solo entre 5 e 95"""
        assert df["umidade_solo"].min() >= 5.0 and df["umidade_solo"].max() <= 95.0
    def test_velocidade_vento_range(self, df):
        """velocidade_vento entre 0 e 80"""
        assert df["velocidade_vento"].min() >= 0.0 and df["velocidade_vento"].max() <= 80.0
    def test_latitude_range(self, df):
        """latitude entre -33.75 e -2.50 (limites do Brasil)"""
        assert df["latitude"].min() >= -33.75 and df["latitude"].max() <= -2.50
    def test_longitude_range(self, df):
        """longitude entre -73.99 e -34.79 (limites do Brasil)"""
        assert df["longitude"].min() >= -73.99 and df["longitude"].max() <= -34.79
    def test_distancia_agua_range(self, df):
        """distancia_agua_m entre 10 e 5000"""
        assert df["distancia_agua_m"].min() >= 10.0 and df["distancia_agua_m"].max() <= 5000.0
    def test_declividade_range(self, df):
        """declividade entre 0 e 45"""
        assert df["declividade"].min() >= 0.0 and df["declividade"].max() <= 45.0
    def test_velocidade_kmh_range(self, df):
        """velocidade_kmh entre 0 e 40"""
        assert df["velocidade_kmh"].min() >= 0.0 and df["velocidade_kmh"].max() <= 40.0
    def test_vibracao_g_range(self, df):
        """vibracao_g no range 0.1 a 4.0 (onde nao e null)"""
        s = df["vibracao_g"].dropna()
        assert s.min() >= 0.1 and s.max() <= 4.0
    def test_temperatura_motor_range(self, df):
        """temperatura_motor entre 50 e 120 (onde nao e null)"""
        s = df["temperatura_motor"].dropna()
        assert s.min() >= 50.0 and s.max() <= 120.0
    def test_horas_operacao_range(self, df):
        """horas_operacao entre 0 e 24"""
        assert df["horas_operacao"].min() >= 0.0 and df["horas_operacao"].max() <= 24.0
    def test_horario_operacao_range(self, df):
        """horario_operacao entre 0 e 23 (inteiro)"""
        assert df["horario_operacao"].min() >= 0 and df["horario_operacao"].max() <= 23
    def test_idade_equipamento_range(self, df):
        """idade_equipamento entre 0 e 25"""
        assert df["idade_equipamento"].min() >= 0 and df["idade_equipamento"].max() <= 25
    def test_historico_sinistros_range(self, df):
        """historico_sinistros entre 0 e 10"""
        assert df["historico_sinistros"].min() >= 0 and df["historico_sinistros"].max() <= 10
    def test_risco_score_range(self, df):
        """risco_score entre 0 e 100"""
        assert df["risco_score"].min() >= 0.0 and df["risco_score"].max() <= 100.0

class TestValoresCategoricos:
    def test_tipo_equipamento_valores(self, df):
        """tipo_equipamento e um de: colheitadeira, trator, implemento"""
        assert set(df["tipo_equipamento"].astype(str).unique()) <= {"colheitadeira", "trator", "implemento"}
    def test_tipo_operacao_valores(self, df):
        """tipo_operacao e um de: colheita, plantio, pulverizacao, transporte, parado"""
        assert set(df["tipo_operacao"].astype(str).unique()) <= {"colheita", "plantio", "pulverizacao", "transporte", "parado"}
    def test_tipo_solo_valores(self, df):
        """tipo_solo e um de: arenoso, argiloso, misto"""
        assert set(df["tipo_solo"].astype(str).unique()) <= {"arenoso", "argiloso", "misto"}
    def test_condicao_clima_valores(self, df):
        """condicao_clima e um de: ensolarado, nublado, chuvoso, tempestade"""
        assert set(df["condicao_clima"].astype(str).unique()) <= {"ensolarado", "nublado", "chuvoso", "tempestade"}
    def test_faixa_risco_valores(self, df):
        """faixa_risco e um de: baixo, medio, alto"""
        assert set(df["faixa_risco"].astype(str).unique()) <= {"baixo", "medio", "alto"}

class TestRegrasConsistencia:
    def test_regra1_sem_iot_temperatura_motor_null(self, df):
        """Equipamentos sem IoT (tem_iot=false) devem ter temperatura_motor null"""
        assert ((~df["tem_iot"]) & df["temperatura_motor"].notna()).sum() == 0
    def test_regra1_com_iot_temperatura_motor_preenchido(self, df):
        """Equipamentos com IoT devem ter temperatura_motor preenchido EXCETO implementos (Regra 10)"""
        mask = df["tem_iot"] & (df["tipo_equipamento"] != "implemento")
        assert (mask & df["temperatura_motor"].isna()).sum() == 0
    def test_regra1_vibracao_com_iot_range(self, df):
        """Com IoT: vibracao_g no range 0.1-4.0 (onde nao null)"""
        s = df.loc[df["tem_iot"], "vibracao_g"].dropna()
        assert s.min() >= 0.1 and s.max() <= 4.0
    def test_regra1_vibracao_sem_iot_range(self, df):
        """Sem IoT: vibracao_g no range 0.1-2.0 (onde nao null)"""
        s = df.loc[~df["tem_iot"], "vibracao_g"].dropna()
        assert s.min() >= 0.1 and s.max() <= 2.0
    def test_regra2_faixa_baixo(self, df):
        """Registros com risco_score <= 33 devem ter faixa_risco = baixo"""
        mask = df["risco_score"] <= 33.0
        assert (mask & (df["faixa_risco"].astype(str) != "baixo")).sum() == 0
    def test_regra2_faixa_medio(self, df):
        """Registros com risco_score entre 33.1 e 66 devem ter faixa_risco = medio"""
        mask = (df["risco_score"] > 33.0) & (df["risco_score"] <= 66.0)
        assert (mask & (df["faixa_risco"].astype(str) != "medio")).sum() == 0
    def test_regra2_faixa_alto(self, df):
        """Registros com risco_score > 66 devem ter faixa_risco = alto"""
        mask = df["risco_score"] > 66.0
        assert (mask & (df["faixa_risco"].astype(str) != "alto")).sum() == 0
    def test_regra4_parado_velocidade_zero(self, df):
        """Operacao parado deve ter velocidade_kmh = 0"""
        assert ((df["tipo_operacao"] == "parado") & (df["velocidade_kmh"] != 0.0)).sum() == 0
    def test_regra4_colheita_velocidade_range(self, df):
        """Operacao colheita deve ter velocidade_kmh entre 3 e 8"""
        s = df.loc[df["tipo_operacao"] == "colheita", "velocidade_kmh"]
        assert s.min() >= 3.0 and s.max() <= 8.0
    def test_regra4_plantio_velocidade_range(self, df):
        """Operacao plantio deve ter velocidade_kmh entre 3 e 8"""
        s = df.loc[df["tipo_operacao"] == "plantio", "velocidade_kmh"]
        assert s.min() >= 3.0 and s.max() <= 8.0
    def test_regra4_pulverizacao_velocidade_range(self, df):
        """Operacao pulverizacao deve ter velocidade_kmh entre 8 e 15"""
        s = df.loc[df["tipo_operacao"] == "pulverizacao", "velocidade_kmh"]
        assert s.min() >= 8.0 and s.max() <= 15.0
    def test_regra4_transporte_velocidade_range(self, df):
        """Operacao transporte deve ter velocidade_kmh entre 15 e 40"""
        s = df.loc[df["tipo_operacao"] == "transporte", "velocidade_kmh"]
        assert s.min() >= 15.0 and s.max() <= 40.0
    def test_regra5_sem_chuva_nao_tempestade(self, df):
        """precipitacao_mm <= 2 nao deve ter condicao_clima = tempestade"""
        assert ((df["precipitacao_mm"] <= 2.0) & (df["condicao_clima"] == "tempestade")).sum() == 0
    def test_regra5_chuva_forte_nao_ensolarado(self, df):
        """precipitacao_mm > 20 nao deve ter condicao_clima = ensolarado"""
        assert ((df["precipitacao_mm"] > 20.0) & (df["condicao_clima"] == "ensolarado")).sum() == 0
    def test_regra10_implemento_sem_temperatura_motor(self, df):
        """Implementos devem ter temperatura_motor null, mesmo com IoT"""
        assert ((df["tipo_equipamento"] == "implemento") & df["temperatura_motor"].notna()).sum() == 0

class TestDistribuicoes:
    def test_distribuicao_faixa_risco(self, df):
        """Distribuicao de faixas: ~40% baixo, ~35% medio, ~25% alto (margem +-8%)"""
        prop = df["faixa_risco"].astype(str).value_counts(normalize=True)
        pct_b, pct_m, pct_a = prop.get("baixo", 0), prop.get("medio", 0), prop.get("alto", 0)
        assert 0.32 <= pct_b <= 0.48, f"baixo: {pct_b:.1%} (esperado 32%-48%)"
        assert 0.27 <= pct_m <= 0.43, f"medio: {pct_m:.1%} (esperado 27%-43%)"
        assert 0.17 <= pct_a <= 0.33, f"alto: {pct_a:.1%} (esperado 17%-33%)"
    def test_distribuicao_tipo_equipamento(self, df):
        """Distribuicao: ~45% trator, ~35% colheitadeira, ~20% implemento (margem +-8%)"""
        prop = df["tipo_equipamento"].value_counts(normalize=True)
        assert 0.37 <= prop.get("trator", 0) <= 0.53, f"{prop.get(chr(116)+chr(114)+chr(97)+chr(116)+chr(111)+chr(114), 0):.1%}"
        assert 0.27 <= prop.get("colheitadeira", 0) <= 0.43, f"{prop.get(chr(99)+chr(111)+chr(108)+chr(104)+chr(101)+chr(105)+chr(116)+chr(97)+chr(100)+chr(101)+chr(105)+chr(114)+chr(97), 0):.1%}"
        assert 0.12 <= prop.get("implemento", 0) <= 0.28, f"{prop.get(chr(105)+chr(109)+chr(112)+chr(108)+chr(101)+chr(109)+chr(101)+chr(110)+chr(116)+chr(111), 0):.1%}"
    def test_distribuicao_tipo_operacao(self, df):
        """Distribuicao: colheita ~30%, transporte ~25%, plantio ~20%, pulverizacao ~15%, parado ~10% (margem +-8%)"""
        prop = df["tipo_operacao"].value_counts(normalize=True)
        assert 0.22 <= prop.get("colheita", 0) <= 0.38
        assert 0.17 <= prop.get("transporte", 0) <= 0.33
        assert 0.12 <= prop.get("plantio", 0) <= 0.28
        assert 0.07 <= prop.get("pulverizacao", 0) <= 0.23
        assert 0.02 <= prop.get("parado", 0) <= 0.18
    def test_distribuicao_tem_iot(self, df):
        """~30% com IoT, ~70% sem IoT (margem +-8%)"""
        pct = df["tem_iot"].mean()
        assert 0.22 <= pct <= 0.38, f"IoT: {pct:.1%} (esperado 22%-38%)"
    def test_equipamentos_unicos(self, df):
        """Deve haver ~200 equipamentos unicos (margem +-20)"""
        n = df["equipamento_id"].nunique()
        assert 180 <= n <= 220, f"Equipamentos unicos: {n} (esperado 180-220)"
    def test_media_avaliacoes_por_equipamento(self, df):
        """Media de ~25 avaliacoes por equipamento (margem +-10)"""
        m = df.groupby("equipamento_id").size().mean()
        assert 15 <= m <= 35, f"Media avaliacoes: {m:.1f} (esperado 15-35)"
