export type ToneKey = 'safe' | 'warn' | 'crit' | 'neut' | 'info'

export interface Tone {
  fg: string
  bg: string
  ring: string
}

export interface Region {
  name: string
  x: number
  y: number
  count: number
  avg: number
}

export interface Client {
  name: string
  equips: number
  avg: number
  alerts: number
  premium: string
  delta: number
}
