# Contrato da API

> Gerado a partir da API **em execução**, não de proposta, e conferido contra o código em
> 28/09/2026. Espelho legível de `docs/openapi.json` (exportado do FastAPI). Com a API no ar, o
> Swagger fica em `http://localhost:8000/docs`.
>
> **Regra do contrato:** qualquer mudança de shape aqui precisa ser avisada às duas frentes antes
> de entrar. É o único ponto onde backend e frontend quebram em silêncio.

## Autenticação

Todas as rotas exigem `Authorization: Bearer <token>`, exceto `POST /auth/token` e `GET /health`.
O Swagger (`/docs`, `/redoc`, `/openapi.json`) também é público.

Token expira em `JWT_EXPIRE_MINUTES` (default 480). Perfis: `operador`, `gestor`, `analista`. Nesta
versão os três enxergam os mesmos dados; o perfil vai no token, mas nenhuma rota o usa para filtrar.

### POST /auth/token

```json
// requisição
{"usuario": "analista", "senha": "..."}
// resposta 200
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "perfil": "analista",
  "expira_em_minutos": 480
}
```

## Erros

Todo erro tratado responde `{"detail": "<mensagem>"}`, sem stack trace.

| Situação | Status | `detail` |
|---|---|---|
| Sem token | `401` | `"Token ausente."` |
| Token inválido ou expirado | `401` | `"Token invalido ou expirado."` |
| Credencial errada em `/auth/token` | `401` | `"Usuario ou senha invalidos."` |
| Equipamento inexistente | `404` | `"Equipamento 'EQ-9999' nao encontrado."` |
| Operador inexistente (`POST /avaliacoes`) | `404` | `"Operador 'OP-9999' nao encontrado."` |
| Payload fora de faixa ou de tipo | `422` | lista do Pydantic: campo em `loc`, motivo em `msg` |
| Campo desconhecido no payload | `422` | lista do Pydantic, `type: "extra_forbidden"` |
| Campos incoerentes entre si (`parado` com velocidade; clima incompatível com a chuva) | `422` | lista do Pydantic, `type: "value_error"`, com a regra violada em `msg` |
| Leitura incoerente com o cadastro (`temperatura_motor` sem IoT ou em implemento) | `422` | texto com a regra violada, ex.: `"temperatura_motor enviada para EQ-0042, que nao tem IoT (Regra 1)"` |
| Open-Meteo fora **e** payload sem clima completo | `502` | mensagem com os campos climáticos ausentes |
| Artefatos do modelo ausentes ou ilegíveis (`POST /avaliacoes`) | `503` | `"Modelo preditivo indisponivel. Verifique os artefatos em models/."` |
| Supabase inacessível: conexão recusada, sem rota ou timeout (qualquer rota de dado) | `503` | `"Banco de dados indisponivel."` |
| Qualquer outra falha | `500` | `"Erro interno. Consulte os logs do servidor."` + campo `request_id` |

**Campo desconhecido é recusado, não ignorado.** Vale para os campos que o servidor deriva
(`faixa_risco`, `atraso_manutencao_pct`, `manutencao_atrasada`): enviá-los é erro. É o que impede o
cliente de forjar o resultado.

**Correlação.** Toda resposta, inclusive o `500`, traz o header `X-Request-ID`, o mesmo
identificador das linhas de log daquela requisição. No `500` ele vem também no corpo, em
`request_id`.

**Auditoria das recusas.** Em `POST /avaliacoes`, toda recusa depois da autenticação (`404`,
`422` de cadastro, `502` e `503` do modelo) grava uma linha em `auditoria` com `status='erro'` e
o motivo em `detalhe`. Com o banco fora (`503` do Supabase), a própria auditoria não tem onde
gravar; a falha fica no log.

## GET /health

Público. Diz se a API subiu e se o modelo carregou.

