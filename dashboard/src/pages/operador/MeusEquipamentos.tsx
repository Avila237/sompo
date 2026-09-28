import { loadAlertas, loadEquipamentos } from '../../data/api'
import { Card, Carregando, Chip, ErroCarga, ScoreBadge, SectionHeader, Trend } from '../../components/shared'
import { useCarga } from '../../lib/useCarga'
import { fmtData, fmtDataHora } from '../../lib/formato'
import { rotuloDaFaixa, SEM_AVALIACAO, WTONE } from '../../lib/risco'

/**
 * Tela inicial do operador (BRA-460). A lista já vem recortada pela API: para
 * o perfil operador, GET /equipamentos e GET /alertas devolvem só os
 * equipamentos que ele operou (BRA-451). Sem KPIs de frota, que a API recusa (403).
 */
export default function MeusEquipamentos({ onPickEquip }: { onPickEquip: (equipamentoId: string) => void }) {
  const equipC = useCarga((recarregar) => loadEquipamentos({ recarregar }))
  const alertasC = useCarga(() => loadAlertas())

  if (equipC.carregando && !equipC.dados) return <Carregando msg="Carregando seus equipamentos…" />
  if (!equipC.dados) {
    return <ErroCarga titulo="Não foi possível carregar seus equipamentos." msg={equipC.erro ?? 'A API não devolveu dados.'} onTentar={equipC.tentarDeNovo} />
  }

  const equips = equipC.dados
  const alertas = alertasC.dados ?? []

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader title="Meus equipamentos" sub="Equipamentos que você operou, com o risco da avaliação mais recente." />

      {equips.length === 0 ? (
        <Card>
          <div style={{ fontSize: 13, color: 'var(--fg-dim)' }}>Nenhum equipamento operado por você ainda.</div>
        </Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
          {equips.map((e) => (
            <button
              key={e.id}
              type="button"
              onClick={() => onPickEquip(e.id)}
              style={{
                display: 'flex', flexDirection: 'column', gap: 12, padding: '16px 18px', minHeight: 44, textAlign: 'left',
                background: 'var(--bg-elev)', border: '1px solid var(--line)', borderRadius: 10, color: 'var(--fg)', cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}>
                <ScoreBadge score={e.score} tone={e.faixa} size="lg" />
                <div style={{ minWidth: 0 }}>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--fg-mute)' }}>{e.id}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.modelo}</div>
                </div>
                <span style={{ marginLeft: 'auto' }}>
                  <Chip state={e.faixa} label={e.score === null ? SEM_AVALIACAO : rotuloDaFaixa(e.faixa)} size="sm" />
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--fg-dim)' }}>
                <span>Última avaliação {fmtData(e.ultimaTs)}</span>
                {e.score !== null && <Trend delta={e.trend} />}
              </div>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Ver o que fazer →</div>
            </button>
          ))}
        </div>
      )}

      <Card title="Alertas dos meus equipamentos" pad={0}>
        {alertasC.erro && !alertasC.dados ? (
          <div style={{ padding: '0 18px' }}>
            <ErroCarga compacto titulo="Não foi possível carregar os alertas." msg={alertasC.erro} onTentar={alertasC.tentarDeNovo} />
          </div>
        ) : alertas.length === 0 ? (
          <div style={{ padding: '14px 18px', fontSize: 13, color: 'var(--fg-mute)' }}>
            {alertasC.carregando ? 'Carregando alertas…' : 'Nenhum alerta no momento.'}
          </div>
        ) : (
          alertas.map((a, i) => (
            <button
              key={`${a.equipamentoId}-${a.ts}`}
              type="button"
              onClick={() => onPickEquip(a.equipamentoId)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '12px 18px', minHeight: 44,
                border: 'none', borderTop: i > 0 ? '1px solid var(--line)' : 'none', background: 'transparent',
                color: 'var(--fg)', textAlign: 'left', cursor: 'pointer',
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: WTONE[a.sev].fg, flexShrink: 0 }} />
              <span style={{ fontSize: 13, fontWeight: 600, flexGrow: 1 }}>{a.msg}</span>
              <span style={{ fontSize: 11, color: 'var(--fg-mute)' }}>{fmtDataHora(a.ts)}</span>
            </button>
          ))
        )}
      </Card>
    </div>
  )
}
