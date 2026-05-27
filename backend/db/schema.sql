-- SafeField — Esquema do banco de dados Supabase (PostgreSQL)
-- Idempotente: pode ser executado multiplas vezes sem erro

DROP TABLE IF EXISTS predicoes;
DROP TABLE IF EXISTS avaliacoes;
DROP TABLE IF EXISTS operadores;
DROP TABLE IF EXISTS equipamentos;

-- ~200 registros (1 por equipamento unico)
CREATE TABLE equipamentos (
    equipamento_id   VARCHAR PRIMARY KEY,
    tipo_equipamento VARCHAR NOT NULL,
    modelo_equipamento VARCHAR NOT NULL,
    categoria_manual VARCHAR NOT NULL,
    idade_equipamento INT NOT NULL,
    historico_sinistros INT NOT NULL,
    tem_iot BOOLEAN NOT NULL,
    intervalo_manut_recomendado_dias INT NOT NULL,
    intervalo_manut_recomendado_horas INT NOT NULL
);

-- ~80 registros (1 por operador unico)
CREATE TABLE operadores (
    operador_id VARCHAR PRIMARY KEY
);

-- 5000 avaliacoes de risco
CREATE TABLE avaliacoes (
    avaliacao_id     BIGSERIAL PRIMARY KEY,
    equipamento_id   VARCHAR NOT NULL REFERENCES equipamentos(equipamento_id),
    operador_id      VARCHAR NOT NULL REFERENCES operadores(operador_id),
    timestamp        TIMESTAMPTZ NOT NULL,

    -- Ambientais
    temperatura_ar   NUMERIC NOT NULL,
    precipitacao_mm  NUMERIC NOT NULL,
    umidade_solo     NUMERIC NOT NULL,
    velocidade_vento NUMERIC NOT NULL,
    condicao_clima   VARCHAR NOT NULL,

    -- Geograficas
    latitude         NUMERIC NOT NULL,
    longitude        NUMERIC NOT NULL,
    tipo_solo        VARCHAR NOT NULL,
    distancia_agua_m NUMERIC NOT NULL,
    declividade      NUMERIC NOT NULL,

    -- Operacionais
    tipo_operacao    VARCHAR NOT NULL,
    velocidade_kmh   NUMERIC NOT NULL,
    vibracao_g       NUMERIC,
    temperatura_motor NUMERIC,
    horas_operacao   NUMERIC NOT NULL,
    horario_operacao INT NOT NULL,

    -- Operador
    pct_velocidade_acima_recomendada NUMERIC NOT NULL,
    freq_eventos_bruscos   NUMERIC NOT NULL,
    pct_operacoes_noturnas NUMERIC NOT NULL,
    score_operador_historico NUMERIC NOT NULL,

    -- Manutencao
    ultima_manutencao_dias     INT NOT NULL,
    ultima_manutencao_horas_op NUMERIC NOT NULL,
    manutencao_atrasada        BOOLEAN NOT NULL,
    atraso_manutencao_pct      NUMERIC NOT NULL,

    -- Target
    risco_score NUMERIC(5,2) NOT NULL,
    faixa_risco VARCHAR NOT NULL
);

CREATE INDEX idx_avaliacoes_equipamento ON avaliacoes(equipamento_id);
CREATE INDEX idx_avaliacoes_operador    ON avaliacoes(operador_id);
CREATE INDEX idx_avaliacoes_timestamp   ON avaliacoes(timestamp);
CREATE INDEX idx_avaliacoes_faixa       ON avaliacoes(faixa_risco);

-- Predicoes do modelo (vazia neste prompt — populada no Prompt 2)
CREATE TABLE predicoes (
    predicao_id         BIGSERIAL PRIMARY KEY,
    avaliacao_id        BIGINT REFERENCES avaliacoes(avaliacao_id),
    timestamp_predicao  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    risco_score_predito NUMERIC(5,2) NOT NULL,
    faixa_predita       VARCHAR NOT NULL,
    top_fatores_shap    JSONB NOT NULL,
    modelo_versao       VARCHAR NOT NULL
);

CREATE INDEX idx_predicoes_avaliacao ON predicoes(avaliacao_id);
CREATE INDEX idx_predicoes_faixa     ON predicoes(faixa_predita);