```json
// resposta 200, modelo carregado
{"status": "ok", "modelo": {"carregado": true, "n_features": 30}, "modelo_versao": "xgboost-v1-baseline"}
// resposta 200, modelo ausente
{"status": "degradado", "modelo": {"carregado": false}, "modelo_versao": "xgboost-v1-baseline"}
```

Responde `200` mesmo degradado; quem monitora deve ler `status`. A rota é pública, então não diz
**por que** o modelo não carregou: o motivo vai para o log. Com o modelo ausente, cada chamada
tenta carregá-lo de novo.

## GET /equipamentos

Query params: `faixa` (`baixo|medio|alto`), `busca` (1–60 caracteres, casa com id ou modelo).
Ordenado por `risco_score` desc. Uma linha por equipamento, com o score da avaliação mais recente.

```json
{
  "total": 200,
  "itens": [
    {
      "equipamento_id": "EQ-0017",
      "modelo_equipamento": "New Holland T7.290",
      "tipo_equipamento": "trator",
      "idade_equipamento": 17,
      "historico_sinistros": 7,
      "tem_iot": true,
      "risco_score": 100.0,
      "score_medio": 81.6,
      "faixa_risco": "alto",
      "tendencia": 0.0,
      "total_avaliacoes": 26,
      "operador_id": "OP-0017",
      "ultima_avaliacao": "2025-11-18T10:49:45+00:00",
      "latitude": -23.882754,
      "longitude": -44.369725
    },
    "..."
  ]
}
```

- `tendencia` é a diferença entre o score da última avaliação e o da penúltima; `0.0` com uma só.
- `faixa_risco` é a faixa gravada na última avaliação, derivada do score cru no momento da
  predição. Não é recalculada a partir do `risco_score` devolvido, que tem duas casas.

**Equipamento sem nenhuma avaliação** também aparece na lista, com:
- `operador_id`, `ultima_avaliacao`, `latitude` e `longitude` iguais a `null`;
- `total_avaliacoes` igual a `0`;
- `risco_score`, `score_medio` e `tendencia` iguais a `0.0`;
- `faixa_risco` igual a `"baixo"`.

Quem consome deve checar `total_avaliacoes` antes de exibir o score: sem avaliação, `0` não
significa risco baixo.

## GET /equipamentos/{id}

Detalhe de um equipamento. `404` se o id não existe no cadastro.

| Campo | Conteúdo | Pode ser `null`? |
|---|---|---|
| `equipamento` | linha completa do cadastro | não |
| `ultima_avaliacao` | linha completa da avaliação mais recente em `avaliacoes` | sim, se não há avaliação |
| `predicao` | predição ligada a essa avaliação | sim, se não há avaliação ou predição |
| `historico` | `{timestamp, risco_score}` de todas as avaliações, da mais antiga à mais recente | lista vazia |

`ultima_avaliacao` é a linha completa de `avaliacoes`. Além dos campos de telemetria, operação,
clima e manutenção, ela traz os identificadores (`avaliacao_id`, `equipamento_id`, `operador_id`),
`timestamp`, `risco_score`, `faixa_risco` e a procedência (`fonte`, `clima_origem`).

