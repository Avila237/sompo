import { useState } from 'react'
import TopBar from './components/TopBar'
import SideNav from './components/SideNav'
import { WIco } from './components/Icons'
import { EQUIPMENT } from './data/mock'
import type { Equipment } from './types'

import SompoOverview from './pages/sompo/Overview'
import SompoRanking from './pages/sompo/Ranking'
import SompoDetail from './pages/sompo/Detail'
import SompoSimulator from './pages/sompo/Simulator'
import SompoUBI from './pages/sompo/UBI'
import SompoReports from './pages/sompo/Reports'
import BrokerView from './pages/broker/Broker'
import TechnicianView from './pages/technician/Technician'

const sompoNav = [
  { k: 'overview',  label: 'Visao geral',          icon: <WIco.map /> },
  { k: 'ranking',   label: 'Ranking de risco',     icon: <WIco.grid />,   count: EQUIPMENT.length },
  { k: 'detail',    label: 'Detalhe equipamento',  icon: <WIco.info /> },
  { k: 'simulator', label: 'Simulador',            icon: <WIco.beaker /> },
  { k: 'ubi',       label: 'UBI · Premios',        icon: <WIco.chart /> },
  { k: 'reports',   label: 'Relatorios',           icon: <WIco.doc />,    count: '28' },
]

const FIRST_SCREEN: Record<string, string> = {
  sompo: 'overview',
  broker: 'broker',
  tech: 'tech',
}

export default function App() {
  const [persona, setPersona] = useState<'sompo' | 'broker' | 'tech'>('sompo')
  const [screen, setScreen] = useState('overview')
  const [pickEquip, setPickEquip] = useState<Equipment | null>(null)

  function handlePersona(p: string) {
    const key = p as 'sompo' | 'broker' | 'tech'
    setPersona(key)
    setScreen(FIRST_SCREEN[key])
    setPickEquip(null)
  }

  function goDetail(e: Equipment) {
    setPickEquip(e)
    setScreen('detail')
  }

  function renderPage() {
    if (persona === 'broker') return <BrokerView />
    if (persona === 'tech') return <TechnicianView />
    switch (screen) {
      case 'overview':  return <SompoOverview onPickEquip={goDetail} onNav={setScreen} />
      case 'ranking':   return <SompoRanking onPickEquip={goDetail} />
      case 'detail':    return <SompoDetail equip={pickEquip} onBack={() => setScreen('ranking')} />
      case 'simulator': return <SompoSimulator />
      case 'ubi':       return <SompoUBI />
      case 'reports':   return <SompoReports />
      default:          return <SompoOverview onPickEquip={goDetail} onNav={setScreen} />
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <TopBar persona={persona} setPersona={handlePersona} />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {persona === 'sompo' && (
          <SideNav items={sompoNav} active={screen} onPick={setScreen} />
        )}
        <main style={{ flex: 1, overflow: 'auto' }}>
          {renderPage()}
        </main>
      </div>
    </div>
  )
}