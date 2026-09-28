import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * CSP estrita no build de producao (S4-18, divida D9). O token fica em
 * sessionStorage; a CSP e o que impede um script injetado de le-lo e mandar
 * para fora: so roda script do proprio bundle e so conecta na API.
 *
 * So no build: o dev server do Vite injeta script inline (HMR, React Refresh),
 * que a mesma politica bloquearia. Estilo inline fica liberado porque os
 * componentes usam style={...} em todo lugar; o vetor de roubo de token e
 * script, nao estilo.
 */
function csp(apiBase: string): Plugin {
  const origemApi = new URL(apiBase).origin
  const politica = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    'font-src https://fonts.gstatic.com',
    "img-src 'self' data:",
    `connect-src 'self' ${origemApi}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; ')
  return {
    name: 'safefield-csp',
    apply: 'build',
    transformIndexHtml: () => [
      { tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: politica }, injectTo: 'head-prepend' },
    ],
  }
}

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  // Sem a variavel, o build falha aqui: melhor que um bundle cuja CSP nao deixa falar com a API.
  // So no build: o preview so serve o dist/ ja gerado.
  if (command === 'build' && !env.VITE_API_BASE_URL) {
    throw new Error('VITE_API_BASE_URL ausente: defina em dashboard/.env.local antes do build.')
  }
  return {
    plugins: [react(), tailwindcss(), ...(env.VITE_API_BASE_URL ? [csp(env.VITE_API_BASE_URL)] : [])],
  }
})
