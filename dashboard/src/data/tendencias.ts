/**
 * GET /tendencias — série de score por grupo nos três eixos (BRA-459).
 * Contrato: `docs/contrato-api.md`, seção GET /tendencias.
 */

import { apiGet } from '../lib/apiClient'

export type Eixo = 'equipamento' | 'regiao' | 'operacao'

export interface PontoTendencia {
  dia: string // YYYY-MM-DD
  score: number
  avaliacoes: number
}

export interface SerieTendencia {
  chave: string
  rotulo: string
  scoreMedio: number // média do grupo NA JANELA (vem da API)
  avaliacoes: number
  pontos: PontoTendencia[] // só dias em que o grupo tem avaliação: lacuna, nunca zero
}

export interface Tendencias {
  eixo: Eixo
  dias: number
  /** Eixo X comum a todas as séries, em ordem crescente. */
  datas: string[]
  series: SerieTendencia[]
}

interface TendenciasResp {
  eixo: Eixo
  dias: number
  janela: { inicio: string | null; fim: string | null; dias_com_dados: number; datas?: string[] }
  series: Array<{
    chave: string
    rotulo: string
    score_medio: number
    avaliacoes: number
    pontos: Array<{ dia: string; score_medio: number; avaliacoes: number }>
  }>
}

export async function loadTendencias(eixo: Eixo, dias: number, limite = 5): Promise<Tendencias> {
  const r = await apiGet<TendenciasResp>('/tendencias', { eixo, dias, limite })
  const series = r.series.map((s) => ({
    chave: s.chave,
    rotulo: s.rotulo,
    scoreMedio: s.score_medio,
    avaliacoes: s.avaliacoes,
    pontos: s.pontos.map((p) => ({ dia: p.dia, score: p.score_medio, avaliacoes: p.avaliacoes })),
  }))
  // `janela.datas` entrou depois da primeira versão da rota. Contra uma API sem o
  // campo, o eixo cai para a união dos dias das séries — pode pular dias da
  // janela, mas nunca inventa ponto.
  const datas = r.janela.datas
    ?? [...new Set(series.flatMap((s) => s.pontos.map((p) => p.dia)))].sort()
  return { eixo: r.eixo, dias: r.dias, datas, series }
}
