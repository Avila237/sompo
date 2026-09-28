-- Sprint 4 — integridade da escrita (S4-12, S4-13, S4-15).
--
-- ADITIVA E IDEMPOTENTE, como a da Entrega 3: nenhum DROP de tabela ou coluna,
-- nenhuma linha apagada. Pode ser reexecutada sem efeito colateral.
-- Numa transacao so: se a trava de duplicatas (secao 3) disparar, nada fica
-- aplicado pela metade.

BEGIN;

-- 1. Idempotencia da ingestao (S4-12) -------------------------------------
-- leitura_id: UUID gerado pelo cliente antes do primeiro envio e reusado no
-- retry. Nulo nas linhas do seed e em cliente que nao manda a chave; varios
-- NULL convivem sob o UNIQUE. payload_hash distingue o reenvio legitimo (mesmo
-- payload) do conflito (mesma chave, payload diferente).
ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS leitura_id UUID;
ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS payload_hash TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_avaliacoes_leitura_id ON avaliacoes(leitura_id);

-- 2. Decomposicao SHAP completa por grupo (S4-15) -------------------------
-- Soma com sinal dos 30 valores SHAP por grupo, a mesma que POST /avaliacoes
-- devolve. Nula nas predicoes do seed, gravadas antes desta coluna existir.
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS contribuicoes_por_grupo JSONB;

-- 3. Uma predicao por avaliacao e versao de modelo (S4-13) ----------------
-- Antes de criar o indice, confere se ja ha duplicata (reexecutar o script de
-- predicoes em lote gerava uma). Se houver, a migration para com erro em vez de
-- apagar qualquer coisa: a limpeza e decisao humana, com a lista em maos.
DO $$
DECLARE
    n_duplicadas INT;
BEGIN
    SELECT count(*) INTO n_duplicadas FROM (
        SELECT avaliacao_id, modelo_versao
        FROM predicoes
        GROUP BY avaliacao_id, modelo_versao
        HAVING count(*) > 1
    ) d;
    IF n_duplicadas > 0 THEN
        RAISE EXCEPTION
            'predicoes tem % pares (avaliacao_id, modelo_versao) duplicados; limpar antes de aplicar',
            n_duplicadas;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_predicoes_avaliacao_versao
    ON predicoes(avaliacao_id, modelo_versao);

-- 4. Escrita atomica da avaliacao e da predicao (S4-13) --------------------
-- As duas linhas numa transacao so: se a predicao falhar, a avaliacao tambem
-- nao fica. Substitui a compensacao manual da API, que podia deixar a avaliacao
-- orfa quando a propria compensacao falhava.
--
-- Com leitura_id repetido:
--   - mesmo payload_hash: nao grava nada e devolve a avaliacao existente
--     (reenvio = true), para a API responder com o resultado original;
--   - payload_hash diferente: erro 'PT409'. O prefixo PT faz o PostgREST
--     responder HTTP 409 (e nao 500), e a API traduz o codigo em 409.
CREATE OR REPLACE FUNCTION registrar_avaliacao(p_avaliacao JSONB, p_predicao JSONB)
RETURNS TABLE (avaliacao_id BIGINT, reenvio BOOLEAN)
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_leitura UUID := NULLIF(p_avaliacao->>'leitura_id', '')::UUID;
    v_id BIGINT;
    v_hash TEXT;
BEGIN
    IF v_leitura IS NOT NULL THEN
        SELECT a.avaliacao_id, a.payload_hash INTO v_id, v_hash
        FROM avaliacoes a WHERE a.leitura_id = v_leitura;
        IF FOUND THEN
            IF v_hash IS DISTINCT FROM p_avaliacao->>'payload_hash' THEN
                RAISE EXCEPTION 'leitura_id % reutilizado com outro payload', v_leitura
                    USING ERRCODE = 'PT409';
            END IF;
            RETURN QUERY SELECT v_id, TRUE;
            RETURN;
        END IF;
    END IF;

    -- A funcao vai no FROM, nao em SELECT (f(...)).*: nesta forma o Postgres
    -- avalia f uma vez por coluna, e o nextval queimaria ~34 ids por insercao.
    INSERT INTO avaliacoes
    SELECT r.* FROM jsonb_populate_record(
        NULL::avaliacoes,
        p_avaliacao || jsonb_build_object(
            'avaliacao_id', nextval(pg_get_serial_sequence('avaliacoes', 'avaliacao_id'))
        )
    ) AS r
    RETURNING avaliacoes.avaliacao_id INTO v_id;

    INSERT INTO predicoes
    SELECT r.* FROM jsonb_populate_record(
        NULL::predicoes,
        p_predicao || jsonb_build_object(
            'predicao_id', nextval(pg_get_serial_sequence('predicoes', 'predicao_id')),
            'avaliacao_id', v_id,
            'timestamp_predicao', now()
        )
    ) AS r;

    RETURN QUERY SELECT v_id, FALSE;
END;
$$;

-- O Supabase expoe funcoes do schema public via RPC, e PUBLIC tem EXECUTE por
-- padrao. Sem isto, a anon key chamaria a funcao pelo navegador e gravaria
-- direto no banco, furando o invariante "nenhum cliente fala com o banco".
REVOKE ALL ON FUNCTION registrar_avaliacao(JSONB, JSONB) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION registrar_avaliacao(JSONB, JSONB) TO service_role;

COMMIT;
