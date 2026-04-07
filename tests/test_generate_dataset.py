# SafeField - Testes do script de geracao. Execucao: pytest tests/test_generate_dataset.py -v
import sys, os, pytest, numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scripts.generate_dataset import (
    generate_equipamentos, generate_ambientais, generate_geograficos,
    generate_operacionais, apply_consistency_rules, calculate_risk_score,
    N_EQUIPAMENTOS, N_REGISTROS
)


def _gerar_dataset(seed):
    np.random.seed(seed)
    equipamentos = generate_equipamentos(N_EQUIPAMENTOS)
    equip_idx = np.random.choice(N_EQUIPAMENTOS, size=N_REGISTROS, replace=True)
    equip_records = equipamentos.iloc[equip_idx].reset_index(drop=True)
    ambientais = generate_ambientais(N_REGISTROS)
    geograficos = generate_geograficos(N_REGISTROS)
    operacionais = generate_operacionais(N_REGISTROS, equipamentos, equip_idx)
    df = pd.concat([
        equip_records[['equipamento_id']],
        operacionais[['timestamp']],
        ambientais,
        geograficos,
        operacionais[['tipo_operacao','velocidade_kmh','horas_operacao','horario_operacao']],
        equip_records[['tipo_equipamento','idade_equipamento','historico_sinistros','tem_iot']],
    ], axis=1)
    df = apply_consistency_rules(df)
    df = calculate_risk_score(df)
    return df


def _make_df(record):
    cols = [
        'precipitacao_mm','umidade_solo','velocidade_vento','distancia_agua_m',
        'declividade','velocidade_kmh','horas_operacao','horario_operacao',
        'idade_equipamento','historico_sinistros','vibracao_g',
        'tipo_solo','tipo_operacao','tipo_equipamento','tem_iot'
    ]
    rows = record if isinstance(record, list) else [record]
    return pd.DataFrame(rows, columns=cols)


@pytest.fixture(scope='session')
def df():
    return pd.read_parquet(os.path.join(os.path.dirname(__file__), '..', 'data', 'dataset_safefield.parquet'))


@pytest.fixture(scope='session')
def equipamentos():
    np.random.seed(42)
    return generate_equipamentos(N_EQUIPAMENTOS)


@pytest.fixture
def reg_baixo():
    return {
        'precipitacao_mm': 0.0, 'umidade_solo': 10.0, 'velocidade_vento': 5.0,
        'distancia_agua_m': 3000.0, 'declividade': 2.0, 'velocidade_kmh': 0.0,
        'vibracao_g': 0.2, 'horas_operacao': 1.0, 'horario_operacao': 10,
        'idade_equipamento': 1, 'historico_sinistros': 0,
        'tipo_solo': 'arenoso', 'tipo_operacao': 'parado',
        'tipo_equipamento': 'trator', 'tem_iot': False
    }


@pytest.fixture
def reg_alto():
    return {
        'precipitacao_mm': 80.0, 'umidade_solo': 85.0, 'velocidade_vento': 50.0,
        'distancia_agua_m': 50.0, 'declividade': 25.0, 'velocidade_kmh': 35.0,
        'vibracao_g': 3.5, 'horas_operacao': 14.0, 'horario_operacao': 22,
        'idade_equipamento': 20, 'historico_sinistros': 5,
        'tipo_solo': 'argiloso', 'tipo_operacao': 'transporte',
        'tipo_equipamento': 'colheitadeira', 'tem_iot': True
    }


class TestReprodutibilidade:

    def test_seed_42_gera_mesmo_resultado(self):
        'Rodar o pipeline duas vezes com seed 42 gera datasets identicos'
        df1 = _gerar_dataset(42)
        df2 = _gerar_dataset(42)
        pd.testing.assert_frame_equal(df1.reset_index(drop=True), df2.reset_index(drop=True))

    def test_seed_diferente_gera_resultado_diferente(self):
        'Rodar com seed diferente gera dataset diferente'
        df1 = _gerar_dataset(42)
        df2 = _gerar_dataset(99)
        with pytest.raises(AssertionError):
            pd.testing.assert_frame_equal(df1[['risco_score']], df2[['risco_score']])


