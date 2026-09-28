/** Dados fictícios das telas atrás de "Em breve" (UBI · Prêmios). Nada aqui chega às telas reais. */
import type { Client } from '../types'

export const CLIENTS: Client[] = [
  { name: 'Fazenda Três Pontes', equips: 4, avg: 62, alerts: 3, premium: 'R$ 142k', delta: +8 },
  { name: 'Agropecuária São João', equips: 6, avg: 48, alerts: 1, premium: 'R$ 218k', delta: +3 },
  { name: 'SLC Agrícola', equips: 28, avg: 24, alerts: 2, premium: 'R$ 1.24M', delta: -5 },
  { name: 'Grupo Amaggi', equips: 42, avg: 30, alerts: 4, premium: 'R$ 1.82M', delta: -2 },
  { name: 'Grupo Bom Futuro', equips: 35, avg: 44, alerts: 7, premium: 'R$ 1.45M', delta: +4 },
  { name: 'Fazenda Boa Vista', equips: 8, avg: 20, alerts: 0, premium: 'R$ 265k', delta: -9 },
]
