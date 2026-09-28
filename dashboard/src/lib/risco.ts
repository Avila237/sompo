/**
 * Tons e faixas de risco usados pelas telas reais.
 *
 * Score de UMA avaliação/equipamento: use a `faixa_risco` que a API devolve
 * (`faixaToTone` em data/api.ts + `rotuloDaFaixa`). Nunca reclassifique: a faixa
 * vem do score cru e o score devolvido tem duas casas — 33,004 volta como 33.0
 * com faixa "medio" (contrato-api.md, armadilha 4).
 *
 * `faixaDaMedia` / `rotuloDaMedia` existem só para MÉDIAS agregadas (KPIs,
 * regiões, operações, séries), que não têm faixa gravada. Limiares iguais ao
 * `derive_faixa` do backend: <=33 baixo, <=66 medio, senao alto.
 */
import type { ToneKey, Tone } from '../types'

export const WTONE: Record<ToneKey, Tone> = {
  safe: { fg: '#5AE06B', bg: 'rgba(90,224,107,0.1)', ring: 'rgba(90,224,107,0.3)' },
  warn: { fg: '#FFB526', bg: 'rgba(255,181,38,0.1)', ring: 'rgba(255,181,38,0.3)' },
  crit: { fg: '#E8372E', bg: 'rgba(232,55,46,0.12)', ring: 'rgba(232,55,46,0.35)' },
  neut: { fg: '#A8AEAB', bg: 'rgba(168,174,171,0.06)', ring: 'rgba(168,174,171,0.2)' },
  info: { fg: '#6EB9FF', bg: 'rgba(110,185,255,0.08)', ring: 'rgba(110,185,255,0.25)' },
}

export function faixaDaMedia(s: number): ToneKey {
  return s <= 33 ? 'safe' : s <= 66 ? 'warn' : 'crit'
}

export function rotuloDaMedia(s: number): string {
  return s <= 33 ? 'BAIXO' : s <= 66 ? 'MÉDIO' : 'ALTO'
}

/**
 * Rótulo da faixa que a API devolveu (já convertida em tom). Tom neutro = faixa
 * ausente numa avaliação que existe; equipamento SEM avaliação usa SEM_AVALIACAO.
 */
export function rotuloDaFaixa(tone: ToneKey): string {
  return tone === 'safe' ? 'BAIXO' : tone === 'warn' ? 'MÉDIO' : tone === 'crit' ? 'ALTO' : 'SEM FAIXA'
}

/** Rótulo de equipamento sem nenhuma avaliação — nunca exibir como score 0 / "baixo". */
export const SEM_AVALIACAO = 'SEM AVALIAÇÃO'