```json
{
  "equipamento": {
    "equipamento_id": "EQ-0042",
    "tipo_equipamento": "colheitadeira",
    "modelo_equipamento": "John Deere S790",
    "categoria_manual": "colheitadeira_manutencao",
    "idade_equipamento": 21,
    "historico_sinistros": 2,
    "tem_iot": false,
    "intervalo_manut_recomendado_dias": 151,
    "intervalo_manut_recomendado_horas": 444
  },
  "ultima_avaliacao": {
    "avaliacao_id": 5001,
    "equipamento_id": "EQ-0042",
    "operador_id": "OP-0015",
    "timestamp": "2026-08-24T13:02:53.465989+00:00",
    "tipo_operacao": "colheita",
    "velocidade_kmh": 6.2,
    "horas_operacao": 7.5,
    "horario_operacao": 14,
    "vibracao_g": 1.8,
    "temperatura_motor": 92.0,
    "precipitacao_mm": 42.0,
    "umidade_solo": 78.0,
    "condicao_clima": "chuvoso",
    "distancia_agua_m": 120.0,
    "declividade": 8.4,
    "tipo_solo": "argiloso",
    "pct_velocidade_acima_recomendada": 22.0,
    "freq_eventos_bruscos": 4.1,
    "pct_operacoes_noturnas": 18.0,
    "score_operador_historico": 61.0,
    "ultima_manutencao_dias": 210,
    "ultima_manutencao_horas_op": 640.0,
    "manutencao_atrasada": true,
    "atraso_manutencao_pct": 1.441,
    "risco_score": 69.47,
    "faixa_risco": "alto",
    "fonte": "telemetria",
    "clima_origem": "open-meteo",
    "__nota": "+ latitude, longitude, temperatura_ar, velocidade_vento"
  },
  "predicao": {
    "avaliacao_id": 5001,
    "risco_score_predito": 69.47,
    "faixa_predita": "alto",
    "top_fatores_shap": [
      {
        "feature": "distancia_agua_m",
        "valor": 120.0,
        "shap_value": 11.5357,
        "grupo": "geografico"
      },
      {
        "feature": "precipitacao_mm",
        "valor": 42.0,
        "shap_value": 11.3671,
        "grupo": "ambiental"
      },
      "..."
    ],
    "modelo_versao": "xgboost-v1-baseline"
  },
  "historico": [
    {
      "timestamp": "2025-01-13T01:07:41+00:00",
      "risco_score": 31.4
    },
    {
      "timestamp": "2025-02-13T01:00:14+00:00",
      "risco_score": 35.0
    },
    "..."
  ]
}
```

`predicao.top_fatores_shap` traz os **5** fatores de maior `|shap_value|`. A decomposição completa
por grupo (`contribuicoes_por_grupo`) só existe na resposta de `POST /avaliacoes` e não é gravada;
somar os 5 fatores por grupo dá uma aproximação, não o mesmo número.

## GET /alertas

Query params: `limite` (1–100, default 7), `faixa_minima` (`baixo|medio|alto`, default `medio`).

**Regra de alerta** (portada de `buildAlertas`, que rodava no cliente): avaliações ordenadas da
mais recente para a mais antiga, descartando as de faixa abaixo de `faixa_minima`, limitadas a
`limite`. O default `faixa_minima=medio` reproduz o `faixa_risco !== 'baixo'` anterior. Como em
`/equipamentos`, a faixa é a gravada na avaliação.

```json
{
  "total": 2,
  "itens": [
    {
      "avaliacao_id": 5001,
      "equipamento_id": "EQ-0042",
      "operador_id": "OP-0015",
      "risco_score": 69.47,
      "faixa_risco": "alto",
      "tipo_operacao": "colheita",
      "timestamp": "2026-08-24T13:02:53.465989+00:00",
      "mensagem": "EQ-0042 · score 69 · risco alto"
    },
    {
      "avaliacao_id": 870,
      "equipamento_id": "EQ-0173",
      "operador_id": "OP-0010",
      "risco_score": 100.0,
      "faixa_risco": "alto",
      "tipo_operacao": "transporte",
      "timestamp": "2025-12-31T14:19:16+00:00",
      "mensagem": "EQ-0173 · score 100 · risco alto"
    }
  ]
}
```

`tipo_operacao` pode vir `null` se a avaliação não tiver o campo.

## GET /kpis

Cobre as três visões que o enunciado exige: por equipamento (`/equipamentos`), **por operação** e
**por região**. Query param: `dias` (1–365, default 30), janela da série `tendencia`.

