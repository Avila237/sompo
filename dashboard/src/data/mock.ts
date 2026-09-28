/** Dados fictícios das telas atrás de "Em breve" (Corretor, Técnico, UBI). Nada aqui chega às telas reais. */
import type { Equipment, Client, MaintItem } from '../types'

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