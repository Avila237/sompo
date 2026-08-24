-- Entrega 3 — integracao.
--
-- ADITIVA E IDEMPOTENTE. Nao contem DROP: backend/db/schema.sql comeca
-- destruindo as tabelas e reexecuta-lo apagaria os registros existentes.

-- 1. Procedencia do dado (RF-03) -----------------------------------------
-- Distingue o que veio do seed em lote do que chegou pela ingestao da API.
ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS
    fonte VARCHAR NOT NULL DEFAULT 'seed';

-- 2. Procedencia do clima (RF-05) ----------------------------------------
-- 'open-meteo' quando enriquecido pela API externa, 'payload' quando a
-- chamada falhou e caiu para os valores enviados pelo cliente, 'seed' para
-- as linhas historicas. Permite a auditoria distinguir clima real de simulado.
ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS
    clima_origem VARCHAR NOT NULL DEFAULT 'seed';

-- 3. Registro de uso (RF-08) ---------------------------------------------
-- Rastreia entradas, saidas e decisoes: quem pediu, quando, sobre qual
-- equipamento, qual score saiu e qual versao do modelo decidiu.
CREATE TABLE IF NOT EXISTS auditoria (
    auditoria_id   BIGSERIAL PRIMARY KEY,
    timestamp      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    usuario        VARCHAR NOT NULL,
    perfil         VARCHAR NOT NULL,
    acao           VARCHAR NOT NULL,
    equipamento_id VARCHAR,
    avaliacao_id   BIGINT,
    score_gerado   NUMERIC(5,2),
    modelo_versao  VARCHAR,
    status         VARCHAR NOT NULL,
    detalhe        TEXT
);

CREATE INDEX IF NOT EXISTS idx_auditoria_ts      ON auditoria(timestamp);
CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria(usuario);
CREATE INDEX IF NOT EXISTS idx_auditoria_acao    ON auditoria(acao);

-- 4. Row Level Security (RF-07) ------------------------------------------
-- Sem policy, a RLS nega tudo. Nenhum papel anonimo le ou escreve; a
-- service_role bypassa RLS por definicao e e o unico caminho de acesso,
-- exercido apenas pelo backend. O browser nao carrega chave de banco.
ALTER TABLE equipamentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE operadores   ENABLE ROW LEVEL SECURITY;
ALTER TABLE avaliacoes   ENABLE ROW LEVEL SECURITY;
ALTER TABLE predicoes    ENABLE ROW LEVEL SECURITY;
ALTER TABLE auditoria    ENABLE ROW LEVEL SECURITY;