```json
{
  "kpis": {
    "total_equipamentos": 200,
    "total_operadores": 80,
    "total_avaliacoes": 5001,
    "score_medio": 47.09,
    "equipamentos_risco_alto": 52,
    "pct_risco_alto": 26.0,
    "avaliacoes_por_faixa": {
      "baixo": 1953,
      "medio": 1820,
      "alto": 1228
    }
  },
  "por_operacao": [
    {
      "tipo_operacao": "transporte",
      "total_avaliacoes": 1316,
      "score_medio": 52.78,
      "avaliacoes_risco_alto": 374
    },
    "..."
  ],
  "por_regiao": [
    {
      "nome": "24°S 63°O",
      "latitude": -24,
      "longitude": -63,
      "x": 0.28035714285714275,
      "y": 0.688,
      "total_equipamentos": 5,
      "score_medio": 31.8
    },
    "..."
  ],
  "tendencia": [
    { "dia": "2025-12-28", "score_medio": 46.35, "avaliacoes": 11 },
    "..."
  ]
}
```

- `total_operadores` conta operadores distintos nas avaliações.
- `por_operacao` vem ordenado por `score_medio` desc. Avaliação sem `tipo_operacao` entra como
  `"desconhecida"`.
- `por_regiao` agrupa equipamentos em células de 3° pela posição da última avaliação. Devolve no
  máximo 14 células, as de mais equipamentos. `x` e `y` são a posição projetada em 0–1 para o mapa.
  Equipamento sem avaliação fica de fora.
- `tendencia` é a média diária de score nos últimos `dias` **com dados**, não dias corridos. O seed
  cobre 2025 e a ingestão grava em 2026: uma janela de calendário devolveria um ponto só, porque não
  há nada entre as duas pontas. Por isso quem exibe a série deve rotular o eixo com `dia`, não com
  "N dias atrás".

## GET /tendencias

