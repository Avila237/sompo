import { Component, type ErrorInfo, type ReactNode } from 'react'

/**
 * Captura erro de render (ex.: campo nulo inesperado vindo da API) e mostra
 * mensagem com "Tentar de novo" em vez de tela branca.
 *
 * Não engole o erro: registra no console com a pilha de componentes, que é
 * onde quem depura vai procurar.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, { erro: Error | null }> {
  state: { erro: Error | null } = { erro: null }

  static getDerivedStateFromError(erro: Error) {
    return { erro }
  }

  componentDidCatch(erro: Error, info: ErrorInfo) {
    console.error('Erro de render capturado pelo ErrorBoundary:', erro, info.componentStack)
  }

  render() {
    const { erro } = this.state
    if (!erro) return this.props.children
    return (
      <div role="alert" style={{ padding: '32px 28px', display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'flex-start' }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--red)' }}>Algo deu errado ao exibir esta tela.</div>
        <div className="mono" style={{ fontSize: 12, color: 'var(--fg-dim)' }}>{erro.message}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => this.setState({ erro: null })} style={botao}>Tentar de novo</button>
          <button onClick={() => window.location.reload()} style={botao}>Recarregar a página</button>
        </div>
      </div>
    )
  }
}

const botao = {
  padding: '7px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer',
  background: 'transparent', color: 'var(--fg)', border: '1px solid var(--line-2)',
} as const
