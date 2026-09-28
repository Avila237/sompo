/**
 * Metadados e agregacao dos fatores SHAP exibidos no Detalhe.
 * Separado de api.ts: aqui nao ha chamada de rede, so apresentacao.
 */

import type { ShapFactor } from './api'

/* ── Decomposicao SHAP por grupo ──────────────────────────── */

export interface GrupoShap {
  group: string
  label: string
  color: string
  value: number // soma COM SINAL dos shap_value do grupo
}

export const SHAP_GROUP_META: Record<string, { label: string; color: string }> = {
  ambiental:   { label: 'Ambiental',   color: 'var(--blue)' },
  geografico:  { label: 'Geográfico',  color: 'var(--green)' },
  operacional: { label: 'Operacional', color: '#A78BFA' },
  equipamento: { label: 'Equipamento', color: '#34D3C0' },
  operador:    { label: 'Operador',    color: 'var(--amber)' },
  manutencao:  { label: 'Manutenção',  color: 'var(--red)' },
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
  return paraGrupos([...sums.entries()])
}

/**
 * Decomposicao por grupo de uma predicao. Usa a gravada pela API, a soma dos
 * 30 SHAP, identica a do POST que gerou a predicao (S4-15). As predicoes do
 * seed, anteriores a essa coluna, vem sem ela e caem na soma dos top 5, que e
 * so uma aproximacao.
 */
export function gruposDaPredicao(p: {
  top_fatores_shap: ShapFactor[]
  contribuicoes_por_grupo?: Record<string, number> | null
}): GrupoShap[] {
  return p.contribuicoes_por_grupo
    ? paraGrupos(Object.entries(p.contribuicoes_por_grupo))
    : aggregateShapByGroup(p.top_fatores_shap)
}

function paraGrupos(somas: [string, number][]): GrupoShap[] {
  return somas
    .map(([group, value]) => ({
      group,
      label: SHAP_GROUP_META[group]?.label ?? group,
      color: SHAP_GROUP_META[group]?.color ?? 'var(--fg-dim)',
      value,
    }))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
}
