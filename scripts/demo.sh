#!/usr/bin/env bash
#
# Roteiro de demonstracao do fluxo integrado — SafeField, Entrega 3.
#
# Sobe a API, autentica, exercita seguranca, roda o simulador e mostra a
# trilha de auditoria. Pausa entre etapas para narracao.
#
# Uso:
#   ./scripts/demo.sh                # pausa em cada etapa (aperte ENTER)
#   ./scripts/demo.sh --auto 4       # avanca sozinho a cada 4 segundos
#   ./scripts/demo.sh --leituras 8   # quantas leituras o simulador envia
#
# NUNCA imprime service_role, senha ou token completo.

set -uo pipefail
cd "$(dirname "$0")/.."

API_PORT=8000
API="http://localhost:${API_PORT}"
LEITURAS=5
AUTO=""
LOG="/tmp/safefield-demo-api.log"
LOG_WEB="/tmp/safefield-demo-web.log"
PORTA_WEB=5173
SEM_WEB=""

while [ $# -gt 0 ]; do
  case "$1" in
    --auto)     AUTO="${2:-4}"; shift 2 ;;
    --leituras) LEITURAS="${2:-5}"; shift 2 ;;
    --porta)    API_PORT="${2:-8000}"; API="http://localhost:${API_PORT}"; shift 2 ;;
    --sem-web)  SEM_WEB=1; shift ;;
    -h|--help)  sed -n '3,16p' "$0"; exit 0 ;;
    *) echo "opcao desconhecida: $1"; exit 1 ;;
  esac
done

AZUL=$'\033[1;34m'; VERDE=$'\033[1;32m'; AMAR=$'\033[1;33m'
VERM=$'\033[1;31m'; CINZA=$'\033[0;90m'; FIM=$'\033[0m'

titulo() {
  echo
  echo "${AZUL}================================================================${FIM}"
  echo "${AZUL} $1${FIM}"
  echo "${AZUL}================================================================${FIM}"
  echo
}
nota()  { echo "${CINZA}  $1${FIM}"; }
ok()    { echo "${VERDE}  OK${FIM}  $1"; }
falha() { echo "${VERM}  FALHA${FIM}  $1"; }

pausa() {
  if [ -n "$AUTO" ]; then sleep "$AUTO"
  else echo; echo "${AMAR}  [ENTER para continuar]${FIM}"; read -r _; fi
}

encerrar() {
  echo
  nota "encerrando a API..."
  pkill -f "uvicorn backend.api.main.*${API_PORT}" 2>/dev/null
  pkill -f "vite.*${PORTA_WEB}" 2>/dev/null
  pkill -f "npm run dev" 2>/dev/null
  nota "logs: API em ${LOG}${SEM_WEB:+ }${SEM_WEB:-, dashboard em ${LOG_WEB}}"
}
trap encerrar EXIT

# ---------------------------------------------------------------- 0. checagens
titulo "0. Pre-requisitos"

[ -x .venv/bin/python ] || { falha "venv ausente. Rode: python3.13 -m venv .venv"; exit 1; }
ok "venv ($(.venv/bin/python -V 2>&1))"

[ -f .env ] || { falha ".env ausente na raiz do projeto"; exit 1; }
ok ".env presente (conteudo nao exibido)"

for artefato in models/xgboost_model.joblib models/encoder.joblib models/features.json; do
  [ -f "$artefato" ] || { falha "$artefato ausente. Rode: python backend/ml/train.py"; exit 1; }
done
ok "artefatos do modelo em models/"

nota "checando o banco..."
if ! .venv/bin/python -c "
from backend.db.repository import contar
print('  equipamentos %d | operadores %d | avaliacoes %d | predicoes %d' % (
    contar('equipamentos'), contar('operadores'), contar('avaliacoes'), contar('predicoes')))
" 2>/dev/null; then
  falha "banco inacessivel. O projeto Supabase pode ter pausado por inatividade."
  exit 1
fi
ok "Supabase respondendo"

pausa

# ------------------------------------------------------------------- 1. subir
titulo "1. Subindo a API"

pkill -f "uvicorn backend.api.main" 2>/dev/null; sleep 1
.venv/bin/python -m uvicorn backend.api.main:app --port "$API_PORT" --log-level info > "$LOG" 2>&1 &

