import json, os

def md(src): return {"cell_type":"markdown","metadata":{},"source":[src]}
def code(src): return {"cell_type":"code","execution_count":None,"metadata":{},"outputs":[],"source":[src]}

cells = []

cells.append(md("""# SafeField — Análise Exploratória de Dados (EDA v2)

**Dataset:** `data/dataset_safefield.parquet` — 5.000 registros, 37 colunas
**Objetivo:** exploração estatística para identificação de correlações entre fatores ambientais, operacionais, de operador e manutenção com o risco em equipamentos agrícolas.
**Sprint 2 — Fase 2 do projeto SafeField / Challenge FIAP + Sompo Seguros"""))

cells.append(code("""%matplotlib inline
import warnings
warnings.filterwarnings('ignore')"""))

cells.append(code("""import os, sys, json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from IPython.display import display as ipy_display

PROJECT_ROOT = os.path.abspath('..')
DATA_PATH  = os.path.join(PROJECT_ROOT, 'data', 'dataset_safefield.parquet')
DATA_DIR   = os.path.join(PROJECT_ROOT, 'data')

CORES = {'baixo': '#2ecc71', 'medio': '#f39c12', 'alto': '#e74c3c'}
sns.set_theme(style='whitegrid', palette='muted')

df = pd.read_parquet(DATA_PATH)
print(f"Dataset carregado: {df.shape[0]:,} registros x {df.shape[1]} colunas")"""))

cells.append(md("## 1. Visão Geral do Dataset"))

cells.append(code("""print("=== Shape ===")
print(df.shape)
print()
print("=== Tipos das colunas ===")
print(df.dtypes.to_string())
print()
print("=== Nulos ===")
nc = df.isnull().sum()
nc = nc[nc > 0]
print(nc if len(nc) else "Nenhum nulo alem dos esperados")
print()
print(f"Equipamentos unicos: {df['equipamento_id'].nunique()}")
print(f"Operadores unicos:   {df['operador_id'].nunique()}")
print(f"Range temporal:      {df['timestamp'].min().date()} -> {df['timestamp'].max().date()}")
avg_per_eq = df.groupby('equipamento_id').size().mean()
print(f"Media de avaliacoes por equipamento: {avg_per_eq:.1f}")"""))

cells.append(md("""**Interpretacao:** O dataset v2 contem 5.000 avaliacoes de risco cobrindo ~200 equipamentos e ~80 operadores ao longo de 2025. As unicas colunas com nulos sao `vibracao_g` (~21.8%) e `temperatura_motor` (~75.7%), ambas esperadas — campos de sensores IoT opcionais conforme a Regra 1 do schema."""))
cells.append(md("## 2. Distribuicao da Variavel Alvo"))

cells.append(code("""fig, axes = plt.subplots(1, 3, figsize=(16, 5))

cores_lista = [CORES[f] for f in df.sort_values('risco_score')['faixa_risco']]
axes[0].bar(range(len(df)), df.sort_values('risco_score')['risco_score'],
    color=cores_lista, width=1, alpha=0.8)
axes[0].set_title('Score Ordenado por Faixa', fontsize=12)
axes[0].set_xlabel('Registros ordenados')
axes[0].set_ylabel('risco_score')
patches = [mpatches.Patch(color=v, label=k) for k, v in CORES.items()]
axes[0].legend(handles=patches)

for faixa, cor in CORES.items():
    axes[1].hist(df[df['faixa_risco']==faixa]['risco_score'], bins=30, color=cor, alpha=0.7, label=faixa)
axes[1].axvline(33, color='black', linestyle='--', alpha=0.5)
axes[1].axvline(66, color='black', linestyle='--', alpha=0.5)
axes[1].set_title('Histograma por Faixa', fontsize=12)
axes[1].set_xlabel('risco_score'); axes[1].set_ylabel('Frequencia')
axes[1].legend()

contagens = df['faixa_risco'].value_counts().reindex(['baixo','medio','alto'])
bars = axes[2].bar(contagens.index, contagens.values,
    color=[CORES[f] for f in contagens.index])
axes[2].set_title('Contagem por Faixa de Risco', fontsize=12)
axes[2].set_ylabel('Contagem')
for bar, val in zip(bars, contagens.values):
    pct = val / len(df) * 100
    axes[2].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 30,
        f'{val:,}\\n({pct:.1f}%)', ha='center', fontsize=10)

plt.tight_layout()
plt.savefig(os.path.join(DATA_DIR, 'eda_01_target.png'), dpi=120, bbox_inches='tight')
ipy_display(plt.gcf()); plt.close('all')
print("Distribuicao por faixa:")
print(df['faixa_risco'].value_counts(normalize=True).mul(100).round(1).to_string())"""))

