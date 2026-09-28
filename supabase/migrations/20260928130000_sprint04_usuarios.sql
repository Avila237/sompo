-- Sprint 4 — usuarios com senha em hash (S4-18, dividas D1 e D3).
--
-- ADITIVA E IDEMPOTENTE: cria a tabela se nao existir e nao apaga nada.
-- Substitui a variavel de ambiente DEMO_USERS, que guardava senha em texto.
-- Cadastro de usuarios: scripts/criar_usuario.py (nunca por INSERT manual,
-- que exigiria calcular o hash fora da aplicacao).

BEGIN;

CREATE TABLE IF NOT EXISTS usuarios (
    usuario      TEXT PRIMARY KEY CHECK (length(usuario) BETWEEN 1 AND 60),
    -- scrypt$n$r$p$sal$hash, gerado por backend/core/security.py
    senha_hash   TEXT NOT NULL CHECK (senha_hash LIKE 'scrypt$%'),
    perfil       TEXT NOT NULL CHECK (perfil IN ('analista', 'gestor', 'tecnico', 'operador')),
    -- So o operador tem vinculo: e o que recorta o que ele ve e em nome de quem envia.
    operador_id  VARCHAR REFERENCES operadores(operador_id),
    ativo        BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT usuarios_operador_tem_vinculo
        CHECK ((perfil = 'operador') = (operador_id IS NOT NULL))
);

-- Mesmo padrao das demais tabelas (migration da Entrega 3): RLS sem policy nega
-- tudo aos papeis anon e authenticated; so a service_role, no backend, le.
-- O hash nunca sai do servidor.
ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON usuarios FROM anon, authenticated;
-- Explicito em vez de depender dos privilegios padrao do projeto Supabase.
-- Sem DELETE: usuario sai por ativo = false, e a auditoria continua apontando para ele.
REVOKE DELETE, TRUNCATE ON usuarios FROM service_role;
GRANT SELECT, INSERT, UPDATE ON usuarios TO service_role;

COMMIT;
