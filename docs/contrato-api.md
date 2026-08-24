# Contrato da API — congelado

> Gerado a partir da API **em execução**, não de proposta. Espelho legível de
> `docs/openapi.json` (exportado do FastAPI). Com a API no ar, o Swagger vive em
> `http://localhost:8000/docs`.
>
> **Regra do contrato:** qualquer mudança de shape aqui precisa ser avisada às duas
> frentes antes de entrar. É o único ponto onde backend e frontend quebram em silêncio.

## Autenticação

Todas as rotas exigem `Authorization: Bearer <token>`, exceto `POST /auth/token` e `GET /health`.

- Sem token → `401 {"detail": "Token ausente."}`
- Token inválido/expirado → `401 {"detail": "Token invalido ou expirado."}`
- Credencial errada → `401 {"detail": "Usuario ou senha invalidos."}`
- Equipamento inexistente → `404 {"detail": "Equipamento 'EQ-9999' nao encontrado."}`
- Payload inválido → `422` com `detail[]` do Pydantic (campo em `loc`, motivo em `msg`)

Token expira em 480 min. Perfis: `operador`, `gestor`, `analista` (sem escopo de dados distinto nesta entrega).

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

## GET /equipamentos

Query params: `faixa` (`baixo|medio|alto`), `busca` (id ou modelo). Ordenado por `risco_score` desc.

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

## GET /equipamentos/{id}

`ultima_avaliacao` traz as 30 colunas da linha em `avaliacoes`. `historico` é ordenado do mais antigo ao mais recente.

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

## GET /alertas

Query params: `limite` (1–100, default 7), `faixa_minima` (`baixo|medio|alto`, default `medio`).

**Regra de alerta** (portada de `buildAlertas`, que rodava no cliente): avaliações ordenadas
da mais recente para a mais antiga, descartando as de faixa abaixo de `faixa_minima`,
limitadas a `limite`. O default `faixa_minima=medio` reproduz o `faixa_risco !== 'baixo'` anterior.

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
            "mensagem": "EQ-0042 \u00b7 score 69 \u00b7 risco alto"
        },
        {
            "avaliacao_id": 870,
            "equipamento_id": "EQ-0173",
            "operador_id": "OP-0010",
            "risco_score": 100.0,
            "faixa_risco": "alto",
            "tipo_operacao": "transporte",
            "timestamp": "2025-12-31T14:19:16+00:00",
            "mensagem": "EQ-0173 \u00b7 score 100 \u00b7 risco alto"
        }
    ]
}
```

## GET /kpis

Cobre as três visões que o enunciado exige: por equipamento (rota acima), **por operação** e **por região**.

```json
{
  "kpis": {
    "total_equipamentos": 200,
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
    {
      "tipo_operacao": "colheita",
      "total_avaliacoes": 1479,
      "score_medio": 51.18,
      "avaliacoes_risco_alto": 433
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
  ]
}
```

## POST /avaliacoes

Ingestão de uma leitura de campo. O cliente envia **apenas o que observa**; o servidor busca o
cadastral no banco (tipo, idade, histórico de sinistros, `tem_iot`, intervalos de manutenção) e
**deriva** o que não pode ser forjado: `atraso_manutencao_pct`, `manutencao_atrasada` (Regra 14 de
`docs/data schema.md`) e `faixa_risco`.

Os cinco campos climáticos são obrigatórios hoje. Quando o enriquecimento via Open-Meteo entrar
(RF-05), passam a **opcionais** — mudança aditiva, nada quebra.

```json
// resposta 201
{
  "avaliacao_id": 5001,
  "equipamento_id": "EQ-0042",
  "risco_score": 69.47,
  "faixa_risco": "alto",
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

## Duas armadilhas conhecidas

**1. `top_fatores_shap` tinha dois formatos.** As 5.000 predições do seed foram gravadas com
`{feature, group, shap_value}`; as geradas pela API usam `{feature, grupo, shap_value, valor}`.
A API **normaliza na leitura** e sempre devolve o formato em português. `valor` vem `null` quando
a predição é do seed, que não o gravou — trate como opcional.

**2. `contribuicoes_por_grupo` soma COM SINAL.** Positivo aumenta o risco, negativo reduz. Difere
de `shap_explainer.group_contributions()`, que soma `|SHAP|` para medir magnitude. A semântica com
sinal é a correta para exibir "+ aumenta / − reduz".