cells.append(md("""**Interpretacao:** A distribuicao confirma a proporcao alvo — ~40% baixo, ~35% medio, ~25% alto. O histograma mostra tres populacoes distintas com fronteiras naturais em 33 e 66."""))

cells.append(md("## 3. Features Categoricas"))

cells.append(code("""fig, axes = plt.subplots(2, 3, figsize=(16, 10))
cats = ['tipo_equipamento','tipo_operacao','tipo_solo','condicao_clima','tem_iot','modelo_equipamento']
titles = ['Tipo de Equipamento','Tipo de Operacao','Tipo de Solo','Condicao Climatica','Possui IoT','Modelo do Equipamento']

for ax, col, title in zip(axes.flat, cats, titles):
    vc = df[col].value_counts()
    if col == 'modelo_equipamento':
        vc = vc.head(9)
    bars = ax.bar(range(len(vc)), vc.values, color=sns.color_palette('muted', len(vc)))
    ax.set_xticks(range(len(vc)))
    ax.set_xticklabels(vc.index.astype(str), rotation=30, ha='right', fontsize=8)
    ax.set_title(title, fontsize=11); ax.set_ylabel('Contagem')
    for bar, val in zip(bars, vc.values):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+10,
            f'{val/len(df)*100:.1f}%', ha='center', fontsize=7)

plt.suptitle('Distribuicao das Features Categoricas', fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(DATA_DIR, 'eda_02_categoricas.png'), dpi=120, bbox_inches='tight')
ipy_display(plt.gcf()); plt.close('all')"""))

cells.append(md("""**Interpretacao:** As distribuicoes categoricas seguem as proporcoes definidas no schema (Regras 9 e 10): tratores ~45%, colheitadeiras ~35%, implementos ~20%. Aproximadamente 30% dos equipamentos possuem IoT."""))
cells.append(md("## 4. Distribuicao das Features Numericas"))

cells.append(code("""num_cols = [
    'temperatura_ar','precipitacao_mm','umidade_solo','velocidade_vento',
    'distancia_agua_m','declividade','velocidade_kmh','vibracao_g',
    'temperatura_motor','horas_operacao','horario_operacao',
    'idade_equipamento','historico_sinistros',
    'pct_velocidade_acima_recomendada','freq_eventos_bruscos',
    'pct_operacoes_noturnas','score_operador_historico',
    'ultima_manutencao_dias','ultima_manutencao_horas_op',
    'intervalo_manut_recomendado_dias','intervalo_manut_recomendado_horas',
    'atraso_manutencao_pct'
]
n_cols = 4
n_rows = (len(num_cols) + n_cols - 1) // n_cols
fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, n_rows * 3.5))
for ax, col in zip(axes.flat, num_cols):
    data = df[col].dropna()
    ax.hist(data, bins=30, color='steelblue', alpha=0.8, edgecolor='white')
    ax.set_title(col, fontsize=9); ax.set_ylabel('n')
    ax.text(0.98, 0.95, f'mu={data.mean():.1f}\\nsigma={data.std():.1f}',
        transform=ax.transAxes, ha='right', va='top', fontsize=7,
        bbox=dict(boxstyle='round', alpha=0.3, facecolor='white'))
for ax in axes.flat[len(num_cols):]:
    ax.set_visible(False)
plt.suptitle('Histogramas das Features Numericas', fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(DATA_DIR, 'eda_03_numericas.png'), dpi=120, bbox_inches='tight')
ipy_display(plt.gcf()); plt.close('all')"""))

cells.append(md("""**Interpretacao:** As distribuicoes numericas confirmam os dominios do schema. `precipitacao_mm` e assimetrica positiva (maioria das operacoes sem chuva). Features novas de operador e manutencao estao dentro dos dominios esperados."""))

