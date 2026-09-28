// API simulada para as evidências de falha do dashboard (BRA-466 · S4-33).
//
// Segue o formato de docs/contrato-api.md, com dado sintético e sem banco. O
// dashboard testado é o real; só o backend é trocado, para provocar cada falha
// de forma reproduzível. Sem dependências: `node api-simulada.mjs`.
//
// Porta: 8010 (PORTA=...). Cenário inicial: CENARIO=normal|lento|html|erro500|expirar.
// Troca ao vivo, sem reiniciar:  curl -X POST 'http://localhost:8010/__cenario?nome=html'
// "API fora do ar" = encerrar este processo (Ctrl+C) com a tela aberta.
import http from 'node:http'

const PORTA = Number(process.env.PORTA ?? 8010)
const ORIGENS = (process.env.ORIGENS ?? 'http://localhost:5173,http://localhost:5175').split(',')
let cenario = process.env.CENARIO ?? 'normal'
const CENARIOS = ['normal', 'lento', 'html', 'erro500', 'expirar']

const hoje = new Date('2026-09-21T12:00:00Z')
const dia = (n) => new Date(hoje.getTime() - n * 86400000).toISOString().slice(0, 10)
const datas = Array.from({ length: 30 }, (_, i) => dia(29 - i))

const EQUIPAMENTOS = [
  ['EQ-0042', 'John Deere S790', 'colheitadeira', 69.47, 'alto', 7.1],
  ['EQ-0173', 'Case IH A8810', 'colheitadeira', 58.2, 'medio', -2.4],
  ['EQ-0118', 'Massey Ferguson 75.180', 'trator', 44.9, 'medio', 1.2],
  ['EQ-0095', 'New Holland T7.290', 'trator', 31.5, 'baixo', -0.8],
  ['EQ-0156', 'Jumil JM-1440', 'implemento', 22.0, 'baixo', 0],
].map(([id, modelo, tipo, score, faixa, tend], i) => ({
  equipamento_id: id, modelo_equipamento: modelo, tipo_equipamento: tipo, idade_equipamento: 5 + i,
  historico_sinistros: i % 3, tem_iot: i % 2 === 0, risco_score: score, score_medio: score - 3,
  faixa_risco: faixa, tendencia: tend, total_avaliacoes: 20 + i, operador_id: `OP-00${10 + i}`,
  ultima_avaliacao: `${dia(i)}T10:00:00+00:00`, latitude: -12 - i * 3, longitude: -54 + i * 2,
}))

function corpoNormal(url) {
  const u = new URL(url, 'http://x')
  switch (u.pathname) {
    case '/auth/token':
      return { access_token: 'token-simulado', token_type: 'bearer', perfil: 'analista', expira_em_minutos: 480 }
    case '/equipamentos':
      return { total: EQUIPAMENTOS.length, itens: EQUIPAMENTOS }
    case '/alertas':
      return { total: 2, itens: [
        { avaliacao_id: 5001, equipamento_id: 'EQ-0042', operador_id: 'OP-0010', risco_score: 69.47, faixa_risco: 'alto', tipo_operacao: 'colheita', timestamp: `${dia(0)}T13:02:53+00:00`, mensagem: 'EQ-0042 · score 69 · risco alto' },
        { avaliacao_id: 4990, equipamento_id: 'EQ-0173', operador_id: 'OP-0011', risco_score: 58.2, faixa_risco: 'medio', tipo_operacao: 'transporte', timestamp: `${dia(1)}T09:40:00+00:00`, mensagem: 'EQ-0173 · score 58 · risco medio' },
      ] }
    case '/kpis':
      return {
        kpis: { total_equipamentos: 5, total_operadores: 5, total_avaliacoes: 110, score_medio: 45.2, equipamentos_risco_alto: 1, pct_risco_alto: 20, avaliacoes_por_faixa: { baixo: 40, medio: 50, alto: 20 } },
        por_operacao: [
          { tipo_operacao: 'transporte', total_avaliacoes: 30, score_medio: 52.8, avaliacoes_risco_alto: 8 },
          { tipo_operacao: 'colheita', total_avaliacoes: 40, score_medio: 47.1, avaliacoes_risco_alto: 9 },
          { tipo_operacao: 'plantio', total_avaliacoes: 40, score_medio: 38.4, avaliacoes_risco_alto: 3 },
        ],
        por_regiao: EQUIPAMENTOS.map((e, i) => ({ nome: `${12 + i * 3}°S ${54 - i * 2}°O`, latitude: e.latitude, longitude: e.longitude, x: 0.3 + i * 0.1, y: 0.4 + i * 0.08, total_equipamentos: 1, score_medio: e.risco_score })),
        tendencia: datas.map((d, i) => ({ dia: d, score_medio: 42 + 6 * Math.sin(i / 4), avaliacoes: 3 + (i % 4) })),
      }
    case '/tendencias':
      return {
        eixo: u.searchParams.get('eixo') ?? 'operacao', dias: Number(u.searchParams.get('dias') ?? 30),
        janela: { inicio: datas[0], fim: datas[datas.length - 1], dias_com_dados: datas.length, datas },
        series: ['transporte', 'colheita', 'plantio'].map((k, s) => ({
          chave: k, rotulo: k, score_medio: 50 - s * 6, avaliacoes: 30,
          pontos: datas.filter((_, i) => (i + s) % 2 === 0).map((d, i) => ({ dia: d, score_medio: 50 - s * 6 + 5 * Math.sin(i / 3 + s), avaliacoes: 2 })),
        })),
      }
    default:
      return null
  }
}

const servidor = http.createServer((req, res) => {
  const origem = req.headers.origin
  if (origem && ORIGENS.includes(origem)) {
    res.setHeader('Access-Control-Allow-Origin', origem)
    res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type')
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    res.setHeader('Access-Control-Expose-Headers', 'X-Request-ID')
  }
  if (req.method === 'OPTIONS') { res.writeHead(204); return res.end() }

  const url = new URL(req.url, 'http://x')
  if (url.pathname === '/__cenario') {
    const nome = url.searchParams.get('nome')
    if (!CENARIOS.includes(nome)) { res.writeHead(400); return res.end(`cenarios: ${CENARIOS.join(', ')}\n`) }
    cenario = nome
    console.log(`cenario -> ${cenario}`)
    res.writeHead(200); return res.end(`cenario=${cenario}\n`)
  }

  const requestId = Math.random().toString(16).slice(2, 10)
  res.setHeader('X-Request-ID', requestId)
  // O login segue funcionando em qualquer cenário: as falhas são das rotas de dado
  const ehLogin = url.pathname === '/auth/token'
  const json = (status, corpo) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(corpo)) }

  if (!ehLogin && cenario === 'lento') return // nunca responde: o cliente tem que desistir sozinho
  if (!ehLogin && cenario === 'html') {
    res.writeHead(200, { 'Content-Type': 'text/html' })
    return res.end('<!doctype html><html><body><h1>502 Bad Gateway</h1><p>proxy</p></body></html>')
  }
  if (!ehLogin && cenario === 'erro500') return json(500, { detail: 'Erro interno. Consulte os logs do servidor.', request_id: requestId })
  if (!ehLogin && cenario === 'expirar') return json(401, { detail: 'Token invalido ou expirado.' })

  const corpo = corpoNormal(req.url)
  return corpo ? json(200, corpo) : json(404, { detail: 'Rota inexistente na API simulada.' })
})

servidor.listen(PORTA, () => console.log(`API simulada em http://localhost:${PORTA} · cenario=${cenario}`))
