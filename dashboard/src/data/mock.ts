import type { Equipment, Region, Contrib, Client, MaintItem, ToneKey, Tone } from '../types'

export const WTONE: Record<ToneKey, Tone> = {
  safe: { fg: '#5AE06B', bg: 'rgba(90,224,107,0.1)', ring: 'rgba(90,224,107,0.3)' },
  warn: { fg: '#FFB526', bg: 'rgba(255,181,38,0.1)', ring: 'rgba(255,181,38,0.3)' },
  crit: { fg: '#E8372E', bg: 'rgba(232,55,46,0.12)', ring: 'rgba(232,55,46,0.35)' },
  neut: { fg: '#A8AEAB', bg: 'rgba(168,174,171,0.06)', ring: 'rgba(168,174,171,0.2)' },
  info: { fg: '#6EB9FF', bg: 'rgba(110,185,255,0.08)', ring: 'rgba(110,185,255,0.25)' },
}

export function scoreBand(s: number): ToneKey {
  return s <= 33 ? 'safe' : s <= 66 ? 'warn' : 'crit'
}

export function scoreBandLabel(s: number): string {
  return s <= 33 ? 'BAIXO' : s <= 66 ? 'MÉDIO' : 'ALTO'
}

export const GROUPS: Record<string, { label: string; color: string }> = {
  env: { label: 'Ambiental', color: 'var(--blue)' },
  op: { label: 'Operador', color: 'var(--amber)' },
  maint: { label: 'Manutenção', color: 'var(--red)' },
}

export const REGIONS: Region[] = [
  { name: 'MT — Sorriso', x: 0.42, y: 0.48, count: 48, avg: 28 },
  { name: 'MT — Sinop', x: 0.43, y: 0.44, count: 32, avg: 32 },
  { name: 'GO — Rio Verde', x: 0.52, y: 0.60, count: 56, avg: 26 },
  { name: 'MS — Maracaju', x: 0.47, y: 0.70, count: 38, avg: 35 },
  { name: 'BA — Oeste', x: 0.66, y: 0.48, count: 22, avg: 72 },
  { name: 'PR — Cascavel', x: 0.52, y: 0.76, count: 34, avg: 24 },
  { name: 'RS — Passo Fundo', x: 0.50, y: 0.88, count: 18, avg: 18 },
  { name: 'MG — Triângulo', x: 0.62, y: 0.64, count: 27, avg: 30 },
  { name: 'TO — Pedro Afonso', x: 0.58, y: 0.40, count: 14, avg: 58 },
  { name: 'PI — Bom Jesus', x: 0.70, y: 0.36, count: 11, avg: 78 },
  { name: 'SP — Ribeirão', x: 0.58, y: 0.70, count: 29, avg: 22 },
  { name: 'MA — Balsas', x: 0.68, y: 0.32, count: 9, avg: 82 },
]