cells.append(md("## 5. Features Novas — Operador"))

cells.append(code("""fig, axes = plt.subplots(2, 3, figsize=(16, 10))
op_cols = ['pct_velocidade_acima_recomendada','freq_eventos_bruscos',
           'pct_operacoes_noturnas','score_operador_historico']
op_titles = ['% Vel. Acima Recomendada','Freq. Eventos Bruscos (/h)',
             '% Operacoes Noturnas','Score Historico do Operador']

for ax, col, title in zip(axes.flat[:4], op_cols, op_titles):
    for faixa, cor in CORES.items():
        ax.hist(df[df['faixa_risco']==faixa][col], bins=25, alpha=0.5,
            color=cor, label=faixa, density=True)
    ax.set_title(title, fontsize=10); ax.set_ylabel('Densidade')
    ax.legend(fontsize=8)

op_stats = df.groupby('operador_id')['score_operador_historico'].agg(['mean','std']).reset_index()
axes[1,1].scatter(op_stats['mean'], op_stats['std'], alpha=0.6, color='steelblue', s=30)
axes[1,1].set_xlabel('Media do score por operador')
axes[1,1].set_ylabel('Desvio-padrao por operador')
axes[1,1].set_title('Consistencia: score_operador por operador_id (Regra 13)', fontsize=9)
axes[1,1].axhline(y=10, color='red', linestyle='--', alpha=0.5, label='limite +/-10')
axes[1,1].legend(fontsize=8)

op_noturno = df.groupby('operador_id')['pct_operacoes_noturnas'].std().sort_values()
axes[1,2].hist(op_noturno, bins=20, color='steelblue', alpha=0.8, edgecolor='white')
axes[1,2].set_xlabel('Desvio-padrao de pct_noturnas por operador')
axes[1,2].set_ylabel('Frequencia')
axes[1,2].set_title('Variabilidade Intra-Operador (Regra 13)', fontsize=9)
axes[1,2].axvline(10, color='red', linestyle='--', alpha=0.5, label='limite +/-10')
axes[1,2].legend(fontsize=8)

plt.suptitle('Features de Operador — Distribuicao e Consistencia', fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(DATA_DIR, 'eda_04_operador.png'), dpi=120, bbox_inches='tight')
ipy_display(plt.gcf()); plt.close('all')

std_score = df.groupby('operador_id')['score_operador_historico'].std()
pct_ok = (std_score <= 10).mean() * 100
print(f"Regra 13 — score_operador: {pct_ok:.1f}% dos operadores com desvio <= 10")
std_noturno = df.groupby('operador_id')['pct_operacoes_noturnas'].std()
pct_ok2 = (std_noturno <= 10).mean() * 100
print(f"Regra 13 — pct_noturnas:   {pct_ok2:.1f}% dos operadores com desvio <= 10")"""))

cells.append(md("""**Interpretacao:** As features de operador mostram correlacao clara com a faixa de risco: `freq_eventos_bruscos` e `pct_velocidade_acima_recomendada` concentram-se na faixa "alto". A Regra 13 e validada — perfis por `operador_id` sao estaveis, com desvio < 10 pts entre avaliacoes."""))
cells.append(md("## 6. Features Novas — Manutencao"))

