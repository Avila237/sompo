-- Ensaio da migration 20260928120000_sprint04_integridade (S4-12/13/15).
--
-- SO num Postgres LOCAL descartavel, nunca no Supabase: insere e tenta gravar.
-- Preparo (uma vez):
--   docker run -d --name sompo-pg -e POSTGRES_PASSWORD=local -p 55432:5432 postgres:16
--   docker exec sompo-pg psql -U postgres -c "CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;"
--   docker exec sompo-pg createdb -U postgres ensaio
--   para cada arquivo em backend/db/schema.sql e supabase/migrations/*.sql, em ordem:
--     docker exec -i sompo-pg psql -U postgres -d ensaio -v ON_ERROR_STOP=1 < <arquivo>
-- Rodar:
--   docker exec -i sompo-pg psql -U postgres -d ensaio < scripts/ensaios/sprint04_integridade.sql
-- Esperado: comentado em cada passo. Os passos 6 e 7 TEM que dar erro.

\set ON_ERROR_STOP 1
SET client_min_messages = warning;

INSERT INTO equipamentos (equipamento_id, tipo_equipamento, modelo_equipamento, categoria_manual,
    idade_equipamento, historico_sinistros, tem_iot, intervalo_manut_recomendado_dias,
    intervalo_manut_recomendado_horas)
VALUES ('EQ-0001', 'trator', 'John Deere 7J195', 'trator_operacao', 5, 1, true, 180, 500);
INSERT INTO operadores (operador_id) VALUES ('OP-0001');

CREATE TEMP TABLE base AS SELECT jsonb_build_object(
    'equipamento_id', 'EQ-0001', 'operador_id', 'OP-0001', 'timestamp', now(),
    'temperatura_ar', 25, 'precipitacao_mm', 10, 'umidade_solo', 30, 'velocidade_vento', 5,
    'condicao_clima', 'nublado', 'latitude', -12.5, 'longitude', -55.7, 'tipo_solo', 'argiloso',
    'distancia_agua_m', 300, 'declividade', 6, 'tipo_operacao', 'colheita', 'velocidade_kmh', 5.5,
    'vibracao_g', 1.4, 'temperatura_motor', 88, 'horas_operacao', 6, 'horario_operacao', 11,
    'pct_velocidade_acima_recomendada', 18, 'freq_eventos_bruscos', 3, 'pct_operacoes_noturnas', 12,
    'score_operador_historico', 45, 'ultima_manutencao_dias', 120, 'ultima_manutencao_horas_op', 300,
    'manutencao_atrasada', false, 'atraso_manutencao_pct', 0.667, 'risco_score', 42.1,
    'faixa_risco', 'medio', 'fonte', 'telemetria', 'clima_origem', 'payload'
) AS av, jsonb_build_object(
    'risco_score_predito', 42.1, 'faixa_predita', 'medio', 'top_fatores_shap', '[]'::jsonb,
    'modelo_versao', 'xgboost-v1-baseline', 'contribuicoes_por_grupo', '{"ambiental": 1.5}'::jsonb
) AS pr;

\echo '1. insercao nova -> (1, f)'
SELECT r.* FROM base, registrar_avaliacao(av || '{"leitura_id":"11111111-1111-1111-1111-111111111111","payload_hash":"h1"}', pr) r;

\echo '2. reenvio: mesma chave e mesmo hash -> (1, t), nada gravado'
SELECT r.* FROM base, registrar_avaliacao(av || '{"leitura_id":"11111111-1111-1111-1111-111111111111","payload_hash":"h1"}', pr) r;
SELECT (SELECT count(*) FROM avaliacoes) AS avaliacoes, (SELECT count(*) FROM predicoes) AS predicoes;

\echo '3. sem leitura_id: grava de novo -> (2, f)'
SELECT r.* FROM base, registrar_avaliacao(av, pr) r;

\echo '4. atomicidade: predicao invalida (faixa_predita nula) nao deixa avaliacao'
SELECT count(*) AS antes FROM avaliacoes;
DO $$ BEGIN
    PERFORM registrar_avaliacao((SELECT av FROM base), (SELECT pr - 'faixa_predita' FROM base));
    RAISE EXCEPTION 'deveria ter falhado';
EXCEPTION WHEN not_null_violation THEN RAISE NOTICE 'falhou como esperado (not_null)';
END $$;
SELECT count(*) AS depois FROM avaliacoes;

\echo '5. contribuicoes gravadas e timestamp preenchido'
SELECT avaliacao_id, contribuicoes_por_grupo, timestamp_predicao IS NOT NULL AS tem_ts FROM predicoes ORDER BY 1;

\set ON_ERROR_STOP 0
\set VERBOSITY verbose
\echo '6. conflito: mesma chave, outro hash -> ERRO PT409'
SELECT r.* FROM base, registrar_avaliacao(av || '{"leitura_id":"11111111-1111-1111-1111-111111111111","payload_hash":"OUTRO"}', pr) r;

\echo '7. anon nao executa a funcao -> ERRO permission denied'
SET ROLE anon;
SELECT registrar_avaliacao('{}'::jsonb, '{}'::jsonb);
RESET ROLE;

\echo '8. service_role executa -> t'
SELECT has_function_privilege('service_role', 'registrar_avaliacao(jsonb,jsonb)', 'EXECUTE') AS service_role_pode;