export const EQUIPMENT: Equipment[] = [
  { id: 'EQ-0042', model: 'John Deere 7J195', type: 'trator', op: 'OP-0015', opName: 'Mauricio Oliveira', client: 'Fazenda Três Pontes', region: 'MT — Sorriso', score: 88, trend: +12, lastAlert: '14:37 hoje', hours: 1247, maint: 'atrasada', maintPct: 38 },
  { id: 'EQ-0118', model: 'Case IH A8810', type: 'colheitadeira', op: 'OP-0027', opName: 'Ricardo Souza', client: 'Agropecuária São João', region: 'GO — Rio Verde', score: 74, trend: +6, lastAlert: '2h', hours: 3890, maint: 'em dia', maintPct: 0 },
  { id: 'EQ-0073', model: 'Massey Ferguson 75.180', type: 'trator', op: 'OP-0033', opName: 'Paulo Lima', client: 'Fazenda Três Pontes', region: 'MT — Sorriso', score: 62, trend: -3, lastAlert: '6h', hours: 720, maint: 'em dia', maintPct: 0 },
  { id: 'EQ-0095', model: 'New Holland T7.290', type: 'trator', op: 'OP-0041', opName: 'Ana Beatriz', client: 'Grupo Bom Futuro', region: 'MT — Sinop', score: 54, trend: +2, lastAlert: '1d', hours: 2140, maint: 'em dia', maintPct: 0 },
  { id: 'EQ-0011', model: 'John Deere S790', type: 'colheitadeira', op: 'OP-0008', opName: 'Fernando Pires', client: 'Agropecuária São João', region: 'GO — Rio Verde', score: 48, trend: -8, lastAlert: '—', hours: 4520, maint: 'atrasada', maintPct: 22 },
  { id: 'EQ-0156', model: 'Jumil JM-1440', type: 'implemento', op: 'OP-0052', opName: 'Eduardo Magno', client: 'SLC Agrícola', region: 'MS — Maracaju', score: 38, trend: -4, lastAlert: '—', hours: 980, maint: 'em dia', maintPct: 0 },
  { id: 'EQ-0204', model: 'John Deere 7J195', type: 'trator', op: 'OP-0061', opName: 'Roberto Ferrari', client: 'SLC Agrícola', region: 'MS — Maracaju', score: 32, trend: -2, lastAlert: '—', hours: 1567, maint: 'em dia', maintPct: 0 },
  { id: 'EQ-0089', model: 'New Holland CR10.90', type: 'colheitadeira', op: 'OP-0044', opName: 'Tiago Moraes', client: 'Grupo Amaggi', region: 'MT — Sorriso', score: 28, trend: 0, lastAlert: '—', hours: 2890, maint: 'em dia', maintPct: 0 },
  { id: 'EQ-0167', model: 'Baldan BFNT-15', type: 'implemento', op: 'OP-0058', opName: 'Juliana Prado', client: 'Fazenda Três Pontes', region: 'MT — Sorriso', score: 22, trend: -1, lastAlert: '—', hours: 840, maint: 'em dia', maintPct: 0 },
  { id: 'EQ-0182', model: 'Marchesan CAP-7', type: 'implemento', op: 'OP-0066', opName: 'Carlos Eduardo', client: 'Fazenda Boa Vista', region: 'PR — Cascavel', score: 18, trend: -2, lastAlert: '—', hours: 420, maint: 'em dia', maintPct: 0 },
  { id: 'EQ-0057', model: 'John Deere 7J195', type: 'trator', op: 'OP-0029', opName: 'Alex Monteiro', client: 'Grupo Amaggi', region: 'MT — Sinop', score: 64, trend: +4, lastAlert: '4h', hours: 1890, maint: 'atrasada', maintPct: 15 },
  { id: 'EQ-0023', model: 'Massey Ferguson 75.180', type: 'trator', op: 'OP-0019', opName: 'Renata Silva', client: 'Grupo Bom Futuro', region: 'BA — Oeste', score: 78, trend: +9, lastAlert: '8h', hours: 3120, maint: 'atrasada', maintPct: 28 },
]

export const CONTRIBS: Contrib[] = [
  { label: 'Vento em altitude acima do limite', group: 'env', pct: 34, val: '+22 pts' },
  { label: 'Temperatura do motor 98°C', group: 'op', pct: 22, val: '+14 pts' },
  { label: 'Atraso de troca de filtros (38%)', group: 'maint', pct: 18, val: '+12 pts' },
  { label: 'Operador fadigado (9h sem pausa)', group: 'op', pct: 14, val: '+9 pts' },
  { label: 'Inclinação média 6.1%', group: 'env', pct: 12, val: '+8 pts' },
]

export const HISTORY: number[] = Array.from({ length: 30 }, (_, i) => {
  const base = 28 - Math.sin(i * 0.4) * 6 + (i > 22 ? (i - 22) * 4 : 0)
  return Math.max(5, Math.min(85, base + (Math.random() - 0.5) * 4))
})

export const CLIENTS: Client[] = [
  { name: 'Fazenda Três Pontes', equips: 4, avg: 62, alerts: 3, premium: 'R$ 142k', delta: +8 },
  { name: 'Agropecuária São João', equips: 6, avg: 48, alerts: 1, premium: 'R$ 218k', delta: +3 },
  { name: 'SLC Agrícola', equips: 28, avg: 24, alerts: 2, premium: 'R$ 1.24M', delta: -5 },
  { name: 'Grupo Amaggi', equips: 42, avg: 30, alerts: 4, premium: 'R$ 1.82M', delta: -2 },
  { name: 'Grupo Bom Futuro', equips: 35, avg: 44, alerts: 7, premium: 'R$ 1.45M', delta: +4 },
  { name: 'Fazenda Boa Vista', equips: 8, avg: 20, alerts: 0, premium: 'R$ 265k', delta: -9 },
]

export const MAINT_QUEUE: MaintItem[] = [
  { id: 'EQ-0042', item: 'Troca filtros hidráulicos', due: '53h atrás', pct: 38, sev: 'crit' },
  { id: 'EQ-0023', item: 'Revisão 500h', due: '28h atrás', pct: 28, sev: 'crit' },
  { id: 'EQ-0011', item: 'Troca óleo motor', due: '14h atrás', pct: 22, sev: 'warn' },
  { id: 'EQ-0057', item: 'Calibração injetores', due: '9h atrás', pct: 15, sev: 'warn' },
  { id: 'EQ-0095', item: 'Inspeção rodados', due: 'em 6h', pct: 0, sev: 'safe' },
  { id: 'EQ-0118', item: 'Limpeza filtros ar', due: 'em 12h', pct: 0, sev: 'safe' },
]