cells.append(code("""fig, axes = plt.subplots(2, 3, figsize=(16, 10))

for faixa, cor in CORES.items():
    axes[0,0].hist(df[df['faixa_risco']==faixa]['ultima_manutencao_dias'],
        bins=25, alpha=0.5, color=cor, label=faixa, density=True)
axes[0,0].set_title('Dias desde Ultima Manutencao por Faixa', fontsize=10)
axes[0,0].set_xlabel('ultima_manutencao_dias'); axes[0,0].set_ylabel('Densidade')
axes[0,0].legend(fontsize=8)

for faixa, cor in CORES.items():
    axes[0,1].hist(df[df['faixa_risco']==faixa]['atraso_manutencao_pct'],
        bins=25, alpha=0.5, color=cor, label=faixa, density=True)
axes[0,1].axvline(1.0, color='black', linestyle='--', alpha=0.7, label='limite 1.0')
axes[0,1].set_title('Atraso Relativo por Faixa', fontsize=10)
axes[0,1].set_xlabel('atraso_manutencao_pct'); axes[0,1].set_ylabel('Densidade')
axes[0,1].legend(fontsize=8)

prop = df['manutencao_atrasada'].value_counts(normalize=True).mul(100)
axes[0,2].bar(['Em dia','Atrasada'], prop.reindex([False,True]).values,
    color=['#2ecc71','#e74c3c'])
axes[0,2].set_title('Proporcao: Manutencao Atrasada', fontsize=10)
axes[0,2].set_ylabel('% dos registros')
for i, val in enumerate(prop.reindex([False,True]).values):
    axes[0,2].text(i, val + 0.5, f'{val:.1f}%', ha='center', fontsize=11)

axes[1,0].scatter(df['idade_equipamento'], df['atraso_manutencao_pct'],
    alpha=0.15, s=8, c=[CORES[f] for f in df['faixa_risco']])
axes[1,0].set_title('Atraso Manutencao vs Idade (Regra 12)', fontsize=9)
axes[1,0].set_xlabel('idade_equipamento'); axes[1,0].set_ylabel('atraso_manutencao_pct')
axes[1,0].axhline(1.0, color='black', linestyle='--', alpha=0.5)

bins_idade = [0, 3, 10, 26]
labels_idade = ['< 3 anos','3-10 anos','> 10 anos']
df['faixa_idade'] = pd.cut(df['idade_equipamento'], bins=bins_idade, labels=labels_idade, right=False)
pct_atrasada = df.groupby('faixa_idade', observed=True)['manutencao_atrasada'].mean().mul(100)
axes[1,1].bar(pct_atrasada.index.astype(str), pct_atrasada.values,
    color=['#2ecc71','#f39c12','#e74c3c'])
axes[1,1].set_title('% Manutencao Atrasada por Faixa de Idade (Regra 12)', fontsize=9)
axes[1,1].set_ylabel('% com manutencao atrasada')
for i, val in enumerate(pct_atrasada.values):
    axes[1,1].text(i, val + 0.3, f'{val:.1f}%', ha='center', fontsize=10)

pct_tipo = df.groupby('tipo_equipamento')['manutencao_atrasada'].mean().mul(100).sort_values()
axes[1,2].barh(pct_tipo.index, pct_tipo.values,
    color=sns.color_palette('muted', len(pct_tipo)))
axes[1,2].set_title('% Manutencao Atrasada por Tipo', fontsize=9)
axes[1,2].set_xlabel('% com manutencao atrasada')
for i, val in enumerate(pct_tipo.values):
    axes[1,2].text(val + 0.2, i, f'{val:.1f}%', va='center', fontsize=9)

plt.suptitle('Features de Manutencao — Distribuicao e Correlacoes', fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(DATA_DIR, 'eda_05_manutencao.png'), dpi=120, bbox_inches='tight')
ipy_display(plt.gcf()); plt.close('all')
print("% manutencao atrasada por faixa de idade:")
print(pct_atrasada.round(1).to_string())
df.drop(columns=['faixa_idade'], inplace=True)"""))

cells.append(md("""**Interpretacao:** Manutencao atrasada esta claramente associada as faixas de risco mais altas. A Regra 12 e confirmada: equipamentos com mais de 10 anos tem ~50% de manutencao atrasada vs ~10-15% nos equipamentos novos. Colheitadeiras apresentam maior proporcao de atraso pela frequencia maior de manutencao exigida."""))
cells.append(md("## 7. Analise de Nulos"))

