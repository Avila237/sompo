export type ToneKey = 'safe' | 'warn' | 'crit' | 'neut' | 'info'

export interface Tone {
  fg: string
  bg: string
  ring: string
}

export interface Equipment {
  id: string
  model: string
  type: 'trator' | 'colheitadeira' | 'implemento'
  op: string
  opName: string
  client: string
  region: string
  score: number
  trend: number
  lastAlert: string
  hours: number
  maint: 'atrasada' | 'em dia'
  maintPct: number
}

export interface Region {
  name: string
  x: number
  y: number
  count: number
  avg: number
}

export interface Contrib {
  label: string
  group: 'env' | 'op' | 'maint'
  pct: number
  val: string
}

export interface Client {
  name: string
  equips: number
  avg: number
  alerts: number
  premium: string
  delta: number
}

export interface MaintItem {
  id: string
  item: string
  due: string
  pct: number
  sev: ToneKey
}