class TestGenerateEquipamentos:

    def test_quantidade_equipamentos(self):
        '200 equipamentos gerados com o parametro padrao'
        np.random.seed(42)
        eq = generate_equipamentos(200)
        assert len(eq) == 200

    def test_ids_unicos(self, equipamentos):
        'Todos os equipamento_id sao unicos'
        assert equipamentos['equipamento_id'].nunique() == N_EQUIPAMENTOS

    def test_formato_id(self, equipamentos):
        'IDs seguem o formato EQ-XXXX'
        assert equipamentos['equipamento_id'].str.match(r'^EQ-\d{4}$').all()

    def test_distribuicao_tipo_equipamento(self, equipamentos):
        '~45% trator, ~35% colheitadeira, ~20% implemento (margem +-8%)'
        prop = equipamentos['tipo_equipamento'].value_counts(normalize=True)
        assert 0.37 <= prop.get('trator', 0) <= 0.53
        assert 0.27 <= prop.get('colheitadeira', 0) <= 0.43
        assert 0.12 <= prop.get('implemento', 0) <= 0.28

    def test_distribuicao_tem_iot(self, equipamentos):
        '~30% com IoT (margem +-8%)'
        pct = equipamentos['tem_iot'].mean()
        assert 0.22 <= pct <= 0.38

    def test_sinistros_correlaciona_idade(self, equipamentos):
        'Equipamentos mais velhos (>10 anos) tem media de sinistros maior que novos (<3 anos)'
        media_velhos = equipamentos.loc[equipamentos['idade_equipamento'] > 10, 'historico_sinistros'].mean()
        media_novos = equipamentos.loc[equipamentos['idade_equipamento'] < 3, 'historico_sinistros'].mean()
        assert media_velhos > media_novos

    def test_sinistros_dentro_range(self, equipamentos):
        'historico_sinistros entre 0 e 10'
        assert equipamentos['historico_sinistros'].min() >= 0
        assert equipamentos['historico_sinistros'].max() <= 10

    def test_idade_dentro_range(self, equipamentos):
        'idade_equipamento entre 0 e 25'
        assert equipamentos['idade_equipamento'].min() >= 0
        assert equipamentos['idade_equipamento'].max() <= 25


class TestGenerateAmbientais:

    def test_quantidade_registros(self):
        'Gera o numero correto de registros'
        np.random.seed(42)
        amb = generate_ambientais(N_REGISTROS)
        assert len(amb) == N_REGISTROS

    def test_clima_consistente_com_precipitacao_baixa(self):
        'precipitacao <= 2mm nao gera tempestade'
        np.random.seed(42)
        amb = generate_ambientais(N_REGISTROS)
        assert ((amb['precipitacao_mm'] <= 2.0) & (amb['condicao_clima'] == 'tempestade')).sum() == 0

    def test_clima_consistente_com_precipitacao_alta(self):
        'precipitacao > 20mm nao gera ensolarado'
        np.random.seed(42)
        amb = generate_ambientais(N_REGISTROS)
        assert ((amb['precipitacao_mm'] > 20.0) & (amb['condicao_clima'] == 'ensolarado')).sum() == 0

    def test_precipitacao_distribuicao_realista(self):
        'Maioria dos registros tem precipitacao baixa (mediana < 30mm)'
        np.random.seed(42)
        amb = generate_ambientais(N_REGISTROS)
        assert amb['precipitacao_mm'].median() < 30.0


