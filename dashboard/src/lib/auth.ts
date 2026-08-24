/**
 * Sessao autenticada contra a API do backend.
 *
 * O token JWT e emitido por `POST /auth/token` e guardado em `sessionStorage`:
 * sobrevive a um refresh da pagina e morre quando a aba fecha. Nenhuma
 * credencial fica embutida no bundle — o usuario digita usuario e senha na
 * tela de login (ver `components/Login.tsx`).
 */

const STORAGE_KEY = 'safefield.sessao'

export interface Sessao {
  token: string
  perfil: string
  /** epoch em ms; derivado de `expira_em_minutos` no momento da emissao */
  expiraEm: number
}

type Listener = (s: Sessao | null) => void

const listeners = new Set<Listener>()

function ler(): Sessao | null {
  try {
    const cru = sessionStorage.getItem(STORAGE_KEY)
    if (!cru) return null
    const s = JSON.parse(cru) as Sessao
    if (typeof s?.token !== 'string' || typeof s?.expiraEm !== 'number') return null
    return s
  } catch {
    // sessionStorage indisponivel (modo privado, storage bloqueado) ou JSON
    // corrompido: trata como "sem sessao" em vez de derrubar a aplicacao.
    return null
  }
}

let sessao: Sessao | null = ler()

function notificar(): void {
  for (const fn of listeners) fn(sessao)
}

/** Sessao corrente, ou `null` se ausente/expirada. */
export function getSessao(): Sessao | null {
  if (sessao && sessao.expiraEm <= Date.now()) limparSessao()
  return sessao
}

/** Token para o header `Authorization`, ou `null` se nao ha sessao valida. */
export function getToken(): string | null {
  return getSessao()?.token ?? null
}

export function setSessao(nova: Sessao): void {
  sessao = nova
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(nova))
  } catch {
    // Persistencia e conveniencia, nao requisito: a sessao segue valida em
    // memoria mesmo que o storage recuse a escrita.
  }
  notificar()
}

export function limparSessao(): void {
  sessao = null
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // idem acima
  }
  notificar()
}

/** Assina mudancas de sessao. Devolve a funcao de cancelamento. */
export function assinarSessao(fn: Listener): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
