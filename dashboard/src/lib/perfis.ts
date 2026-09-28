/**
 * Navegação por perfil (BRA-460), seguindo a matriz perfil × rota aprovada na
 * BRA-451. O recorte de DADOS é da API (o operador só recebe os equipamentos
 * que operou; /kpis e /tendencias dão 403 para ele): aqui só se decide que
 * telas cada perfil vê, para ninguém cair numa tela que a API vai recusar.
 */

import type { Publico } from '../data/recomendacoes'

export type Perfil = 'analista' | 'gestor' | 'tecnico' | 'operador'

export type Tela =
  | 'overview' | 'ranking' | 'detail' | 'reports'
  | 'manutencao' | 'meus'
  | 'simulator' | 'ubi'

interface ConfigPerfil {
  rotulo: string
  inicio: Tela
  /** Telas do menu, na ordem. 'detail' abre ao escolher um equipamento. */
  menu: Tela[]
  /** Lista para onde "voltar" leva a partir do Detalhe. */
  lista: Tela
  /** Público cujas recomendações o card do Detalhe abre filtrado; null = todas. */
  publico: Publico | null
  /** Mostra no Detalhe as ações de frota ainda sem endpoint ("Em breve"): não fazem sentido para o operador. */
  acoesDetalhe: boolean
}

export const PERFIS: Record<Perfil, ConfigPerfil> = {
  analista: {
    rotulo: 'Analista (Sompo)', inicio: 'overview', lista: 'ranking', publico: null, acoesDetalhe: true,
    menu: ['overview', 'ranking', 'detail', 'reports', 'simulator', 'ubi'],
  },
  gestor: {
    rotulo: 'Gestor de frota', inicio: 'overview', lista: 'ranking', publico: 'gestor', acoesDetalhe: true,
    menu: ['overview', 'ranking', 'detail', 'reports'],
  },
  tecnico: {
    rotulo: 'Técnico de manutenção', inicio: 'manutencao', lista: 'manutencao', publico: 'tecnico', acoesDetalhe: true,
    menu: ['manutencao', 'overview', 'ranking', 'detail', 'reports'],
  },
  operador: {
    rotulo: 'Operador', inicio: 'meus', lista: 'meus', publico: 'operador', acoesDetalhe: false,
    menu: ['meus', 'detail'],
  },
}

/** Perfil desconhecido não ganha menu por palpite: a tela diz que ele não é reconhecido. */
export function perfilConhecido(perfil: string): perfil is Perfil {
  return perfil in PERFIS
}