class TestGenerateGeograficos:

    def test_coordenadas_dentro_brasil(self):
        'Latitude e longitude dentro dos limites do Brasil'
        np.random.seed(42)
        geo = generate_geograficos(N_REGISTROS)
        assert geo['latitude'].min() >= -33.75 and geo['latitude'].max() <= -2.50
        assert geo['longitude'].min() >= -73.99 and geo['longitude'].max() <= -34.79

    def test_distribuicao_tipo_solo(self):
        '~40% argiloso, ~35% misto, ~25% arenoso (margem +-8%)'
        np.random.seed(42)
        geo = generate_geograficos(N_REGISTROS)
        prop = pd.Series(geo['tipo_solo']).value_counts(normalize=True)
        assert 0.32 <= prop.get('argiloso', 0) <= 0.48
        assert 0.27 <= prop.get('misto', 0) <= 0.43
        assert 0.17 <= prop.get('arenoso', 0) <= 0.33

    def test_distancia_agua_positiva(self):
        'distancia_agua_m sempre > 0'
        np.random.seed(42)
        geo = generate_geograficos(N_REGISTROS)
        assert (geo['distancia_agua_m'] > 0).all()


class TestGenerateOperacionais:

    @pytest.fixture(scope='class')
    def op(self):
        np.random.seed(42)
        eq = generate_equipamentos(N_EQUIPAMENTOS)
        equip_idx = np.random.choice(N_EQUIPAMENTOS, size=N_REGISTROS, replace=True)
        return generate_operacionais(N_REGISTROS, eq, equip_idx)

    def test_velocidade_parado_zero(self, op):
        'Operacao parado sempre tem velocidade 0'
        assert ((op['tipo_operacao'] == 'parado') & (op['velocidade_kmh'] != 0.0)).sum() == 0

    def test_velocidade_colheita_range(self, op):
        'Colheita: velocidade entre 3-8 km/h'
        s = op.loc[op['tipo_operacao'] == 'colheita', 'velocidade_kmh']
        assert s.min() >= 3.0 and s.max() <= 8.0

    def test_velocidade_transporte_range(self, op):
        'Transporte: velocidade entre 15-40 km/h'
        s = op.loc[op['tipo_operacao'] == 'transporte', 'velocidade_kmh']
        assert s.min() >= 15.0 and s.max() <= 40.0

    def test_distribuicao_operacoes(self, op):
        'Distribuicao segue os percentuais definidos (margem +-8%)'
        prop = op['tipo_operacao'].value_counts(normalize=True)
        assert 0.22 <= prop.get('colheita', 0) <= 0.38
        assert 0.17 <= prop.get('transporte', 0) <= 0.33
        assert 0.12 <= prop.get('plantio', 0) <= 0.28
        assert 0.07 <= prop.get('pulverizacao', 0) <= 0.23
        assert 0.02 <= prop.get('parado', 0) <= 0.18

    def test_horas_operacao_correlaciona_tipo(self, op):
        'Colheita/transporte tem media de horas maior que parado'
        media_colheita = op.loc[op['tipo_operacao'] == 'colheita', 'horas_operacao'].mean()
        media_transporte = op.loc[op['tipo_operacao'] == 'transporte', 'horas_operacao'].mean()
        media_parado = op.loc[op['tipo_operacao'] == 'parado', 'horas_operacao'].mean()
        assert media_colheita > media_parado
        assert media_transporte > media_parado


