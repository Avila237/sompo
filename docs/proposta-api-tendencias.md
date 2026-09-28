# Proposta de contrato · GET /tendencias

> **Status: proposta, não implementada.** Serve à BRA-459 (S4-26, relatórios de tendência), que
> pede o contrato definido antes do front. Quando a rota existir, esta seção migra para
> `docs/contrato-api.md` (que só descreve a API em execução) e este arquivo é removido.
>
> Design da tela que consome a rota: canvas da BRA-459 (link no PR).

## Por que uma rota nova

`GET /kpis` já devolve `tendencia`, mas só a **global**: uma série para a frota inteira. O enunciado
da Sprint 4 pede *"tendências de risco por equipamento, região ou tipo de operação"*: uma série por
grupo, em cada um dos três eixos. Estender o `/kpis` faria a Visão Geral baixar três conjuntos de
séries que ela não usa. Por isso a proposta é uma rota separada, chamada só pela tela Relatórios.

## Requisição

`GET /tendencias` · autenticada (Bearer), como as demais rotas de leitura.

| Parâmetro | Tipo | Default | Regra |
|---|---|---|---|
| `eixo` | `equipamento` \| `regiao` \| `operacao` | obrigatório | outro valor → `422` |
| `dias` | int | `30` | 1–365. Janela em **dias com dados**, mesma semântica de `tendencia` em `/kpis` |
| `limite` | int | `5` | 1–20. Quantos grupos devolver |
| `chave` | string | — | Opcional. Restringe a um grupo (ex.: `EQ-0042`) e ignora `limite` |

## Resposta 200

```json
{
  "eixo": "operacao",
  "dias": 30,
  "janela": {
    "inicio": "2025-11-02",
    "fim": "2026-09-21",
    "dias_com_dados": 30
  },
  "series": [
    {
      "chave": "transporte",
      "rotulo": "transporte",
      "score_medio": 52.78,
      "avaliacoes": 312,
      "pontos": [
        { "dia": "2025-11-02", "score_medio": 49.10, "avaliacoes": 9 },
        { "dia": "2025-11-04", "score_medio": 55.32, "avaliacoes": 12 },
        "..."
      ]
    },
    "..."
  ]
}
```

### Regras

- **Janela.** Os últimos `dias` dias que têm pelo menos uma avaliação **na base inteira**, não por
  grupo. Assim todas as séries dividem o mesmo eixo X. `dias_com_dados` < `dias` quando a base tem
  menos dias do que o pedido.
- **Pontos.** Um grupo só tem ponto nos dias da janela em que **ele** tem avaliação. Dia sem dado
  não vira `0` nem é interpolado. O front desenha lacuna.
- **Agrupamento por eixo:**
  - `equipamento`: `equipamento_id`. `rotulo` = o próprio id.
  - `operacao`: `tipo_operacao`. Avaliação sem o campo entra como `"desconhecida"`, como em `/kpis`.
  - `regiao`: célula de 3° pela **posição da própria avaliação** (`latitude`/`longitude` dela), com
    `rotulo` no formato `"24°S 51°O"`. **Difere de `por_regiao` do `/kpis`**, que usa a posição da
    última avaliação do equipamento: numa série temporal, cada ponto precisa da região onde a
    avaliação aconteceu. Avaliação sem coordenada fica de fora.
- **Quais grupos entram.** Os `limite` grupos de maior `score_medio` na janela (desempate: mais
  `avaliacoes`). A tela é de risco, então o topo é o que importa. Com `chave`, só aquele grupo.
- **`score_medio` e `avaliacoes` do grupo** são calculados sobre a janela, não sobre toda a base.
- **Ordem.** `series` por `score_medio` desc. `pontos` por `dia` asc.
- **Sem dados.** `series: []` com `200`, inclusive com `chave` inexistente: filtro que não casa não
  é erro. (Equipamento inexistente continua `404` em `/equipamentos/{id}`.)

### Erros

| Situação | Status |
|---|---|
| Sem token / token inválido | `401` (como as demais rotas) |
| `eixo` ausente ou inválido, `dias`/`limite` fora da faixa | `422` |

## Exportação CSV

Sem rota própria. O front gera o CSV no navegador a partir desta mesma resposta
(`eixo,chave,dia,score_medio,avaliacoes`, uma linha por ponto). Assim o arquivo é exatamente o que
está na tela, e não existe botão que finge exportar.

## Implementação sugerida (backend)

Tudo sai do que já está em memória: `repo.listar_avaliacoes_resumo()` traz `timestamp`,
`risco_score`, `equipamento_id`, `tipo_operacao`, `latitude` e `longitude`. Não precisa de coluna
nem de consulta nova. Uma função `consultas.tendencias(eixo, dias, limite, chave)` segue o padrão de
`consultas.tendencia(dias)`, e a rota fica em `backend/api/routers/consultas.py`.

Testes mínimos: janela menor que `dias`; grupo com lacuna (sem ponto zerado); `regiao` usando a
posição da avaliação; `chave` inexistente → `series: []`; `eixo` inválido → `422`.

## Em aberto

- **Quem implementa a rota.** Backend é frente do Guilherme. Esta proposta pode ser implementada por
  qualquer um dos dois, desde que revisada pela outra frente.
- **Filtro por perfil (S4-18).** Hoje nenhuma rota filtra por perfil. Se a S4-18 restringir o que
  cada perfil enxerga, esta rota segue a mesma regra das demais, sem regra própria.