nota "aguardando o modelo carregar no startup..."
for _ in $(seq 1 40); do
  curl -s -o /dev/null "${API}/health" 2>/dev/null && break
  sleep 0.5
done

SAUDE=$(curl -s "${API}/health")
echo "$SAUDE" | python3 -m json.tool
if echo "$SAUDE" | python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("status")=="ok" else 1)'; then
  ok "API no ar — modelo carregado uma vez, no startup"
else
  falha "API subiu degradada — veja ${LOG}"; exit 1
fi

nota "Swagger navegavel em ${API}/docs"

if [ -z "$SEM_WEB" ]; then
  if [ ! -f dashboard/src/lib/apiClient.ts ]; then
    falha "dashboard ainda nao religado a API (falta dashboard/src/lib/apiClient.ts)."
    nota  "Esta branch nao tem o PR do dashboard. Use --sem-web para seguir so com a API,"
    nota  "ou faca merge da branch do dashboard antes de gravar."
    exit 1
  fi

  if [ ! -f dashboard/.env.local ]; then
    cp dashboard/.env.example dashboard/.env.local
    nota "dashboard/.env.local criado a partir do .env.example"
  fi
  if ! grep -q "^VITE_API_BASE_URL=${API}$" dashboard/.env.local; then
    printf 'VITE_API_BASE_URL=%s\n' "$API" > dashboard/.env.local
    nota "VITE_API_BASE_URL apontado para ${API}"
  fi

  if [ ! -d dashboard/node_modules ]; then
    nota "instalando dependencias do dashboard (primeira vez)..."
    ( cd dashboard && npm install --silent ) || { falha "npm install falhou"; exit 1; }
  fi

  nota "subindo o dashboard..."
  ( cd dashboard && npm run dev -- --port "$PORTA_WEB" --strictPort ) > "$LOG_WEB" 2>&1 &

  for _ in $(seq 1 60); do
    curl -s -o /dev/null "http://localhost:${PORTA_WEB}/" 2>/dev/null && break
    sleep 0.5
  done
  if curl -s -o /dev/null "http://localhost:${PORTA_WEB}/" 2>/dev/null; then
    ok "dashboard no ar em http://localhost:${PORTA_WEB}"
    nota "faca login com o usuario 'analista' — a senha esta em: grep DEMO_USERS .env"
  else
    falha "dashboard nao subiu; veja ${LOG_WEB}"
  fi
fi
pausa

# ---------------------------------------------------------------- 2. seguranca
titulo "2. Controle de acesso"

nota "2a. rota de dado SEM token:"
CODIGO=$(curl -s -o /tmp/_d1 -w '%{http_code}' "${API}/equipamentos")
echo "      HTTP ${CODIGO}  $(cat /tmp/_d1)"
[ "$CODIGO" = "401" ] && ok "recusado" || falha "esperado 401"

nota "2b. token forjado:"
CODIGO=$(curl -s -o /dev/null -w '%{http_code}' "${API}/equipamentos" -H "Authorization: Bearer nao.e.um.token")
echo "      HTTP ${CODIGO}"
[ "$CODIGO" = "401" ] && ok "recusado" || falha "esperado 401"

nota "2c. senha errada:"
CODIGO=$(curl -s -o /tmp/_d2 -w '%{http_code}' -X POST "${API}/auth/token" \
  -H 'Content-Type: application/json' -d '{"usuario":"analista","senha":"errada"}')
echo "      HTTP ${CODIGO}  $(cat /tmp/_d2)"
[ "$CODIGO" = "401" ] && ok "recusado" || falha "esperado 401"

nota "2d. a chave ANONIMA do Supabase nao le o banco (RLS):"
REF=$(grep '^SUPABASE_URL' .env | sed 's|.*//||; s|\..*||')
ANON=$(grep '^SUPABASE_ANON_KEY' .env | cut -d= -f2)
FAIXA=$(curl -sI "https://${REF}.supabase.co/rest/v1/avaliacoes?select=*" \
  -H "apikey: ${ANON}" -H "Authorization: Bearer ${ANON}" \
  -H "Prefer: count=exact" -H "Range: 0-0" | grep -i '^content-range' | tr -d '\r')
echo "      ${FAIXA}"
echo "$FAIXA" | grep -q '\*/0' \
  && ok "RLS nega o papel anonimo — so o backend acessa, via service_role" \
  || falha "a anon key leu dados; a RLS nao esta ativa"

