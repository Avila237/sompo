-- Ensaio da migration 20260928130000_sprint04_usuarios (S4-18).
--
-- SO num Postgres LOCAL descartavel, nunca no Supabase. Preparo igual ao de
-- scripts/ensaios/sprint04_integridade.sql, com um passo a mais ANTES das
-- migrations, que imita os privilegios padrao de um projeto Supabase (ALL em
-- tabela nova para os tres papeis):
--   docker exec sompo-pg psql -U postgres -d ensaio -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role, anon, authenticated;"
-- Rodar:
--   docker exec -i sompo-pg psql -U postgres -d ensaio < scripts/ensaios/sprint04_usuarios.sql
-- Esperado: 1 e 2 passam; 3 a 7 TEM que dar erro; 8 mostra anon/authenticated
-- sem nada e service_role lendo e atualizando, sem apagar.

SET client_min_messages = warning;
INSERT INTO operadores (operador_id) VALUES ('OP-0015') ON CONFLICT DO NOTHING;

\echo '1. analista sem vinculo: ok'
INSERT INTO usuarios (usuario, senha_hash, perfil) VALUES ('ana', 'scrypt$x', 'analista');
\echo '2. operador com vinculo: ok'
INSERT INTO usuarios (usuario, senha_hash, perfil, operador_id) VALUES ('op', 'scrypt$x', 'operador', 'OP-0015');
\echo '3. operador SEM vinculo -> ERRO usuarios_operador_tem_vinculo'
INSERT INTO usuarios (usuario, senha_hash, perfil) VALUES ('op2', 'scrypt$x', 'operador');
\echo '4. gestor COM vinculo -> ERRO usuarios_operador_tem_vinculo'
INSERT INTO usuarios (usuario, senha_hash, perfil, operador_id) VALUES ('g', 'scrypt$x', 'gestor', 'OP-0015');
\echo '5. perfil invalido -> ERRO usuarios_perfil_check'
INSERT INTO usuarios (usuario, senha_hash, perfil) VALUES ('x', 'scrypt$x', 'admin');
\echo '6. senha em texto -> ERRO usuarios_senha_hash_check'
INSERT INTO usuarios (usuario, senha_hash, perfil) VALUES ('y', 'senha123', 'analista');
\echo '7. operador inexistente -> ERRO de FK'
INSERT INTO usuarios (usuario, senha_hash, perfil, operador_id) VALUES ('z', 'scrypt$x', 'operador', 'OP-9999');

\echo '8. privilegios efetivos'
SELECT r AS papel,
  has_table_privilege(r, 'usuarios', 'SELECT') AS le,
  has_table_privilege(r, 'usuarios', 'UPDATE') AS atualiza,
  has_table_privilege(r, 'usuarios', 'DELETE') AS apaga
FROM unnest(ARRAY['anon', 'authenticated', 'service_role']) r;
