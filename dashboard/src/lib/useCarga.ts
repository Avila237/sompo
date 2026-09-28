import { useCallback, useEffect, useRef, useState } from 'react'

export interface Carga<T> {
  dados: T | null
  erro: string | null
  carregando: boolean
  /** Refaz a busca ignorando cache (`recarregar = true`). */
  tentarDeNovo: () => void
}

/**
 * Busca assíncrona com o padrão que se repetia nas telas: flag `ativo` contra
 * resposta atrasada, erro legível e "tentar de novo".
 *
 * - `chave` muda → refaz a busca (ex.: período, equipamento). Os dados
 *   anteriores ficam na tela até a nova resposta chegar.
 * - Em erro, `dados` preserva o último sucesso: a tela decide se mostra os
 *   dados antigos com aviso ou só o erro.
 */
export function useCarga<T>(carregar: (recarregar: boolean) => Promise<T>, chave: string | number = ''): Carga<T> {
  const [estado, setEstado] = useState<Omit<Carga<T>, 'tentarDeNovo'>>({ dados: null, erro: null, carregando: true })
  const [tentativa, setTentativa] = useState(0)

  // A função muda a cada render; a busca só deve refazer quando `chave` ou `tentativa` mudam
  const carregarRef = useRef(carregar)
  useEffect(() => { carregarRef.current = carregar })

  useEffect(() => {
    let ativo = true
    carregarRef.current(tentativa > 0)
      .then((dados) => { if (ativo) setEstado({ dados, erro: null, carregando: false }) })
      .catch((e) => { if (ativo) setEstado((s) => ({ ...s, erro: String(e?.message ?? e), carregando: false })) })
    return () => { ativo = false }
  }, [chave, tentativa])

  const tentarDeNovo = useCallback(() => {
    setEstado((s) => ({ ...s, erro: null, carregando: true }))
    setTentativa((t) => t + 1)
  }, [])

  return { ...estado, tentarDeNovo }
}
