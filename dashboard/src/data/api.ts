/**
 * Camada de dados do dashboard.
 *
 * Fala exclusivamente com a API do backend (FastAPI). O SDK do Supabase saiu
 * do caminho de dados: nenhuma chave de banco chega ao browser (RF-07).
 *
 * Contrato: `docs/contrato-api.md` · Swagger: `${VITE_API_BASE_URL}/docs`.
 */

import { apiGet, apiPostPublico } from '../lib/apiClient'
import { setSessao, limparSessao, assinarSessao } from '../lib/auth'
import type { Region, ToneKey } from '../types'

/* ── Autenticacao ─────────────────────────────────────────── */

interface TokenResp {
  access_token: string
  token_type: string
  perfil: string
  expira_em_minutos: number
}

/** POST /auth/token — emite o JWT e abre a sessao. */
export async function login(usuario: string, senha: string): Promise<void> {
  const r = await apiPostPublico<TokenResp>('/auth/token', { usuario, senha })
  setSessao({
    token: r.access_token,
    perfil: r.perfil,
    expiraEm: Date.now() + r.expira_em_minutos * 60_000,
  })
}

export function logout(): void {
  limparSessao()
}

/* ── Faixa de risco ───────────────────────────────────────── */

/**
 * A API e a unica fonte da faixa de uma avaliacao (`derive_faixa` no backend,
 * sobre o score cru). O cliente converte em tom, nunca reclassifica.
 */
export function faixaToTone(faixa: string | null | undefined): ToneKey {
  if (faixa === 'baixo') return 'safe'
  if (faixa === 'medio') return 'warn'
  if (faixa === 'alto') return 'crit'
  // Faixa nula ou desconhecida é ausência de dado: neutro ("SEM AVALIAÇÃO"), nunca ALTO
  return 'neut'
}

/* ── GET /equipamentos ────────────────────────────────────── */

interface EquipamentoItemResp {
  equipamento_id: string
  modelo_equipamento: string
  tipo_equipamento: 'trator' | 'colheitadeira' | 'implemento'
  idade_equipamento: number
  historico_sinistros: number
  tem_iot: boolean
  risco_score: number
  score_medio: number
  faixa_risco: string
  tendencia: number
  total_avaliacoes: number
  // contrato: os quatro vêm null em equipamento sem avaliacao
  operador_id: string | null
  ultima_avaliacao: string | null
  latitude: number | null
  longitude: number | null
}

/** Uma linha por equipamento, ja agregada pelo servidor. */
export interface EquipamentoView {
  id: string
  modelo: string
  tipo: 'trator' | 'colheitadeira' | 'implemento'
  idade: number
  sinistros: number
  iot: boolean
  score: number | null // score da avaliacao mais recente; null = sem avaliacao
  scoreMedio: number   // media das avaliacoes do equipamento
  trend: number        // ultima avaliacao - penultima
  faixa: ToneKey       // 'neut' quando sem avaliacao
  avaliacoes: number
  operador: string
  ultimaTs: string
  lat: number | null
  lon: number | null
}

function toView(e: EquipamentoItemResp): EquipamentoView {
  // A API devolve score 0.0 e faixa "baixo" para equipamento sem avaliacao
  // (contrato-api.md, GET /equipamentos). Ausencia de dado nao e risco baixo.
  const semAvaliacao = e.total_avaliacoes === 0
  return {
    id: e.equipamento_id,
    modelo: e.modelo_equipamento,
    tipo: e.tipo_equipamento,
    idade: e.idade_equipamento,
    sinistros: e.historico_sinistros,
    iot: e.tem_iot,
    score: semAvaliacao ? null : e.risco_score, // 2 casas, como a API devolve; arredondar so na exibicao
    scoreMedio: Math.round(e.score_medio),
    trend: Math.round(e.tendencia),
    faixa: semAvaliacao ? 'neut' : faixaToTone(e.faixa_risco),
    avaliacoes: e.total_avaliacoes,
    operador: e.operador_id || '—',
    ultimaTs: e.ultima_avaliacao ?? '',
    lat: e.latitude,
    lon: e.longitude,
  }
}