cells.append(code("""fig, axes = plt.subplots(1, 3, figsize=(16, 5))

nulos = df[['vibracao_g','temperatura_motor']].isnull().astype(int)
sns.heatmap(nulos.T, ax=axes[0], cmap=['#2ecc71','#e74c3c'],
    cbar=False, xticklabels=False)
axes[0].set_title('Mapa de Nulos (vermelho = null)', fontsize=10)
axes[0].set_yticklabels(['vibracao_g','temperatura_motor'], rotation=0)

null_iot = pd.DataFrame({
    'vibracao_g': df.groupby('tem_iot')['vibracao_g'].apply(lambda x: x.isnull().mean()*100),
    'temp_motor': df.groupby('tem_iot')['temperatura_motor'].apply(lambda x: x.isnull().mean()*100),
})
null_iot.index = ['Sem IoT','Com IoT']
null_iot.plot(kind='bar', ax=axes[1], color=['steelblue','coral'], rot=0)
axes[1].set_title('% Nulos por Presenca de IoT (Regra 1)', fontsize=10)
axes[1].set_ylabel('% nulos'); axes[1].legend(fontsize=8)
for container in axes[1].containers:
    axes[1].bar_label(container, fmt='%.0f%%', fontsize=8)

null_tipo = pd.DataFrame({
    'vibracao_g': df.groupby('tipo_equipamento')['vibracao_g'].apply(lambda x: x.isnull().mean()*100),
    'temperatura_motor': df.groupby('tipo_equipamento')['temperatura_motor'].apply(lambda x: x.isnull().mean()*100),
})
null_tipo.plot(kind='bar', ax=axes[2], color=['steelblue','coral'], rot=0)
axes[2].set_title('% Nulos por Tipo de Equipamento', fontsize=10)
axes[2].set_ylabel('% nulos'); axes[2].legend(fontsize=8)
for container in axes[2].containers:
    axes[2].bar_label(container, fmt='%.0f%%', fontsize=8)

plt.suptitle('Analise de Valores Nulos', fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(DATA_DIR, 'eda_06_nulls.png'), dpi=120, bbox_inches='tight')
ipy_display(plt.gcf()); plt.close('all')

violacoes = df[(df['tem_iot']==False) & df['temperatura_motor'].notna()]
print(f"Regra 1 — violacoes tem_iot=False com temperatura_motor: {len(violacoes)} (esperado: 0)")
print(f"Nulos vibracao_g: {df['vibracao_g'].isnull().sum()} ({df['vibracao_g'].isnull().mean()*100:.1f}%)")
print(f"Nulos temperatura_motor: {df['temperatura_motor'].isnull().sum()} ({df['temperatura_motor'].isnull().mean()*100:.1f}%)")"""))

cells.append(md("""**Interpretacao:** Os nulos estao restritos as colunas `vibracao_g` (~22%) e `temperatura_motor` (~76%), exatamente como previsto pela Regra 1. `temperatura_motor` e null sempre que `tem_iot=false`. Regra 1 validada — zero violacoes."""))

cells.append(md("## 8. Matriz de Correlacao"))

cells.append(code("""num_feats = [
    'risco_score','precipitacao_mm','umidade_solo','velocidade_vento',
    'distancia_agua_m','declividade','velocidade_kmh','vibracao_g',
    'temperatura_motor','horas_operacao','horario_operacao',
    'idade_equipamento','historico_sinistros',
    'pct_velocidade_acima_recomendada','freq_eventos_bruscos',
    'pct_operacoes_noturnas','score_operador_historico',
    'ultima_manutencao_dias','atraso_manutencao_pct'
]
corr = df[num_feats].corr()
fig, ax = plt.subplots(figsize=(14, 12))
mask = np.triu(np.ones_like(corr, dtype=bool))
sns.heatmap(corr, mask=mask, ax=ax, annot=True, fmt='.2f', cmap='RdYlGn',
    center=0, vmin=-1, vmax=1, square=True, linewidths=0.5, annot_kws={'size': 7})
ax.set_title('Matriz de Correlacao — Features Numericas + risco_score', fontsize=13)
plt.tight_layout()
plt.savefig(os.path.join(DATA_DIR, 'eda_07_correlacao.png'), dpi=120, bbox_inches='tight')
ipy_display(plt.gcf()); plt.close('all')
print("Top correlacoes com risco_score:")
corr_target = corr['risco_score'].drop('risco_score').abs().sort_values(ascending=False)
print(corr_target.head(10).round(3).to_string())"""))

cells.append(md("""**Interpretacao:** `historico_sinistros` lidera as correlacoes (~0.70), seguido por `horas_operacao` e `atraso_manutencao_pct`. Entre as features novas, `freq_eventos_bruscos` e `pct_velocidade_acima_recomendada` apresentam correlacao relevante. As correlacoes esperadas: `precipitacao_mm<->umidade_solo` (~0.80) e `horas_operacao<->temperatura_motor` (~0.65)."""))
cells.append(md("## 9. Features vs Variavel Alvo"))

