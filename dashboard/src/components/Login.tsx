import { useState, type FormEvent } from 'react'
import { login } from '../data/api'
import { ApiError } from '../lib/apiClient'
import { SompoMark } from './shared'

/**
 * Portao de autenticacao do dashboard.
 *
 * As credenciais sao digitadas aqui e trocadas por um JWT em POST /auth/token.
 * Nenhuma credencial vive no bundle nem em `.env.local` — a spec de
 * implementacao (§6) define que o frontend recebe apenas VITE_API_BASE_URL.
 */
export default function Login({ onEntrar }: { onEntrar: () => void }) {
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (enviando) return
    setErro(null)
    setEnviando(true)
    try {
      await login(usuario.trim(), senha)
      onEntrar()
    } catch (err) {
      // Distingue backend fora do ar (status 0) de credencial recusada (401),
      // porque a acao do usuario e diferente em cada caso.
      const msg =
        err instanceof ApiError && err.status === 0
          ? `${err.message} Confira se o backend esta rodando.`
          : err instanceof Error
            ? err.message
            : 'Falha ao autenticar.'
      setErro(msg)
      setEnviando(false)
    }
  }

  const campo = {
    width: '100%',
    padding: '10px 12px',
    borderRadius: 6,
    background: 'var(--bg-elev-2)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    fontSize: 14,
    outline: 'none',
  } as const

  return (
    <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)' }}>
      <form
        onSubmit={submeter}
        style={{
          width: 340, display: 'flex', flexDirection: 'column', gap: 14,
          background: 'var(--bg-elev)', border: '1px solid var(--line)',
          borderRadius: 12, padding: 28,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
          <SompoMark size={14} />
          <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--fg)' }}>SafeField</span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--fg-mute)', marginBottom: 6 }}>
          Entre para consultar os scores de risco da carteira.
        </div>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--fg-dim)', fontWeight: 600 }}>Usuário</span>
          <input
            style={campo}
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--fg-dim)', fontWeight: 600 }}>Senha</span>
          <input
            style={campo}
            type="password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {erro && (
          <div style={{ fontSize: 12, color: 'var(--red)', lineHeight: 1.5 }} role="alert">
            {erro}
          </div>
        )}

        <button
          type="submit"
          disabled={enviando}
          style={{
            marginTop: 4, padding: '10px 14px', borderRadius: 6, fontWeight: 700, fontSize: 13,
            cursor: enviando ? 'default' : 'pointer', border: '1px solid #5AE06B',
            background: enviando ? 'var(--bg-elev-2)' : '#5AE06B',
            color: enviando ? 'var(--fg-mute)' : '#0A0C0B',
          }}
        >
          {enviando ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