/**
 * Busca os 200 equipamentos de uma vez. Filtro, busca e ordenacao seguem no
 * cliente: a lista e pequena, a interacao fica instantanea e a busca por
 * operador (que o parametro `busca` da API nao cobre) continua funcionando.
 *
 * App (contador do menu), Visao geral e Ranking pedem a mesma lista; a promessa
 * fica guardada por EQUIP_TTL_MS para as tres telas dividirem uma requisicao.
 * Falha nao fica em cache, e troca de sessao limpa tudo.
 */
const EQUIP_TTL_MS = 60_000
let equipCache: { promessa: Promise<EquipamentoView[]>; em: number } | null = null

assinarSessao(() => { equipCache = null })

export function loadEquipamentos(opts: { recarregar?: boolean } = {}): Promise<EquipamentoView[]> {
  if (!opts.recarregar && equipCache && Date.now() - equipCache.em < EQUIP_TTL_MS) {
    return equipCache.promessa
  }
  const promessa = apiGet<{ total: number; itens: EquipamentoItemResp[] }>('/equipamentos')
    .then((r) => r.itens.map(toView))
  const entrada = { promessa, em: Date.now() }
  equipCache = entrada
  promessa.catch(() => { if (equipCache === entrada) equipCache = null })
  return promessa
}

/* ── GET /kpis + GET /alertas ─────────────────────────────── */

export interface Kpis {
  totalEquip: number
  totalAval: number
  scoreMedio: number
  riscoAlto: number
  pctRiscoAlto: number
  operadores: number // operadores distintos nas avaliacoes
}

/** Ponto da serie diaria. So existem dias COM dados — ver `tendencia` no contrato. */
export interface TendenciaPonto {
  dia: string // YYYY-MM-DD
  score: number
  avaliacoes: number
}

/** Agregacao por tipo de operacao — terceiro eixo exigido pelo RF-09. */
export interface OperacaoAgg {
  tipo: string
  avaliacoes: number
  scoreMedio: number
  riscoAlto: number
}

export interface Alerta {
  sev: ToneKey
  msg: string
  time: string
  ts: string // timestamp ISO da avaliacao que gerou o alerta
  equipamentoId: string
}

export interface VisaoGeral {
  kpis: Kpis
  porOperacao: OperacaoAgg[]
  regioes: Region[]
  alertas: Alerta[]
  tendencia: TendenciaPonto[]
}

interface KpisResp {
  kpis: {
    total_equipamentos: number
    total_avaliacoes: number
    score_medio: number
    equipamentos_risco_alto: number
    pct_risco_alto: number
    avaliacoes_por_faixa: Record<string, number>
    total_operadores: number
  }
  por_operacao: Array<{
    tipo_operacao: string
    total_avaliacoes: number
    score_medio: number
    avaliacoes_risco_alto: number
  }>
  por_regiao: Array<{
    nome: string
    latitude: number
    longitude: number
    x: number
    y: number
    total_equipamentos: number
    score_medio: number
  }>
  tendencia: Array<{ dia: string; score_medio: number; avaliacoes: number }>
}

interface AlertaResp {
  avaliacao_id: number
  equipamento_id: string
  operador_id: string
  risco_score: number
  faixa_risco: string
  tipo_operacao: string | null // contrato: null se a avaliacao nao tiver o campo
  timestamp: string
  mensagem: string
}

