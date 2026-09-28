import { useCallback, useEffect, useRef, useState } from 'react'

type Chave = string | number

export interface Carga<T> {
  dados: T | null
  erro: string | null
  /** Verdadeiro enquanto a busca da `chave` atual não terminou — inclusive logo após a chave mudar. */
  carregando: boolean
  /** A `chave` a que `dados` pertence (null antes do primeiro sucesso). Use-a para rotular o que está na tela. */
  chaveDados: Chave | null
  /** Refaz a busca ignorando cache (`recarregar = true`). */
  tentarDeNovo: () => void
}

interface Estado<T> {
  dados: T | null
  erro: string | null
  chaveDados: Chave | null
  /** Última chave cuja busca terminou (sucesso ou erro). */
  chaveConcluida: Chave | null
  /** Recarga pedida por tentarDeNovo ainda em curso. */
  recarregando: boolean
}

/**
 * Busca assíncrona com o padrão que se repetia nas telas: flag `ativo` contra
 * resposta atrasada, erro legível e "tentar de novo".
 *
 * - `chave` muda → refaz a busca (ex.: período, equipamento). Os dados
 *   anteriores ficam na tela até a nova resposta chegar; `carregando` já fica
 *   verdadeiro nesse intervalo, e `chaveDados` diz a que chave eles pertencem.
 * - Em erro, `dados` preserva o último sucesso: a tela decide se mostra os
 *   dados antigos com aviso ou só o erro.
 */
export function useCarga<T>(carregar: (recarregar: boolean) => Promise<T>, chave: Chave = ''): Carga<T> {
  const [estado, setEstado] = useState<Estado<T>>({
    dados: null, erro: null, chaveDados: null, chaveConcluida: null, recarregando: false,
  })
  const [tentativa, setTentativa] = useState(0)

  // A função muda a cada render; a busca só deve refazer quando `chave` ou `tentativa` mudam
  const carregarRef = useRef(carregar)
  useEffect(() => { carregarRef.current = carregar })

  useEffect(() => {
    let ativo = true
    carregarRef.current(tentativa > 0)
      .then((dados) => {
        if (ativo) setEstado({ dados, erro: null, chaveDados: chave, chaveConcluida: chave, recarregando: false })
      })
      .catch((e) => {
        if (ativo) setEstado((s) => ({ ...s, erro: String(e?.message ?? e), chaveConcluida: chave, recarregando: false }))
      })
    return () => { ativo = false }
  }, [chave, tentativa])

  const tentarDeNovo = useCallback(() => {
    setEstado((s) => ({ ...s, erro: null, recarregando: true }))
    setTentativa((t) => t + 1)
  }, [])

  // Derivado, não guardado: "carregando" logo que a chave muda, sem setState síncrono no efeito
  const carregando = estado.recarregando || estado.chaveConcluida !== chave
  return { dados: estado.dados, erro: estado.erro, chaveDados: estado.chaveDados, carregando, tentarDeNovo }
}
