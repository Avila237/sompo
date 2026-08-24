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

  let res: Response
  try {
    res = await fetch(`${base}${caminho}`, { ...init, headers })
  } catch (e) {
    // Falha de rede, CORS ou backend fora do ar. Nao e engolida: vira erro
    // com status 0 para a interface distinguir de erro HTTP.
    throw new ApiError(0, `Nao foi possivel falar com a API em ${base}. ${(e as Error).message}`)
  }

  if (res.status === 401) {
    // Token invalido ou expirado: derruba a sessao para a interface voltar ao login.
    limparSessao()
    throw new ApiError(401, await mensagemDeErro(res))
  }
  if (!res.ok) throw new ApiError(res.status, await mensagemDeErro(res))
  if (res.status === 204) return undefined as T

  return (await res.json()) as T
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

/** POST autenticado. Para `/auth/token`, use `apiPostPublico`. */
export function apiPost<T>(caminho: string, corpo: unknown): Promise<T> {
  return requisitar<T>(
    caminho,
    { method: 'POST', body: JSON.stringify(corpo), headers: { 'Content-Type': 'application/json' } },
    true,
  )
}

/** POST sem Authorization — so para as rotas publicas do contrato. */
export function apiPostPublico<T>(caminho: string, corpo: unknown): Promise<T> {
  return requisitar<T>(
    caminho,
    { method: 'POST', body: JSON.stringify(corpo), headers: { 'Content-Type': 'application/json' } },
    false,
  )
}

export const API_BASE_URL = BASE
