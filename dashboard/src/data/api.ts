/**
 * Camada de dados do dashboard.
 *
 * Fala exclusivamente com a API do backend (FastAPI). O SDK do Supabase saiu
 * do caminho de dados: nenhuma chave de banco chega ao browser (RF-07).
 *
 * Contrato: `docs/contrato-api.md` · Swagger: `${VITE_API_BASE_URL}/docs`.
 */

import { apiGet, apiPostPublico } from '../lib/apiClient'
import { setSessao, limparSessao } from '../lib/auth'
import type { Equipment, Region, ToneKey } from '../types'

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
 * A API e a fonte da faixa (`derive_faixa` no backend). Os limiares sao os
 * mesmos do `scoreBand` do frontend (<=33 baixo, <=66 medio, senao alto),
 * entao a migracao nao muda nenhuma classificacao ja exibida.
 */
export function faixaToTone(faixa: string): ToneKey {
  return faixa === 'baixo' ? 'safe' : faixa === 'medio' ? 'warn' : 'crit'
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
  operador_id: string
  ultima_avaliacao: string | null
  latitude: number
  longitude: number
}

/** Uma linha por equipamento, ja agregada pelo servidor. */
export interface EquipamentoView {
  id: string
  modelo: string
  tipo: 'trator' | 'colheitadeira' | 'implemento'
  idade: number
  sinistros: number
  iot: boolean
  score: number       // score da avaliacao mais recente (arredondado)
  scoreMedio: number  // media das avaliacoes do equipamento
  trend: number       // ultima avaliacao - penultima
  faixa: ToneKey
  avaliacoes: number
  operador: string
  ultimaTs: string
  lat: number
  lon: number
}

