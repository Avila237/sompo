import { useState, useEffect } from 'react'
import TopBar from './components/TopBar'
import SideNav from './components/SideNav'
import { WIco } from './components/Icons'
import { loadRawData } from './data/api'
import type { Equipment } from './types'
import { ComingSoon } from './components/ComingSoon'

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
  const [persona, setPersona] = useState<'sompo' | 'broker' | 'tech'>('sompo')
  const [screen, setScreen] = useState('overview')
  const [pickEquip, setPickEquip] = useState<Equipment | null>(null)
  const [equipCount, setEquipCount] = useState<number | undefined>(undefined)

  useEffect(() => {
    loadRawData()
      .then((d) => setEquipCount(d.equipamentos.length))
      .catch(() => setEquipCount(undefined))
  }, [])

  const sompoNav = [
    { k: 'overview',  label: 'Visao geral',          icon: <WIco.map /> },
    { k: 'ranking',   label: 'Equipamentos',         icon: <WIco.grid />,   count: equipCount },
    { k: 'detail',    label: 'Detalhe equipamento',  icon: <WIco.info /> },
    { k: 'simulator', label: 'Simulador',            icon: <WIco.beaker /> },
    { k: 'ubi',       label: 'UBI · Premios',        icon: <WIco.chart /> },
    { k: 'reports',   label: 'Relatorios',           icon: <WIco.doc />,    count: '28' },
  ]

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
    if (persona === 'broker') return <ComingSoon><BrokerView /></ComingSoon>
    if (persona === 'tech') return <ComingSoon><TechnicianView /></ComingSoon>
    switch (screen) {
      case 'overview':  return <SompoOverview onPickEquip={goDetail} onNav={setScreen} />
      case 'ranking':   return <SompoRanking onPickEquip={goDetail} />
      case 'detail':    return <SompoDetail equip={pickEquip} onBack={() => setScreen('ranking')} />
      case 'simulator': return <ComingSoon><SompoSimulator /></ComingSoon>
      case 'ubi':       return <ComingSoon><SompoUBI /></ComingSoon>
      case 'reports':   return <ComingSoon><SompoReports /></ComingSoon>
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