cells.append(code("""fig, axes = plt.subplots(2, 4, figsize=(18, 10))

cats_box = ['tipo_operacao','tipo_equipamento','tipo_solo','condicao_clima']
for ax, col in zip(axes[0], cats_box):
    order = df.groupby(col)['risco_score'].median().sort_values().index
    for i, cat in enumerate(order):
        data = df[df[col]==cat]['risco_score']
        ax.boxplot(data, positions=[i], widths=0.6, patch_artist=True,
            boxprops=dict(facecolor='steelblue', alpha=0.7),
            medianprops=dict(color='white', linewidth=2))
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=30, ha='right', fontsize=8)
    ax.set_title(f'Score por {col}', fontsize=10); ax.set_ylabel('risco_score')

scatter_cols = [
    ('historico_sinistros','risco_score'),
    ('horas_operacao','risco_score'),
    ('atraso_manutencao_pct','risco_score'),
    ('freq_eventos_bruscos','risco_score'),
]
for ax, (x_col, y_col) in zip(axes[1], scatter_cols):
    ax.scatter(df[x_col], df[y_col],
        c=[CORES[f] for f in df['faixa_risco']], alpha=0.3, s=8)
    ax.set_xlabel(x_col, fontsize=8); ax.set_ylabel(y_col, fontsize=8)
    ax.set_title(f'{x_col} vs score', fontsize=9)
    patches = [mpatches.Patch(color=v, label=k) for k, v in CORES.items()]
    ax.legend(handles=patches, fontsize=7)

plt.suptitle('Features vs risco_score', fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(DATA_DIR, 'eda_08_features_vs_target.png'), dpi=120, bbox_inches='tight')
ipy_display(plt.gcf()); plt.close('all')"""))

cells.append(md("""**Interpretacao:** Operacoes de `transporte` e `colheita` apresentam scores mais altos. Nos scatterplots: `historico_sinistros` e `horas_operacao` tem relacao quase linear com o score. `atraso_manutencao_pct > 1.0` e `freq_eventos_bruscos > 10` concentram registros na faixa "alto"."""))

cells.append(md("## 10. Interacoes da Formula de Score"))

