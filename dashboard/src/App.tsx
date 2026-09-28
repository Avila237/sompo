import { useState, useEffect } from 'react'
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
import BrokerView from './pages/broker/Broker'
import TechnicianView from './pages/technician/Technician'

const FIRST_SCREEN: Record<string, string> = {
  sompo: 'overview',
  broker: 'broker',
  tech: 'tech',
}

export default function App() {
  const [sessao, setSessaoState] = useState<Sessao | null>(() => getSessao())

  // Um 401 em qualquer chamada limpa a sessao no apiClient; aqui a interface
  // reage voltando para o login em vez de ficar exibindo tela vazia.
  useEffect(() => assinarSessao(setSessaoState), [])

  if (!sessao) return <Login onEntrar={() => setSessaoState(getSessao())} />

  // key = token: cada login monta o Shell do zero, entao o proximo usuario nao
  // herda tela, persona nem equipamento selecionado do anterior.
  return <Shell key={sessao.token} perfil={sessao.perfil} />
}

function Shell({ perfil }: { perfil: string }) {
  const [persona, setPersona] = useState<'sompo' | 'broker' | 'tech'>('sompo')
  const [screen, setScreen] = useState('overview')
  const [pickEquip, setPickEquip] = useState<string | null>(null) // equipamento_id
  const [equipCount, setEquipCount] = useState<number | undefined>(undefined)

  useEffect(() => {
    let ativo = true
    loadEquipamentos()
      .then((eqs) => { if (ativo) setEquipCount(eqs.length) })
      .catch((e) => {
        // O contador do menu fica vazio; a mensagem para o usuario sai na
        // propria tela (Visao geral / Ranking), que faz a mesma chamada.
        console.error('Falha ao carregar contagem de equipamentos:', e)
      })
    return () => { ativo = false }
  }, [])

  const sompoNav = [
    { k: 'overview',  label: 'Visao geral',          icon: <WIco.map /> },
    { k: 'ranking',   label: 'Equipamentos',         icon: <WIco.grid />,   count: equipCount },
    { k: 'detail',    label: 'Detalhe equipamento',  icon: <WIco.info /> },
    { k: 'simulator', label: 'Simulador',            icon: <WIco.beaker /> },
    { k: 'ubi',       label: 'UBI · Premios',        icon: <WIco.chart /> },
    { k: 'reports',   label: 'Relatorios',           icon: <WIco.doc /> },
  ]

  function handlePersona(p: string) {
    const key = p as 'sompo' | 'broker' | 'tech'
    setPersona(key)
    setScreen(FIRST_SCREEN[key])
    setPickEquip(null)
  }

  function goDetail(id: string) {
    setPickEquip(id)
    setScreen('detail')
  }

  function renderPage() {
    if (persona === 'broker') return <ComingSoon><BrokerView /></ComingSoon>
    if (persona === 'tech') return <ComingSoon><TechnicianView /></ComingSoon>
    switch (screen) {
      case 'overview':  return <SompoOverview onPickEquip={goDetail} onNav={setScreen} />
      case 'ranking':   return <SompoRanking onPickEquip={goDetail} />
      case 'detail':    return <SompoDetail equipId={pickEquip} onBack={() => setScreen('ranking')} />
      case 'simulator': return <ComingSoon><SompoSimulator /></ComingSoon>
      case 'ubi':       return <ComingSoon><SompoUBI /></ComingSoon>
      case 'reports':   return <SompoReports />
      default:          return <SompoOverview onPickEquip={goDetail} onNav={setScreen} />
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <TopBar persona={persona} setPersona={handlePersona} perfil={perfil} onSair={logout} />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {persona === 'sompo' && (
          <SideNav items={sompoNav} active={screen} onPick={setScreen} />
        )}
        <main style={{ flex: 1, overflow: 'auto' }}>
          {/* key: trocar de tela ou equipamento zera o erro; a navegação segue viva */}
          <ErrorBoundary key={`${persona}:${screen}:${pickEquip ?? ''}`}>
            {renderPage()}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}