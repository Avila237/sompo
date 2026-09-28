/**
 * Geração de CSV no navegador. O arquivo é exatamente o que está na tela, sem
 * rota de exportação no backend.
 */

/**
 * Célula começando com = + - @ (ou tab/CR) é lida como fórmula por Excel e
 * Sheets (CSV injection). Os valores vêm do banco, então o prefixo ' neutraliza
 * qualquer um que comece assim; aspas e vírgulas são escapadas pelo RFC 4180.
 */
function celula(v: string | number, separador: string): string {
  // número com vírgula decimal: o Excel pt-BR lê "52.78" como texto
  let s = typeof v === 'number' ? String(v).replace('.', ',') : v
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`
  return s.includes(separador) || /["\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/**
 * Separador `;` e vírgula decimal: é o que o Excel em pt-BR abre direto em
 * colunas (com `,` ele joga tudo numa coluna só). O Sheets em pt-BR também lê.
 */
export function gerarCsv(cabecalho: string[], linhas: Array<Array<string | number>>, separador = ';'): string {
  return [cabecalho, ...linhas].map((l) => l.map((v) => celula(v, separador)).join(separador)).join('\r\n')
}

/** BOM UTF-8 para o Excel abrir acentos e "°" corretamente. */
export function baixarCsv(nomeArquivo: string, conteudo: string): void {
  const blob = new Blob(['﻿', conteudo], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nomeArquivo
  a.click()
  URL.revokeObjectURL(url)
}