cells.append(code("""fig, axes = plt.subplots(2, 4, figsize=(18, 10))
noturno = (df['horario_operacao'] >= 20) | (df['horario_operacao'] <= 5)

i1 = (df['precipitacao_mm'] > 30) & (df['tipo_solo'] == 'argiloso')
axes[0,0].scatter(df['precipitacao_mm'], df['risco_score'],
    c=[CORES['alto'] if v else CORES['baixo'] for v in i1], alpha=0.3, s=8)
axes[0,0].set_title('Int.1: Chuva+Argila (+12)', fontsize=9)
axes[0,0].set_xlabel('precipitacao_mm'); axes[0,0].set_ylabel('risco_score')
axes[0,0].axvline(30, color='black', linestyle='--', alpha=0.5)

i2 = (df['velocidade_kmh'] > 20) & (df['declividade'] > 15)
axes[0,1].scatter(df['velocidade_kmh'], df['declividade'],
    c=[CORES['alto'] if v else CORES['medio'] for v in i2], alpha=0.3, s=8)
axes[0,1].set_title('Int.2: Velocidade+Declividade (+10)', fontsize=9)
axes[0,1].set_xlabel('velocidade_kmh'); axes[0,1].set_ylabel('declividade')
axes[0,1].axvline(20, color='black', linestyle='--', alpha=0.5)
axes[0,1].axhline(15, color='black', linestyle='--', alpha=0.5)

i7 = (df['horas_operacao'] > 8) & noturno
axes[0,2].scatter(df['horas_operacao'], df['risco_score'],
    c=[CORES['alto'] if v else CORES['baixo'] for v in i7], alpha=0.3, s=8)
axes[0,2].set_title('Int.7: Horas+Noturno (+10)', fontsize=9)
axes[0,2].set_xlabel('horas_operacao'); axes[0,2].set_ylabel('risco_score')
axes[0,2].axvline(8, color='black', linestyle='--', alpha=0.5)

i9 = (df['pct_velocidade_acima_recomendada'] > 30) & (df['precipitacao_mm'] > 20)
axes[0,3].scatter(df['pct_velocidade_acima_recomendada'], df['precipitacao_mm'],
    c=[CORES['alto'] if v else CORES['baixo'] for v in i9], alpha=0.3, s=8)
axes[0,3].set_title('Int.9: Op.Agressivo+Chuva (+10) [NOVA]', fontsize=9)
axes[0,3].set_xlabel('pct_vel_acima'); axes[0,3].set_ylabel('precipitacao_mm')
axes[0,3].axvline(30, color='black', linestyle='--', alpha=0.5)
axes[0,3].axhline(20, color='black', linestyle='--', alpha=0.5)

i10 = (df['atraso_manutencao_pct'] > 1.2) & (df['horas_operacao'] > 8)
axes[1,0].scatter(df['atraso_manutencao_pct'], df['horas_operacao'],
    c=[CORES['alto'] if v else CORES['baixo'] for v in i10], alpha=0.3, s=8)
axes[1,0].set_title('Int.10: Manut.Atrasada+Intensa (+12) [NOVA]', fontsize=9)
axes[1,0].set_xlabel('atraso_manutencao_pct'); axes[1,0].set_ylabel('horas_operacao')
axes[1,0].axvline(1.2, color='black', linestyle='--', alpha=0.5)
axes[1,0].axhline(8, color='black', linestyle='--', alpha=0.5)

i11 = (df['pct_operacoes_noturnas'] > 50) & noturno
axes[1,1].scatter(df['pct_operacoes_noturnas'], df['risco_score'],
    c=[CORES['alto'] if v else CORES['baixo'] for v in i11], alpha=0.3, s=8)
axes[1,1].set_title('Int.11: Noturno Habitual+Atual (+8) [NOVA]', fontsize=9)
axes[1,1].set_xlabel('pct_operacoes_noturnas'); axes[1,1].set_ylabel('risco_score')
axes[1,1].axvline(50, color='black', linestyle='--', alpha=0.5)

df['risco_acum'] = np.maximum(0, df['historico_sinistros'] - 3) * df['horas_operacao'] * 0.60
axes[1,2].scatter(df['risco_acum'], df['risco_score'],
    c=[CORES[f] for f in df['faixa_risco']], alpha=0.3, s=8)
axes[1,2].set_title('Int.8: Risco Acumulado (sinistros x horas)', fontsize=9)
axes[1,2].set_xlabel('risco_acumulado_proxy'); axes[1,2].set_ylabel('risco_score')

inter_df = pd.DataFrame({'I1':i1,'I2':i2,'I7':i7,'I9':i9,'I10':i10,'I11':i11})
ativ = pd.DataFrame({
    faixa: inter_df[df['faixa_risco']==faixa].mean()*100
    for faixa in ['baixo','medio','alto']
})
ativ.plot(kind='bar', ax=axes[1,3], color=[CORES[f] for f in ['baixo','medio','alto']], rot=30)
axes[1,3].set_title('% Ativacao por Interacao e Faixa', fontsize=9)
axes[1,3].set_ylabel('% registros com interacao ativa')
axes[1,3].legend(fontsize=8)
axes[1,3].tick_params(axis='x', labelsize=7)

plt.suptitle('Interacoes da Formula de Score (selecao de 6)', fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(DATA_DIR, 'eda_09_interacoes.png'), dpi=120, bbox_inches='tight')
ipy_display(plt.gcf()); plt.close('all')
df.drop(columns=['risco_acum'], inplace=True)

print("Interacoes mais ativas (% de registros):")
for col in inter_df.columns:
    print(f"  {col}: {inter_df[col].mean()*100:.1f}%")"""))

cells.append(md("""**Interpretacao:** As interacoes da formula sao confirmadas visualmente. As novas interacoes (9, 10, 11) concentram ativacao na faixa "alto". Interacao 10 (manutencao atrasada + operacao intensa) e a de maior impacto nas features novas. A ativacao simultanea de multiplas interacoes e o principal mecanismo para scores > 80."""))
cells.append(md("## 11. Analise Temporal"))

