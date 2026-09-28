/**
 * Cliente HTTP da API do backend (FastAPI).
 *
 * Substitui o SDK do Supabase no caminho de dados: o browser nao fala mais com
 * o banco. Contrato em `docs/contrato-api.md`; Swagger em `/docs` com a API no ar.
 *
 * Todas as rotas exigem `Authorization: Bearer <token>`, exceto `POST /auth/token`
 * e `GET /health`.
 */

import { getToken, limparSessao } from './auth'

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ?? ''

/** Sem limite, uma API travada deixava a tela em "Carregando…" para sempre. */
const TIMEOUT_MS = 15_000

/** Erro de API com o status HTTP preservado, para o chamador decidir o que fazer. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function exigirBase(): string {
  if (!BASE) {
    throw new ApiError(
      0,
      'VITE_API_BASE_URL nao definida. Crie dashboard/.env.local com ' +
        'VITE_API_BASE_URL=http://localhost:8000 e reinicie o servidor do Vite.',
    )
  }
  return BASE
}

/** Extrai `detail` do corpo de erro do FastAPI, com fallback legivel. */
async function mensagemDeErro(res: Response): Promise<string> {
  try {
    const corpo = await res.json()
    const detail = (corpo as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    // 422 do Pydantic: detail e uma lista de {loc, msg}
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const campo = Array.isArray(d?.loc) ? d.loc.filter((p: unknown) => p !== 'body').join('.') : ''
          return campo ? `${campo}: ${d?.msg}` : String(d?.msg ?? '')
        })
        .filter(Boolean)
        .join(' · ')
    }
  } catch {
    // corpo vazio ou nao-JSON: cai no fallback
  }
  return `${res.status} ${res.statusText}`.trim()
}

async function requisitar<T>(caminho: string, init: RequestInit, autenticado: boolean): Promise<T> {
  const base = exigirBase()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')

  if (autenticado) {
    const token = getToken()
    if (!token) throw new ApiError(401, 'Sessao ausente ou expirada. Faca login novamente.')
    headers.set('Authorization', `Bearer ${token}`)
  }

  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  let res: Response
  try {
    res = await fetch(`${base}${caminho}`, { ...init, headers, signal: ctrl.signal })
  } catch (e) {
    // Falha de rede, CORS, backend fora do ar ou timeout. Nao e engolida: vira
    // erro com status 0 para a interface distinguir de erro HTTP.
    const motivo = ctrl.signal.aborted
      ? `a API nao respondeu em ${TIMEOUT_MS / 1000} s.`
      : (e as Error).message
    throw new ApiError(0, `Nao foi possivel falar com a API em ${base}: ${motivo}`)
  } finally {
    clearTimeout(timer)
  }

  if (res.status === 401) {
    // Token invalido ou expirado: derruba a sessao para a interface voltar ao
    // login, marcando o motivo para a tela de login explicar o que houve.
    const msg = await mensagemDeErro(res)
    if (autenticado) limparSessao('expirada')
    throw new ApiError(401, msg)
  }
  if (!res.ok) throw new ApiError(res.status, await mensagemDeErro(res))
  if (res.status === 204) return undefined as T

  return lerJson<T>(res)
}

/**
 * Le o corpo como JSON. Um 200 com HTML (proxy, pagina de erro do servidor,
 * VITE_API_BASE_URL apontando para o lugar errado) virava "Unexpected token '<'"
 * na tela; aqui vira mensagem que diz o que aconteceu.
 */
async function lerJson<T>(res: Response): Promise<T> {
  const tipo = res.headers.get('Content-Type') ?? ''
  if (!tipo.includes('application/json')) {
    throw new ApiError(res.status, `Resposta inesperada da API (${tipo || 'sem Content-Type'}), esperado JSON.`)
  }
  try {
    return (await res.json()) as T
  } catch {
    throw new ApiError(res.status, 'A API devolveu um JSON invalido.')
  }
}

type Params = Record<string, string | number | undefined>

function query(params?: Params): string {
  if (!params) return ''
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export function apiGet<T>(caminho: string, params?: Params): Promise<T> {
  return requisitar<T>(`${caminho}${query(params)}`, { method: 'GET' }, true)
}

/** POST sem Authorization — so para as rotas publicas do contrato. */
export function apiPostPublico<T>(caminho: string, corpo: unknown): Promise<T> {
  return requisitar<T>(
    caminho,
    { method: 'POST', body: JSON.stringify(corpo), headers: { 'Content-Type': 'application/json' } },
    false,
  )
}
