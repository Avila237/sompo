/**
 * Recomendações preventivas (BRA-458 · S4-25). Vêm de regras determinísticas no
 * backend (`backend/services/recomendacoes.py`); o front só exibe.
 * Contrato: `docs/contrato-api.md`, seção "Recomendações".
 */

import { featureLabel } from './shap'

export type Publico = 'operador' | 'gestor' | 'tecnico'

export interface Recomendacao {
  id: string // estável: identifica a regra ("fator_dominante" e "monitorar" são os fallbacks)
  publico: Publico
  acao: string
  criterio: string // condição que disparou, com os valores reais da leitura
}

export const ROTULO_PUBLICO: Record<Publico, string> = { operador: 'Operador', gestor: 'Gestor', tecnico: 'Técnico' }

/**
 * Regras de fallback (nenhuma regra específica disparou), cada uma com a nota
 * que explica de onde veio a ação. `monitorar` existe justamente porque nenhum
 * fator elevou o score: não pode reusar a nota do `fator_dominante`.
 */
export const NOTA_FALLBACK: Record<string, string> = {
  fator_dominante: 'Nenhuma regra específica disparou; a ação vem do fator que mais elevou o score.',
  monitorar: 'Nenhuma regra específica disparou e nenhum fator isolado elevou o score; a recomendação é acompanhar.',
}

/**
 * Deixa o critério legível para o usuário final: troca o nome técnico da coluna
 * pelo rótulo que o Detalhe já usa, `true/false` por sim/não e o ponto decimal
 * por vírgula. Só reescreve tokens `feature=valor` de features conhecidas; o
 * resto do texto (operadores, limiares, frases) fica como veio. O critério
 * original continua visível ao lado: esta é uma leitura, não uma substituição.
 */
export function criterioLegivel(criterio: string): string {
  return criterio
    .replace(/\b([a-z_]+)=([^\s),]+)/g, (tudo, feature: string, valor: string) => {
      const rotulo = featureLabel(feature)
      if (rotulo === feature) return tudo // feature desconhecida: não inventa rótulo
      // sem distinção de caixa: o backend chegou a mandar True/False no fator_dominante
      const bool = valor.toLowerCase()
      const v = bool === 'true' ? 'sim' : bool === 'false' ? 'não' : valor.replace(/(\d)\.(\d)/g, '$1,$2')
      return `${rotulo} = ${v}`
    })
    .replace(/(\d)\.(\d)/g, '$1,$2')
}
