/** Formatação de datas exibidas no dashboard (pt-BR). Entrada vazia ou inválida vira "—". */

function parse(ts: string): Date | null {
  if (!ts) return null
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? null : d
}

/** "18/11/2025" */
export function fmtData(ts: string): string {
  return parse(ts)?.toLocaleDateString('pt-BR') ?? '—'
}

/** "18/11/2025, 10:49" */
export function fmtDataHora(ts: string): string {
  return parse(ts)?.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) ?? '—'
}

/** "2025-12-28" → "28/12/25", sem passar por Date para não deslocar o dia pelo fuso */
export function fmtDiaIso(dia: string): string {
  const [a, m, d] = dia.split('-')
  return a && m && d ? `${d}/${m}/${a.slice(2)}` : dia
}