function toView(e: EquipamentoItemResp): EquipamentoView {
  return {
    id: e.equipamento_id,
    modelo: e.modelo_equipamento,
    tipo: e.tipo_equipamento,
    idade: e.idade_equipamento,
    sinistros: e.historico_sinistros,
    iot: e.tem_iot,
    score: Math.round(e.risco_score),
    scoreMedio: Math.round(e.score_medio),
    trend: Math.round(e.tendencia),
    faixa: faixaToTone(e.faixa_risco),
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
 */
export async function loadEquipamentos(): Promise<EquipamentoView[]> {
  const r = await apiGet<{ total: number; itens: EquipamentoItemResp[] }>('/equipamentos')
  return r.itens.map(toView)
}

/* ── GET /kpis + GET /alertas ─────────────────────────────── */

export interface Kpis {
  totalEquip: number
  totalAval: number
  scoreMedio: number
  riscoAlto: number
  pctRiscoAlto: number
  /** Ausente enquanto a API nao expuser `total_operadores` — ver nota abaixo. */
  operadores: number | null
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
  equipamentoId: string
}

export interface VisaoGeral {
  kpis: Kpis
  porOperacao: OperacaoAgg[]
  regioes: Region[]
  alertas: Alerta[]
  /**
   * Serie de media diaria de score. `null` enquanto a API nao devolver
   * `tendencia` em GET /kpis — a Visao geral esconde o grafico nesse caso em
   * vez de exibir dado vazio. Ver "Pendencias de contrato" no PR.
   */
  tendencia: number[] | null
}

interface KpisResp {
  kpis: {
    total_equipamentos: number
    total_avaliacoes: number
    score_medio: number
    equipamentos_risco_alto: number
    pct_risco_alto: number
    avaliacoes_por_faixa: Record<string, number>
    total_operadores?: number
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
  /** Campo aditivo ainda nao implementado no backend. */
  tendencia?: Array<{ dia: string; score_medio: number }>
}

interface AlertaResp {
  avaliacao_id: number
  equipamento_id: string
  operador_id: string
  risco_score: number
  faixa_risco: string
  tipo_operacao: string
  timestamp: string
  mensagem: string
}

function horaLocal(ts: string): string {
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return '--:--'
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/**
 * Carrega tudo que a Visao geral precisa em duas requisicoes paralelas.
 *
 * @param dias janela da serie de tendencia; repassada como `?dias=` para o
 *   momento em que a API implementar o campo. Parametro desconhecido e
 *   ignorado pelo FastAPI, entao nao quebra hoje.
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
      operadores: k.kpis.total_operadores ?? null,
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
    alertas: a.itens.map((it) => ({
      sev: faixaToTone(it.faixa_risco),
      msg: it.mensagem,
      time: horaLocal(it.timestamp),
      equipamentoId: it.equipamento_id,
    })),
    tendencia: k.tendencia ? k.tendencia.map((p) => p.score_medio) : null,
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
  tipo_operacao: string
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

/* ── Adapta EquipamentoView ao tipo Equipment (tela Detalhe) ─ */

export function toEquipment(v: EquipamentoView): Equipment {
  return {
    id: v.id,
    model: v.modelo,
    type: v.tipo,
    op: v.operador,
    opName: v.operador,
    client: '—',
    region: v.ultimaTs ? `${Math.abs(v.lat).toFixed(1)}°S ${Math.abs(v.lon).toFixed(1)}°O` : '—',
    score: v.score,
    trend: v.trend,
    lastAlert: v.ultimaTs ? new Date(v.ultimaTs).toLocaleDateString('pt-BR') : '—',
    hours: 0,
    maint: 'em dia',
    maintPct: 0,
  }
}

/* ── Decomposicao SHAP por grupo ──────────────────────────── */

export interface GrupoShap {
  group: string
  label: string
  color: string
  value: number // soma COM SINAL dos shap_value do grupo
}

export const SHAP_GROUP_META: Record<string, { label: string; color: string }> = {
  ambiental:   { label: 'Ambiental',   color: '#6EB9FF' },
  geografico:  { label: 'Geográfico',  color: '#5AE06B' },
  operacional: { label: 'Operacional', color: '#A78BFA' },
  equipamento: { label: 'Equipamento', color: '#34D3C0' },
  operador:    { label: 'Operador',    color: '#FFB526' },
  manutencao:  { label: 'Manutenção',  color: '#E8372E' },
}

export const FEATURE_LABELS: Record<string, string> = {
  temperatura_ar: 'Temperatura do ar',
  precipitacao_mm: 'Precipitação (24h)',
  umidade_solo: 'Umidade do solo',
  velocidade_vento: 'Velocidade do vento',
  condicao_clima: 'Condição climática',
  latitude: 'Latitude',
  longitude: 'Longitude',
  tipo_solo: 'Tipo de solo',
  distancia_agua_m: 'Distância de corpo d’água',
  declividade: 'Declividade do terreno',
  tipo_operacao: 'Tipo de operação',
  velocidade_kmh: 'Velocidade de deslocamento',
  vibracao_g: 'Vibração',
  temperatura_motor: 'Temperatura do motor',
  horas_operacao: 'Horas de operação',
  horario_operacao: 'Horário da operação',
  tipo_equipamento: 'Tipo de equipamento',
  idade_equipamento: 'Idade do equipamento',
  historico_sinistros: 'Histórico de sinistros',
  tem_iot: 'Possui IoT',
  pct_velocidade_acima_recomendada: 'Velocidade acima do recomendado',
  freq_eventos_bruscos: 'Eventos bruscos',
  pct_operacoes_noturnas: 'Operações noturnas',
  score_operador_historico: 'Score histórico do operador',
  ultima_manutencao_dias: 'Dias desde última manutenção',
  ultima_manutencao_horas_op: 'Horas desde última manutenção',
  intervalo_manut_recomendado_dias: 'Intervalo recomendado (dias)',
  intervalo_manut_recomendado_horas: 'Intervalo recomendado (horas)',
  manutencao_atrasada: 'Manutenção atrasada',
  atraso_manutencao_pct: 'Atraso de manutenção',
}

export function featureLabel(f: string): string {
  return FEATURE_LABELS[f] ?? f
}

/**
 * Soma os SHAP por grupo preservando o sinal: positivo aumenta o risco,
 * negativo reduz. Difere de `group_contributions()` do backend, que soma
 * |SHAP| para medir magnitude — a semantica com sinal e a que o
 * DivergingBar exibe.
 */
export function aggregateShapByGroup(factors: ShapFactor[]): GrupoShap[] {
  const sums = new Map<string, number>()
  for (const f of factors) {
    sums.set(f.grupo, (sums.get(f.grupo) ?? 0) + Number(f.shap_value))
  }
  return [...sums.entries()]
    .map(([group, value]) => ({
      group,
      label: SHAP_GROUP_META[group]?.label ?? group,
      color: SHAP_GROUP_META[group]?.color ?? '#A8AEAB',
      value,
    }))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
}