pausa

# ------------------------------------------------------------------ 3. login
titulo "3. Autenticacao"

SENHA=$(grep '^DEMO_USERS' .env | sed 's/.*analista:\([^:,]*\):.*/\1/')
RESP=$(curl -s -X POST "${API}/auth/token" -H 'Content-Type: application/json' \
  -d "{\"usuario\":\"analista\",\"senha\":\"${SENHA}\"}")
TOKEN=$(echo "$RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
echo "$RESP" | python3 -c '
import json,sys
d = json.load(sys.stdin); d["access_token"] = "<omitido>"
print(json.dumps(d, indent=2, ensure_ascii=False))'
ok "token emitido (${#TOKEN} caracteres, nao exibido)"
AUTH="Authorization: Bearer ${TOKEN}"
pausa

# --------------------------------------------------------------- 4. validacao
titulo "4. Validacao da entrada"

nota "4a. velocidade de 999 km/h:"
CODIGO=$(curl -s -o /tmp/_d3 -w '%{http_code}' -X POST "${API}/avaliacoes" -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"equipamento_id":"EQ-0001","velocidade_kmh":999}')
echo "      HTTP ${CODIGO}"
python3 -c '
import json
d = json.load(open("/tmp/_d3"))
for e in d["detail"][:3]:
    print(f"      campo {e[\"loc\"][-1]}: {e[\"msg\"]}")' 2>/dev/null
[ "$CODIGO" = "422" ] && ok "recusado sem tocar o banco" || falha "esperado 422"

nota "4b. tentando forjar um campo que o SERVIDOR deriva:"
CODIGO=$(curl -s -o /tmp/_d4 -w '%{http_code}' -X POST "${API}/avaliacoes" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"equipamento_id":"EQ-0042","operador_id":"OP-0015","latitude":-12.5,"longitude":-55.7,
       "tipo_solo":"argiloso","distancia_agua_m":300,"declividade":6,"tipo_operacao":"colheita",
       "velocidade_kmh":5.5,"horas_operacao":6,"horario_operacao":11,
       "pct_velocidade_acima_recomendada":18,"freq_eventos_bruscos":3,
       "pct_operacoes_noturnas":12,"score_operador_historico":45,
       "ultima_manutencao_dias":120,"ultima_manutencao_horas_op":300,
       "faixa_risco":"baixo"}')
echo "      HTTP ${CODIGO}  $(python3 -c 'import json;d=json.load(open("/tmp/_d4"));print(d["detail"][0]["type"], "->", d["detail"][0]["loc"][-1])' 2>/dev/null)"
[ "$CODIGO" = "422" ] && ok "faixa_risco e derivada do score; o cliente nao a define" || falha "esperado 422"

nota "4c. equipamento inexistente:"
CODIGO=$(curl -s -o /tmp/_d5 -w '%{http_code}' -X POST "${API}/avaliacoes" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"equipamento_id":"EQ-9999","operador_id":"OP-0015","latitude":-12.5,"longitude":-55.7,
       "tipo_solo":"argiloso","distancia_agua_m":300,"declividade":6,"tipo_operacao":"colheita",
       "velocidade_kmh":5.5,"horas_operacao":6,"horario_operacao":11,
       "pct_velocidade_acima_recomendada":18,"freq_eventos_bruscos":3,
       "pct_operacoes_noturnas":12,"score_operador_historico":45,
       "ultima_manutencao_dias":120,"ultima_manutencao_horas_op":300}')
echo "      HTTP ${CODIGO}  $(cat /tmp/_d5)"
[ "$CODIGO" = "404" ] && ok "integridade referencial preservada" || falha "esperado 404"

pausa

# ------------------------------------------------------- 5. fluxo ponta a ponta
titulo "5. Fluxo de ponta a ponta"

ANTES=$(.venv/bin/python -c "from backend.db.repository import contar; print(contar('avaliacoes'))")
nota "avaliacoes no banco antes: ${ANTES}"
echo
nota "cada leitura: valida -> clima Open-Meteo -> deriva manutencao -> persiste"
nota "              -> XGBoost + SHAP -> grava predicao -> grava auditoria"
echo
.venv/bin/python scripts/simulate_telemetry.py --n "$LEITURAS" --intervalo 2 --cenario critico

DEPOIS=$(.venv/bin/python -c "from backend.db.repository import contar; print(contar('avaliacoes'))")
echo
ok "avaliacoes: ${ANTES} -> ${DEPOIS}"
pausa

# ------------------------------------------------------------- 6. saida legivel
titulo "6. O score nunca vem sozinho"

nota "ultimo alerta gerado, e a decomposicao que o produziu:"
echo
curl -s -H "$AUTH" "${API}/alertas?limite=1" > /tmp/_alerta
EQ=$(python3 -c "import json; print(json.load(open('/tmp/_alerta'))['itens'][0]['equipamento_id'])")

python3 - /tmp/_alerta <<'PY'
import json, sys
a = json.load(open(sys.argv[1]))['itens'][0]
print('    equipamento  ' + str(a['equipamento_id']))
print('    score        ' + str(a['risco_score']) + '   faixa ' + str(a['faixa_risco']))
print('    operacao     ' + str(a['tipo_operacao']) + '   operador ' + str(a['operador_id']))
PY

echo
nota "decomposicao SHAP por grupo (+ aumenta o risco / - reduz):"
curl -s -H "$AUTH" "${API}/equipamentos/${EQ}" > /tmp/_detalhe
python3 - /tmp/_detalhe <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
p = d.get('predicao')
if not p:
    print('    (sem predicao para este equipamento)')
    raise SystemExit
grupos = {}
for f in p['top_fatores_shap']:
    g = f['grupo']
    grupos[g] = grupos.get(g, 0.0) + float(f['shap_value'])
for g, v in sorted(grupos.items(), key=lambda x: -abs(x[1])):
    barra = '#' * min(28, int(abs(v)))
    print('    {:<13} {:+8.2f}  {}'.format(g, v, barra))
print()
print('    top fatores contribuintes:')
for f in p['top_fatores_shap']:
    print('      {:<34} {:+8.2f}  [{}]'.format(
        f['feature'], float(f['shap_value']), f['grupo']))
PY
pausa

# ---------------------------------------------------------------- 7. auditoria
titulo "7. Trilha de auditoria"

nota "quem pediu, quando, qual equipamento, qual score, qual versao do modelo:"
echo
.venv/bin/python -c "
from backend.db.repository import get_client
r = get_client().table('auditoria').select('*').order('auditoria_id', desc=True).limit(8).execute().data
print('   id  hora      usuario/perfil       acao       status   equip      score   modelo')
print('   ' + '-'*84)
for a in reversed(r):
    print(f\"   {a['auditoria_id']:<3} {a['timestamp'][11:19]}  {a['usuario']+'/'+a['perfil']:<19}\"
          f\" {a['acao']:<10} {a['status']:<8} {a['equipamento_id'] or '-':<10}\"
          f\" {str(a['score_gerado'] or '-'):<7} {a['modelo_versao'] or '-'}\")
"
echo
nota "log da API, correlacionado por request_id:"
grep -E "safefield\.(scoring|clima|api)" "$LOG" | tail -5 | sed 's/^/    /' | cut -c1-130
pausa

# ------------------------------------------------------------------- 8. fim
titulo "8. Resumo"

.venv/bin/python -c "
from backend.db.repository import get_client, contar
c = get_client()
seed = c.table('avaliacoes').select('*', count='exact').eq('fonte','seed').limit(0).execute().count
tel  = c.table('avaliacoes').select('*', count='exact').eq('fonte','telemetria').limit(0).execute().count
print(f'  equipamentos     {contar(\"equipamentos\")}')
print(f'  operadores       {contar(\"operadores\")}')
print(f'  avaliacoes       {contar(\"avaliacoes\")}  (seed {seed} | telemetria {tel})')
print(f'  predicoes        {contar(\"predicoes\")}')
print(f'  auditoria        {contar(\"auditoria\")}')
"
echo
nota "A API segue no ar em ${API} — Swagger em ${API}/docs"
[ -z "$SEM_WEB" ] && nota "Dashboard em http://localhost:${PORTA_WEB} — use-o para a parte visual"
nota "Encerre com Ctrl+C quando terminar de gravar."
echo
if [ -z "$AUTO" ]; then
  echo "${AMAR}  [ENTER para encerrar a API]${FIM}"; read -r _
else
  sleep 30
fi