class TestApplyConsistencyRules:

    @pytest.fixture(scope='class')
    def df_full(self):
        np.random.seed(42)
        eq = generate_equipamentos(N_EQUIPAMENTOS)
        equip_idx = np.random.choice(N_EQUIPAMENTOS, size=N_REGISTROS, replace=True)
        equip_records = eq.iloc[equip_idx].reset_index(drop=True)
        amb = generate_ambientais(N_REGISTROS)
        geo = generate_geograficos(N_REGISTROS)
        op = generate_operacionais(N_REGISTROS, eq, equip_idx)
        base = pd.concat([
            equip_records[['equipamento_id']],
            op[['timestamp']],
            amb,
            geo,
            op[['tipo_operacao','velocidade_kmh','horas_operacao','horario_operacao']],
            equip_records[['tipo_equipamento','idade_equipamento','historico_sinistros','tem_iot']],
        ], axis=1)
        return apply_consistency_rules(base)

    def test_umidade_solo_correlaciona_precipitacao(self, df_full):
        'Registros com alta precipitacao (>50mm) tem umidade media maior que baixa precipitacao (<10mm)'
        alta = df_full.loc[df_full['precipitacao_mm'] > 50, 'umidade_solo'].mean()
        baixa = df_full.loc[df_full['precipitacao_mm'] < 10, 'umidade_solo'].mean()
        assert alta > baixa

    def test_umidade_solo_fator_argiloso(self, df_full):
        'Para mesma faixa de precipitacao, solo argiloso tem umidade media maior que arenoso'
        faixa = (df_full['precipitacao_mm'] >= 10) & (df_full['precipitacao_mm'] <= 30)
        arg = df_full.loc[faixa & (df_full['tipo_solo'] == 'argiloso'), 'umidade_solo'].mean()
        are = df_full.loc[faixa & (df_full['tipo_solo'] == 'arenoso'), 'umidade_solo'].mean()
        assert arg > are

    def test_vibracao_com_iot_range_maior(self, df_full):
        'Com IoT: vibracao_g pode chegar a 4.0. Sem IoT: limitado a 2.0'
        max_iot = df_full.loc[df_full['tem_iot'], 'vibracao_g'].dropna().max()
        max_sem = df_full.loc[~df_full['tem_iot'], 'vibracao_g'].dropna().max()
        assert max_iot > 2.0
        assert max_sem <= 2.0

    def test_temperatura_motor_correlaciona_horas(self, df_full):
        'Registros com mais horas de operacao tem temperatura_motor media maior'
        alta_horas = df_full.loc[df_full['horas_operacao'] > 15, 'temperatura_motor'].dropna().mean()
        baixa_horas = df_full.loc[df_full['horas_operacao'] < 3, 'temperatura_motor'].dropna().mean()
        assert alta_horas > baixa_horas

    def test_implemento_sem_temperatura(self, df_full):
        'Implementos nunca tem temperatura_motor preenchido'
        assert ((df_full['tipo_equipamento'] == 'implemento') & df_full['temperatura_motor'].notna()).sum() == 0

    def test_vibracao_correlaciona_operacao(self, df_full):
        'Colheita tem vibracao media maior que parado'
        media_colheita = df_full.loc[df_full['tipo_operacao'] == 'colheita', 'vibracao_g'].dropna().mean()
        media_parado = df_full.loc[df_full['tipo_operacao'] == 'parado', 'vibracao_g'].dropna().mean()
        assert media_colheita > media_parado