Série de score por grupo, num dos três eixos que o enunciado da Sprint 4 pede: *"tendências de
risco por equipamento, região ou tipo de operação"*. Alimenta a tela Relatórios. Contrato proposto
pelo front (PR #14) e implementado sem mudança de shape.

| Parâmetro | Tipo | Default | Regra |
|---|---|---|---|
| `eixo` | `equipamento` \| `regiao` \| `operacao` | obrigatório | outro valor → `422` |
| `dias` | int | `30` | 1–365. Janela em **dias com dados**, mesma semântica de `tendencia` em `/kpis` |
| `limite` | int | `5` | 1–20. Quantos grupos devolver |
| `chave` | string | — | Opcional. Restringe a um grupo e ignora `limite`. Para `regiao`, é o próprio rótulo da célula (`"24°S 51°O"`) |

```json
{
  "eixo": "operacao",
  "dias": 30,
  "janela": { "inicio": "2025-11-02", "fim": "2026-09-21", "dias_com_dados": 30 },
  "series": [
    {
      "chave": "transporte",
      "rotulo": "transporte",
      "score_medio": 52.78,
      "avaliacoes": 312,
      "pontos": [
        { "dia": "2025-11-02", "score_medio": 49.10, "avaliacoes": 9 },
        "..."
      ]
    },
    "..."
  ]
}
```

- **Janela:** os últimos `dias` dias com pelo menos uma avaliação **na base inteira**, não por grupo,
  para todas as séries dividirem o mesmo eixo X. `dias_com_dados` é menor que `dias` quando a base
  tem menos dias.
- **Lacuna, não zero:** um grupo só tem ponto nos dias em que ele tem avaliação. Dia sem dado não
  vira `0` nem é interpolado.
- **Agrupamento:**
  - `equipamento`: por `equipamento_id`.
  - `operacao`: por `tipo_operacao`; avaliação sem o campo entra como `"desconhecida"`.
  - `regiao`: célula de 3° pela posição **da própria avaliação**. Difere de `por_regiao` do `/kpis`,
    que usa a última posição do equipamento, mas o rótulo da célula é calculado pela mesma função
    nas duas rotas. Avaliação sem coordenada fica de fora.
- **Seleção:** os `limite` grupos de maior `score_medio` na janela (desempate: mais avaliações). Com
  `chave`, só aquele grupo. `score_medio` e `avaliacoes` do grupo são calculados sobre a janela.
- **Ordem:** `series` por `score_medio` desc; `pontos` por `dia` asc.
- **Sem dados:** `series: []` com `200`, inclusive com `chave` inexistente.
- **Exportação CSV:** sem rota própria; o front monta o arquivo a partir desta resposta.

## POST /avaliacoes

Ingestão de uma leitura de campo. O cliente envia **apenas o que observa**; o servidor busca o
cadastral no banco (tipo, idade, histórico de sinistros, `tem_iot`, intervalos de manutenção) e
**deriva** o que não pode ser forjado: `atraso_manutencao_pct`, `manutencao_atrasada` (Regra 14 de
`docs/data schema.md`) e `faixa_risco`. Responde `201`.

**Os cinco campos climáticos são opcionais.** Se ausentes, o servidor busca na Open-Meteo pela
coordenada. Se presentes, servem de fallback caso a API externa falhe.

A resposta traz `clima_origem` dizendo de onde veio o dado:

| valor | significado |
|---|---|
| `open-meteo` | enriquecido pela API externa |
| `payload` | Open-Meteo falhou; usados os valores enviados pelo cliente |
| `seed` | linha histórica, populada pelo seed em lote (só aparece nas consultas, nunca nesta resposta) |

Se a Open-Meteo falhar **e** o payload não trouxer o clima completo, a requisição é recusada com
`502`: o servidor não inventa clima para alimentar o modelo.

O modelo roda **antes** de gravar. Em seguida o servidor grava a avaliação e a predição. Se a
gravação da predição falhar, a avaliação é removida e a requisição responde `500`.

**Reenvio duplica.** A rota não tem chave de idempotência: reenviar o mesmo payload grava uma
segunda avaliação.

```json
// resposta 201
{
  "avaliacao_id": 5001,
  "equipamento_id": "EQ-0042",
  "risco_score": 69.47,
  "faixa_risco": "alto",
  "clima_origem": "open-meteo",
  "contribuicoes_por_grupo": {
    "ambiental": 17.7577,
    "geografico": 12.0574,
    "operacional": -2.0559,
    "equipamento": -4.9901,
    "operador": -0.9026,
    "manutencao": -0.0194
  },
  "top_fatores": [
    {
      "feature": "distancia_agua_m",
      "valor": 120.0,
      "shap_value": 11.5357,
      "grupo": "geografico"
    },
    {
      "feature": "precipitacao_mm",
      "valor": 42.0,
      "shap_value": 11.3671,
      "grupo": "ambiental"
    },
    "..."
  ],
  "modelo_versao": "xgboost-v1-baseline",
  "timestamp": "2026-08-24T13:02:53.465989+00:00"
}
```

## Armadilhas conhecidas

**1. `top_fatores_shap` tem dois formatos gravados.** As 5.000 predições do seed foram gravadas
com `{feature, group, shap_value}`; as geradas pela API usam `{feature, grupo, shap_value, valor}`.
A API **normaliza na leitura** e sempre devolve o formato em português. `valor` vem `null` quando a
predição é do seed, que não o gravou; trate como opcional.

**2. `valor` é o valor que entrou no modelo, não o que o usuário vê.** Para feature numérica é o
próprio número. Para categórica (`tipo_solo`, `tipo_operacao`, `condicao_clima`,
`tipo_equipamento`) é o código ordinal do encoder, e para booleana (`tem_iot`,
`manutencao_atrasada`) é `0` ou `1`. Para exibir, leia o rótulo em `ultima_avaliacao`.

**3. `contribuicoes_por_grupo` soma COM SINAL.** Positivo aumenta o risco, negativo reduz. Difere
de `shap_explainer.group_contributions()`, que soma `|SHAP|` para medir magnitude. A semântica com
sinal é a correta para exibir "+ aumenta / − reduz".

**4. Não reclassifique o score no cliente.** A faixa é derivada do score cru e gravada; o
`risco_score` devolvido tem duas casas. Um score cru de 33,004 é devolvido como `33.0` com faixa
`medio`. Recalcular a faixa a partir do número exibido daria `baixo`. Use sempre `faixa_risco`.
