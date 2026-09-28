-- Base — estrutura inicial: equipamentos, operadores, avaliacoes e predicoes.
--
-- Substitui backend/db/schema.sql, removido: ele comecava com DROP TABLE e
-- reexecuta-lo apagava todos os registros. Mesmas tabelas, colunas e indices,
-- sem nenhum DROP e com IF NOT EXISTS em cada CREATE.
--
-- ADITIVA E IDEMPOTENTE, como as demais:
--   - no banco que ja existe (montado por schema.sql + migrations) nao faz nada;
--   - num banco vazio, seguida das outras migrations em ordem de nome, monta a
--     mesma estrutura que schema.sql + migrations montavam.
-- Por isso so cria o que schema.sql criava. Colunas, tabelas, RLS e funcoes
-- posteriores ficam nas migrations seguintes, na ordem em que entraram.
-- IF NOT EXISTS confere so o nome: nao corrige uma tabela que ja exista com
-- outra estrutura.
--
-- A estrutura final do banco e este arquivo seguido dos demais de
-- supabase/migrations/, em ordem de nome. Ensaio: scripts/ensaios/base_migration.sql.

BEGIN;

-- Um registro por equipamento (~200 no seed)
CREATE TABLE IF NOT EXISTS equipamentos (
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

-- Um registro por operador (~80 no seed)
CREATE TABLE IF NOT EXISTS operadores (
    operador_id VARCHAR PRIMARY KEY
);

-- Avaliacoes de risco: 5.000 do seed mais as ingeridas pela API
CREATE TABLE IF NOT EXISTS avaliacoes (
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

CREATE INDEX IF NOT EXISTS idx_avaliacoes_equipamento ON avaliacoes(equipamento_id);
CREATE INDEX IF NOT EXISTS idx_avaliacoes_operador    ON avaliacoes(operador_id);
CREATE INDEX IF NOT EXISTS idx_avaliacoes_timestamp   ON avaliacoes(timestamp);
CREATE INDEX IF NOT EXISTS idx_avaliacoes_faixa       ON avaliacoes(faixa_risco);

-- Predicoes do modelo: as do seed (scripts/populate_predictions.py) e as da API
CREATE TABLE IF NOT EXISTS predicoes (
    predicao_id         BIGSERIAL PRIMARY KEY,
    avaliacao_id        BIGINT REFERENCES avaliacoes(avaliacao_id),
    timestamp_predicao  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    risco_score_predito NUMERIC(5,2) NOT NULL,
    faixa_predita       VARCHAR NOT NULL,
    top_fatores_shap    JSONB NOT NULL,
    modelo_versao       VARCHAR NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_predicoes_avaliacao ON predicoes(avaliacao_id);
CREATE INDEX IF NOT EXISTS idx_predicoes_faixa     ON predicoes(faixa_predita);

COMMIT;
