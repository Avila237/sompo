/**
 * Tons e faixas de risco usados pelas telas reais.
 * Limiares iguais ao `derive_faixa` do backend: <=33 baixo, <=66 medio, senao alto.
 */
import type { ToneKey, Tone } from '../types'

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

/** Rótulo de equipamento sem nenhuma avaliação — nunca exibir como score 0 / "baixo". */
export const SEM_AVALIACAO = 'SEM AVALIAÇÃO'
