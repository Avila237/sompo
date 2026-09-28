import { useState, useEffect, type JSX } from 'react'
import TopBar from './components/TopBar'
import SideNav from './components/SideNav'
import { WIco } from './components/Icons'
import { loadEquipamentos, logout } from './data/api'
import { getSessao, assinarSessao, type Sessao } from './lib/auth'
import Login from './components/Login'
import { ComingSoon } from './components/ComingSoon'
import { ErrorBoundary } from './components/ErrorBoundary'

import SompoOverview from './pages/sompo/Overview'
import SompoRanking from './pages/sompo/Ranking'
import SompoDetail from './pages/sompo/Detail'
import SompoSimulator from './pages/sompo/Simulator'
import SompoUBI from './pages/sompo/UBI'
import SompoReports from './pages/sompo/Reports'
import MeusEquipamentos from './pages/operador/MeusEquipamentos'
import Manutencao from './pages/tecnico/Manutencao'
import { PERFIS, perfilConhecido, type Perfil, type Tela } from './lib/perfis'

export default function App() {
  const [sessao, setSessaoState] = useState<Sessao | null>(() => getSessao())

  // Um 401 em qualquer chamada limpa a sessao no apiClient; aqui a interface
  // reage voltando para o login em vez de ficar exibindo tela vazia.
  useEffect(() => assinarSessao(setSessaoState), [])

  if (!sessao) return <Login onEntrar={() => setSessaoState(getSessao())} />

  // Perfil fora da matriz (BRA-451) não ganha menu por palpite
  if (!perfilConhecido(sessao.perfil)) return <PerfilDesconhecido perfil={sessao.perfil} usuario={sessao.usuario} />

  // key = token: cada login monta o Shell do zero, entao o proximo usuario nao
  // herda tela nem equipamento selecionado do anterior.
  return <Shell key={sessao.token} perfil={sessao.perfil} usuario={sessao.usuario} />
}

const ITENS_MENU: Record<Tela, { label: string; icon: JSX.Element }> = {
  meus:       { label: 'Meus equipamentos',    icon: <WIco.grid /> },
  manutencao: { label: 'Manutenção da frota',  icon: <WIco.wrench /> },
  overview:   { label: 'Visão geral',          icon: <WIco.map /> },
  ranking:    { label: 'Equipamentos',         icon: <WIco.grid /> },
  detail:     { label: 'Detalhe equipamento',  icon: <WIco.info /> },
  reports:    { label: 'Relatórios',           icon: <WIco.doc /> },
  simulator:  { label: 'Simulador',            icon: <WIco.beaker /> },
  ubi:        { label: 'UBI · Prêmios',        icon: <WIco.chart /> },
}

function Shell({ perfil, usuario }: { perfil: Perfil; usuario?: string }) {
  const cfg = PERFIS[perfil]
  const [screen, setScreen] = useState<Tela>(cfg.inicio)
  const [pickEquip, setPickEquip] = useState<string | null>(null) // equipamento_id
  const [equipCount, setEquipCount] = useState<number | undefined>(undefined)

  useEffect(() => {
    let ativo = true
    loadEquipamentos()
      .then((eqs) => { if (ativo) setEquipCount(eqs.length) })
      .catch((e) => {
        // O contador do menu fica vazio; a mensagem para o usuario sai na
        // propria tela, que faz a mesma chamada.
        console.error('Falha ao carregar contagem de equipamentos:', e)
      })
    return () => { ativo = false }
  }, [])

  const menu = cfg.menu.map((k) => ({
    k, ...ITENS_MENU[k],
    // o contador acompanha a lista de equipamentos do perfil (a do operador já vem recortada)
    count: k === 'ranking' || k === 'meus' ? equipCount : undefined,
  }))

  function goDetail(id: string) {
    setPickEquip(id)
    setScreen('detail')
  }

  // Só renderiza tela do menu do perfil: nada de cair numa tela que a API vai recusar (403)
  function renderPage() {
    const tela = cfg.menu.includes(screen) ? screen : cfg.inicio
    switch (tela) {
      case 'meus':       return <MeusEquipamentos onPickEquip={goDetail} />
      case 'manutencao': return <Manutencao onPickEquip={goDetail} />
      case 'overview':   return <SompoOverview onPickEquip={goDetail} onNav={(t) => setScreen(t as Tela)} />
      case 'ranking':    return <SompoRanking onPickEquip={goDetail} />
      case 'detail':     return <SompoDetail equipId={pickEquip} publico={cfg.publico} onBack={() => setScreen(cfg.lista)} />
      case 'reports':    return <SompoReports />
      case 'simulator':  return <ComingSoon><SompoSimulator /></ComingSoon>
      case 'ubi':        return <ComingSoon><SompoUBI /></ComingSoon>
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <TopBar perfil={cfg.rotulo} usuario={usuario} onSair={logout} />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <SideNav items={menu} active={screen} onPick={(k) => setScreen(k as Tela)} />
        <main style={{ flex: 1, overflow: 'auto' }}>
          {/* key: trocar de tela ou equipamento zera o erro; a navegação segue viva */}
          <ErrorBoundary key={`${screen}:${pickEquip ?? ''}`}>
            {renderPage()}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}

function PerfilDesconhecido({ perfil, usuario }: { perfil: string; usuario?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)' }}>
      <TopBar perfil={perfil} usuario={usuario} onSair={logout} />
      <div role="alert" style={{ padding: '32px 28px', fontSize: 14, color: 'var(--fg-dim)' }}>
        O perfil <strong className="mono" style={{ color: 'var(--fg)' }}>{perfil}</strong> não é reconhecido por este dashboard.
        Saia e entre com um usuário de perfil analista, gestor, técnico ou operador.
      </div>
    </div>
  )
}