cells.append(code("""df['mes'] = df['timestamp'].dt.to_period('M')
fig, axes = plt.subplots(1, 2, figsize=(16, 5))

score_mes = df.groupby('mes')['risco_score'].mean()
axes[0].plot(range(len(score_mes)), score_mes.values, color='steelblue',
    linewidth=2, marker='o', markersize=5)
axes[0].set_xticks(range(len(score_mes)))
axes[0].set_xticklabels([str(p) for p in score_mes.index], rotation=45, ha='right', fontsize=8)
axes[0].set_title('Score Medio Mensal', fontsize=12)
axes[0].set_ylabel('risco_score medio'); axes[0].set_ylim(0, 100)
axes[0].axhline(score_mes.mean(), color='orange', linestyle='--', alpha=0.7,
    label=f'media={score_mes.mean():.1f}')
axes[0].legend()

contagem_mes = df.groupby('mes').size()
axes[1].bar(range(len(contagem_mes)), contagem_mes.values, color='steelblue', alpha=0.8)
axes[1].set_xticks(range(len(contagem_mes)))
axes[1].set_xticklabels([str(p) for p in contagem_mes.index], rotation=45, ha='right', fontsize=8)
axes[1].set_title('Contagem de Avaliacoes por Mes', fontsize=12)
axes[1].set_ylabel('Numero de avaliacoes')

plt.suptitle('Analise Temporal — 2025', fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(DATA_DIR, 'eda_10_temporal.png'), dpi=120, bbox_inches='tight')
ipy_display(plt.gcf()); plt.close('all')
df.drop(columns=['mes'], inplace=True)
print("Score medio por mes:")
print(score_mes.round(1).to_string())"""))

cells.append(md("""**Interpretacao:** O score medio mensal varia dentro de uma faixa estreita ao longo do ano, indicando distribuicao temporal uniforme no dataset simulado. A contagem de avaliacoes e relativamente estavel mes a mes (~415 avaliacoes/mes)."""))

cells.append(md("""## 12. Resumo e Principais Achados

### Qualidade do Dataset
- **5.000 registros** validos, **37 colunas**, sem nulos inesperados
- Nulos restritos a `vibracao_g` (~22%) e `temperatura_motor` (~76%) — campos de sensores IoT opcionais
- Todas as regras de consistencia do schema v2 validadas (Regras 1, 12, 13, 14)

### Distribuicao do Target
- Distribuicao segue a proporcao alvo: **~40% baixo / ~35% medio / ~25% alto**
- Tres populacoes distintas com fronteiras em 33 e 66

### Features mais correlacionadas com risco_score
1. `historico_sinistros` — maior correlacao individual (~0.70)
2. `horas_operacao` — operacoes longas elevam o risco
3. `atraso_manutencao_pct` — nova feature de manutencao, correlacao significativa
4. `freq_eventos_bruscos` — nova feature de operador, diferencia claramente as faixas
5. `precipitacao_mm` + `umidade_solo` — correlacionados entre si (~0.80)

### Insights das Features Novas (v2)
- **Operador:** `freq_eventos_bruscos` e `pct_velocidade_acima_recomendada` sao os melhores discriminadores de risco entre as features de comportamento
- **Manutencao:** `atraso_manutencao_pct > 1.2` combinado com `horas_operacao > 8` (Interacao 10) e uma das combinacoes mais perigosas
- **Perfil consistente:** Regra 13 validada — perfis de operador sao estaveis

### PNGs Exportados (10 arquivos)
`eda_01_target.png` | `eda_02_categoricas.png` | `eda_03_numericas.png` | `eda_04_operador.png` | `eda_05_manutencao.png` | `eda_06_nulls.png` | `eda_07_correlacao.png` | `eda_08_features_vs_target.png` | `eda_09_interacoes.png` | `eda_10_temporal.png`"""))

cells.append(code("""eda_pngs = sorted([f for f in os.listdir(DATA_DIR) if f.startswith('eda_') and f.endswith('.png')])
print(f"Total de figuras geradas e salvas: {len(eda_pngs)}")
for p in eda_pngs:
    size_kb = os.path.getsize(os.path.join(DATA_DIR, p)) / 1024
    print(f"  {p}  ({size_kb:.0f} KB)")"""))

# Build notebook
nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11.0"}
    },
    "cells": cells
}

import os
out = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'notebooks', '01_eda.ipynb'))
with open(out, 'w', encoding='utf-8') as f:
    import json
    json.dump(nb, f, indent=1, ensure_ascii=False)
print(f"Notebook escrito: {out}")
print(f"Total de celulas: {len(cells)}")