function horaLocal(ts: string): string {
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return '--:--'
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function toAlerta(it: AlertaResp): Alerta {
  return {
    sev: faixaToTone(it.faixa_risco),
    msg: it.mensagem,
    time: horaLocal(it.timestamp),
    ts: it.timestamp,
    equipamentoId: it.equipamento_id,
  }
}

/** GET /alertas — alertas reais derivados do score (regra no servidor). */
export async function loadAlertas(): Promise<Alerta[]> {
  const r = await apiGet<{ total: number; itens: AlertaResp[] }>('/alertas')
  return r.itens.map(toAlerta)
}

/**
 * Carrega tudo que a Visao geral precisa em duas requisicoes paralelas.
 *
 * @param dias janela da serie `tendencia`, em dias COM dados (nao corridos).
 */
export async function loadVisaoGeral(dias: number): Promise<VisaoGeral> {
  const [k, a] = await Promise.all([
    apiGet<KpisResp>('/kpis', { dias }),
    apiGet<{ total: number; itens: AlertaResp[] }>('/alertas'),
  ])

  return {
    kpis: {
      totalEquip: k.kpis.total_equipamentos,
      totalAval: k.kpis.total_avaliacoes,
      scoreMedio: Math.round(k.kpis.score_medio),
      riscoAlto: k.kpis.equipamentos_risco_alto,
      pctRiscoAlto: k.kpis.pct_risco_alto,
      operadores: k.kpis.total_operadores,
    },
    porOperacao: k.por_operacao.map((o) => ({
      tipo: o.tipo_operacao,
      avaliacoes: o.total_avaliacoes,
      scoreMedio: Math.round(o.score_medio),
      riscoAlto: o.avaliacoes_risco_alto,
    })),
    regioes: k.por_regiao.map((r) => ({
      name: r.nome,
      x: r.x,
      y: r.y,
      count: r.total_equipamentos,
      avg: Math.round(r.score_medio),
    })),
    alertas: a.itens.map(toAlerta),
    // Mantem `dia`: descarta-lo fazia o eixo rotular "N d" quando os pontos
    // podem cobrir meses (so ha pontos em dias com dados)
    tendencia: k.tendencia.map((p) => ({ dia: p.dia, score: p.score_medio, avaliacoes: p.avaliacoes })),
  }
}

/* ── GET /equipamentos/{id} ───────────────────────────────── */

export interface EquipamentoRow {
  equipamento_id: string
  tipo_equipamento: 'trator' | 'colheitadeira' | 'implemento'
  modelo_equipamento: string
  categoria_manual: string
  idade_equipamento: number
  historico_sinistros: number
  tem_iot: boolean
  intervalo_manut_recomendado_dias: number
  intervalo_manut_recomendado_horas: number
}

/**
 * Fator SHAP como a API devolve.
 *
 * O banco tem dois formatos gravados — as 5.000 predicoes do seed usam
 * `group` (ingles) e nao gravaram `valor`; as geradas pela API usam `grupo`.
 * A API normaliza na leitura e sempre entrega o formato em portugues, por
 * isso aqui so existe `grupo`. `valor` e opcional porque vem nulo no seed.
 */
export interface ShapFactor {
  feature: string
  grupo: string
  shap_value: number
  valor?: number | null
}

export interface PredicaoRow {
  avaliacao_id: number
  risco_score_predito: number
  faixa_predita: string
  top_fatores_shap: ShapFactor[]
  modelo_versao: string
}

export interface AvaliacaoFull {
  avaliacao_id: number
  equipamento_id: string
  operador_id: string
  timestamp: string
  temperatura_ar: number
  precipitacao_mm: number
  umidade_solo: number
  velocidade_vento: number
  condicao_clima: string
  latitude: number
  longitude: number
  tipo_solo: string
  distancia_agua_m: number
  declividade: number
  tipo_operacao: string | null // contrato: pode faltar na avaliacao
  velocidade_kmh: number
  vibracao_g: number | null
  temperatura_motor: number | null
  horas_operacao: number
  horario_operacao: number
  pct_velocidade_acima_recomendada: number
  freq_eventos_bruscos: number
  pct_operacoes_noturnas: number
  score_operador_historico: number
  ultima_manutencao_dias: number
  ultima_manutencao_horas_op: number
  manutencao_atrasada: boolean
  atraso_manutencao_pct: number
  risco_score: number
  faixa_risco: string
}

export interface HistPoint {
  ts: string
  score: number
}

export interface EquipamentoDetail {
  equipamento: EquipamentoRow
  ultima: AvaliacaoFull | null
  predicao: PredicaoRow | null
  historico: HistPoint[]
}

interface DetalheResp {
  equipamento: EquipamentoRow
  ultima_avaliacao: AvaliacaoFull | null
  predicao: PredicaoRow | null
  historico: Array<{ timestamp: string; risco_score: number }>
}

export async function loadEquipamentoDetail(id: string): Promise<EquipamentoDetail> {
  const r = await apiGet<DetalheResp>(`/equipamentos/${encodeURIComponent(id)}`)
  return {
    equipamento: r.equipamento,
    ultima: r.ultima_avaliacao,
    predicao: r.predicao,
    historico: (r.historico ?? []).map((h) => ({ ts: h.timestamp, score: h.risco_score })),
  }
}