class TestCalculateRiskScore:

    @pytest.fixture(scope='class')
    def df_scored(self):
        np.random.seed(42)
        eq = generate_equipamentos(N_EQUIPAMENTOS)
        equip_idx = np.random.choice(N_EQUIPAMENTOS, size=N_REGISTROS, replace=True)
        equip_records = eq.iloc[equip_idx].reset_index(drop=True)
        amb = generate_ambientais(N_REGISTROS)
        geo = generate_geograficos(N_REGISTROS)
        op = generate_operacionais(N_REGISTROS, eq, equip_idx)
        base = pd.concat([
            equip_records[['equipamento_id']],
            op[['timestamp']],
            amb,
            geo,
            op[['tipo_operacao','velocidade_kmh','horas_operacao','horario_operacao']],
            equip_records[['tipo_equipamento','idade_equipamento','historico_sinistros','tem_iot']],
        ], axis=1)
        base = apply_consistency_rules(base)
        return calculate_risk_score(base)

    def test_score_entre_0_e_100(self, df_scored):
        'Todos os scores estao no range [0, 100]'
        assert df_scored['risco_score'].min() >= 0.0
        assert df_scored['risco_score'].max() <= 100.0

    def test_score_arredondado_uma_casa(self, df_scored):
        'Todos os scores tem no maximo 1 casa decimal'
        decimais = df_scored['risco_score'].apply(lambda x: len(str(x).split(chr(46))[1]) if chr(46) in str(x) else 0)
        assert (decimais <= 1).all()

    def test_faixa_derivada_corretamente(self, df_scored):
        'Faixa corresponde ao score: <=33 baixo, <=66 medio, >66 alto'
        faixa = df_scored['faixa_risco'].astype(str)
        assert ((df_scored['risco_score'] <= 33.0) & (faixa != 'baixo')).sum() == 0
        assert (((df_scored['risco_score'] > 33.0) & (df_scored['risco_score'] <= 66.0)) & (faixa != 'medio')).sum() == 0
        assert ((df_scored['risco_score'] > 66.0) & (faixa != 'alto')).sum() == 0

    def test_cenario_baixo_risco(self, reg_baixo):
        'Cenario seguro gera score baixo (< 33)'
        np.random.seed(0)
        df_out = calculate_risk_score(_make_df(reg_baixo))
        score = df_out['risco_score'].iloc[0]
        assert score < 33.0, 'Score esperado < 33, obtido: ' + str(score)

    def test_cenario_alto_risco(self, reg_alto):
        'Cenario perigoso gera score alto (> 66)'
        np.random.seed(0)
        df_out = calculate_risk_score(_make_df(reg_alto))
        score = df_out['risco_score'].iloc[0]
        assert score > 66.0, 'Score esperado > 66, obtido: ' + str(score)

    def test_interacao_chuva_solo_argiloso(self):
        'Chuva >30mm + solo argiloso gera score maior que chuva >30mm + solo arenoso'
        base = {
            'precipitacao_mm': 50.0, 'umidade_solo': 40.0, 'velocidade_vento': 10.0,
            'distancia_agua_m': 1000.0, 'declividade': 5.0, 'velocidade_kmh': 5.0,
            'vibracao_g': 0.5, 'horas_operacao': 3.0, 'horario_operacao': 10,
            'idade_equipamento': 5, 'historico_sinistros': 1,
            'tipo_operacao': 'colheita', 'tipo_equipamento': 'trator', 'tem_iot': False
        }
        arg = dict(base); arg['tipo_solo'] = 'argiloso'
        are = dict(base); are['tipo_solo'] = 'arenoso'
        np.random.seed(7); s_arg = calculate_risk_score(_make_df(arg))['risco_score'].iloc[0]
        np.random.seed(7); s_are = calculate_risk_score(_make_df(are))['risco_score'].iloc[0]
        assert s_arg > s_are

    def test_interacao_noturno_velocidade(self):
        'Noturno + velocidade >15km/h gera score maior que diurno + mesma velocidade'
        base = {
            'precipitacao_mm': 5.0, 'umidade_solo': 20.0, 'velocidade_vento': 10.0,
            'distancia_agua_m': 1000.0, 'declividade': 5.0, 'velocidade_kmh': 20.0,
            'vibracao_g': 0.8, 'horas_operacao': 5.0,
            'idade_equipamento': 5, 'historico_sinistros': 1,
            'tipo_solo': 'misto', 'tipo_operacao': 'transporte',
            'tipo_equipamento': 'trator', 'tem_iot': False
        }
        noturno = dict(base); noturno['horario_operacao'] = 22
        diurno = dict(base); diurno['horario_operacao'] = 10
        np.random.seed(7); s_noturno = calculate_risk_score(_make_df(noturno))['risco_score'].iloc[0]
        np.random.seed(7); s_diurno = calculate_risk_score(_make_df(diurno))['risco_score'].iloc[0]
        assert s_noturno > s_diurno

    def test_interacao_agua_chuva(self):
        'Perto de agua (<200m) + chuva >25mm gera score maior que longe de agua + mesma chuva'
        base = {
            'precipitacao_mm': 40.0, 'umidade_solo': 50.0, 'velocidade_vento': 15.0,
            'declividade': 5.0, 'velocidade_kmh': 5.0, 'vibracao_g': 0.5,
            'horas_operacao': 3.0, 'horario_operacao': 10,
            'idade_equipamento': 5, 'historico_sinistros': 1,
            'tipo_solo': 'misto', 'tipo_operacao': 'colheita',
            'tipo_equipamento': 'trator', 'tem_iot': False
        }
        perto = dict(base); perto['distancia_agua_m'] = 100.0
        longe = dict(base); longe['distancia_agua_m'] = 2000.0
        np.random.seed(7); s_perto = calculate_risk_score(_make_df(perto))['risco_score'].iloc[0]
        np.random.seed(7); s_longe = calculate_risk_score(_make_df(longe))['risco_score'].iloc[0]
        assert s_perto > s_longe

    def test_interacao_equipamento_velho_vibracao(self):
        'Idade >10 + vibracao >2.0 gera score maior que idade <5 + mesma vibracao'
        base = {
            'precipitacao_mm': 5.0, 'umidade_solo': 20.0, 'velocidade_vento': 10.0,
            'distancia_agua_m': 1000.0, 'declividade': 5.0, 'velocidade_kmh': 5.0,
            'vibracao_g': 2.5, 'horas_operacao': 5.0, 'horario_operacao': 10,
            'tipo_solo': 'misto', 'tipo_operacao': 'colheita',
            'tipo_equipamento': 'trator', 'tem_iot': True, 'historico_sinistros': 0
        }
        velho = dict(base); velho['idade_equipamento'] = 15
        novo = dict(base); novo['idade_equipamento'] = 3
        np.random.seed(7); s_velho = calculate_risk_score(_make_df(velho))['risco_score'].iloc[0]
        np.random.seed(7); s_novo = calculate_risk_score(_make_df(novo))['risco_score'].iloc[0]
        assert s_velho > s_novo

    def test_interacao_transporte_declividade(self):
        'Transporte >25km/h + declividade >10% gera score maior que mesma velocidade em terreno plano'
        base = {
            'precipitacao_mm': 5.0, 'umidade_solo': 20.0, 'velocidade_vento': 10.0,
            'distancia_agua_m': 1000.0, 'velocidade_kmh': 30.0,
            'vibracao_g': 1.0, 'horas_operacao': 5.0, 'horario_operacao': 10,
            'idade_equipamento': 5, 'historico_sinistros': 1,
            'tipo_solo': 'misto', 'tipo_operacao': 'transporte',
            'tipo_equipamento': 'trator', 'tem_iot': False
        }
        inclinado = dict(base); inclinado['declividade'] = 20.0
        plano = dict(base); plano['declividade'] = 2.0
        np.random.seed(7); s_inc = calculate_risk_score(_make_df(inclinado))['risco_score'].iloc[0]
        np.random.seed(7); s_pla = calculate_risk_score(_make_df(plano))['risco_score'].iloc[0]
        assert s_inc > s_pla

    def test_ruido_gaussiano_presente(self):
        'Dois registros com features identicas mas seeds diferentes geram scores ligeiramente diferentes'
        reg = {
            'precipitacao_mm': 15.0, 'umidade_solo': 30.0, 'velocidade_vento': 20.0,
            'distancia_agua_m': 500.0, 'declividade': 5.0, 'velocidade_kmh': 10.0,
            'vibracao_g': 1.0, 'horas_operacao': 5.0, 'horario_operacao': 10,
            'idade_equipamento': 5, 'historico_sinistros': 1,
            'tipo_solo': 'misto', 'tipo_operacao': 'colheita',
            'tipo_equipamento': 'trator', 'tem_iot': True
        }
        np.random.seed(1); s1 = calculate_risk_score(_make_df(reg))['risco_score'].iloc[0]
        np.random.seed(2); s2 = calculate_risk_score(_make_df(reg))['risco_score'].iloc[0]
        assert s1 != s2
