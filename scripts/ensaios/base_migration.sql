-- Ensaio da migration 20260527000000_base (BRA-446 item 3, R4-04).
--
-- ESTADO: escrito em 28/09/2026 e ainda NAO EXECUTADO: a maquina onde foi
-- escrito nao tinha Docker nem Postgres. Rodar antes de aplicar a base no
-- Supabase; com o resultado conferido, apagar este paragrafo.
--
-- SO num Postgres LOCAL descartavel, nunca no Supabase: insere e aplica DDL.
-- Compara dois caminhos ate a mesma estrutura:
--   atual = o caminho antigo: backend/db/schema.sql (lido do historico) + as 3 migrations
--   vazio = o caminho novo: supabase/migrations/*.sql em ordem de nome, base primeiro
--
-- Preparo, da raiz do repo (container proprio, com o repo montado so leitura):
--   docker run -d --name sompo-pg-base -e POSTGRES_PASSWORD=local -v "$PWD":/repo:ro postgres:16
--   until docker exec sompo-pg-base pg_isready -U postgres -h 127.0.0.1; do sleep 1; done
--   docker exec sompo-pg-base psql -U postgres -c "CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;"
--   docker exec sompo-pg-base createdb -U postgres atual
--   docker exec sompo-pg-base createdb -U postgres vazio
--   # caminho antigo; schema.sql so teve o commit 8a485df. O sed tira o BOM do inicio do arquivo
--   git show 8a485df:backend/db/schema.sql | LC_ALL=C sed $'1s/^\xef\xbb\xbf//' \
--     | docker exec -i sompo-pg-base psql -U postgres -d atual -v ON_ERROR_STOP=1
--   for f in $(ls supabase/migrations/*.sql | grep -v _base.sql); do
--     docker exec sompo-pg-base psql -U postgres -d atual -v ON_ERROR_STOP=1 -f /repo/$f || break; done
--   # caminho novo
--   for f in supabase/migrations/*.sql; do
--     docker exec sompo-pg-base psql -U postgres -d vazio -v ON_ERROR_STOP=1 -f /repo/$f || break; done
--   # pg_dump recente emite \restrict/\unrestrict com chave aleatoria: fora da comparacao
--   dump() { docker exec sompo-pg-base pg_dump -U postgres --schema-only "$1" | grep -vE '^\\(un)?restrict '; }
--   dump atual > /tmp/atual_antes.sql
--
-- Rodar (no banco atual, que ganha dados antes da base):
--   docker exec sompo-pg-base psql -U postgres -d atual -f /repo/scripts/ensaios/base_migration.sql
-- Depois, a estrutura:
--   dump atual > /tmp/atual_depois.sql
--   dump vazio > /tmp/vazio.sql
--   diff /tmp/atual_antes.sql /tmp/atual_depois.sql   # 3. a base nao mudou o banco atual
--   diff /tmp/atual_antes.sql /tmp/vazio.sql          # 4. caminho novo == caminho antigo
--   for f in supabase/migrations/*.sql; do
--     docker exec sompo-pg-base psql -U postgres -d vazio -v ON_ERROR_STOP=1 -f /repo/$f || break; done
--   dump vazio | diff /tmp/vazio.sql -                 # 5. reaplicar tudo nao muda nada
-- Limpeza: docker rm -f sompo-pg-base
--
-- Esperado: 1 sem ERRO, com 10 NOTICE "already exists, skipping" (4 tabelas e
-- 6 indices); 2 -> t; os diff 3, 4 e 5 sem nenhuma saida.

\set ON_ERROR_STOP 1

INSERT INTO equipamentos (equipamento_id, tipo_equipamento, modelo_equipamento, categoria_manual,
    idade_equipamento, historico_sinistros, tem_iot, intervalo_manut_recomendado_dias,
    intervalo_manut_recomendado_horas)
VALUES ('EQ-0001', 'trator', 'John Deere 7J195', 'trator_operacao', 5, 1, true, 180, 500);
INSERT INTO operadores (operador_id) VALUES ('OP-0001');
SELECT registrar_avaliacao(jsonb_build_object(
    'equipamento_id', 'EQ-0001', 'operador_id', 'OP-0001', 'timestamp', now(),
    'temperatura_ar', 25, 'precipitacao_mm', 10, 'umidade_solo', 30, 'velocidade_vento', 5,
    'condicao_clima', 'nublado', 'latitude', -12.5, 'longitude', -55.7, 'tipo_solo', 'argiloso',
    'distancia_agua_m', 300, 'declividade', 6, 'tipo_operacao', 'colheita', 'velocidade_kmh', 5.5,
    'vibracao_g', 1.4, 'temperatura_motor', 88, 'horas_operacao', 6, 'horario_operacao', 11,
    'pct_velocidade_acima_recomendada', 18, 'freq_eventos_bruscos', 3, 'pct_operacoes_noturnas', 12,
    'score_operador_historico', 45, 'ultima_manutencao_dias', 120, 'ultima_manutencao_horas_op', 300,
    'manutencao_atrasada', false, 'atraso_manutencao_pct', 0.667, 'risco_score', 42.1,
    'faixa_risco', 'medio', 'fonte', 'telemetria', 'clima_origem', 'payload'
), jsonb_build_object(
    'risco_score_predito', 42.1, 'faixa_predita', 'medio', 'top_fatores_shap', '[]'::jsonb,
    'modelo_versao', 'xgboost-v1-baseline'
));

CREATE TEMP TABLE antes AS SELECT
    (SELECT count(*) FROM equipamentos) AS equipamentos,
    (SELECT count(*) FROM operadores) AS operadores,
    (SELECT count(*) FROM avaliacoes) AS avaliacoes,
    (SELECT count(*) FROM predicoes) AS predicoes;
TABLE antes;

\echo '1. base sobre o banco com dados: sem ERRO, so NOTICE "already exists, skipping"'
\i /repo/supabase/migrations/20260527000000_base.sql

\echo '2. nada apagado: contagens iguais -> t'
SELECT (SELECT count(*) FROM equipamentos) = equipamentos
   AND (SELECT count(*) FROM operadores) = operadores
   AND (SELECT count(*) FROM avaliacoes) = avaliacoes
   AND (SELECT count(*) FROM predicoes) = predicoes AS nada_apagado
FROM antes;
