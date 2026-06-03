# 🚌 Controle de KM Rodado - Ônibus

Aplicação em Python/Streamlit para controle de quilometragem rodada por dia e turno, com **análise temporal completa** e **fotos de evidência**.

## ✅ Funcionalidades

### Cadastro
- **Nova Viagem**: Registre data, turno (ADM, A, B, C), número do ônibus, KM inicial/final e passageiros
- **Fotos de Evidência**: Tire fotos do hodômetro (KM inicial e final) como comprovação
- **Extração automática**: Dia da semana, semana do ano, mês e ano são calculados automaticamente

### Dashboard
- Cards com métricas em tempo real (KM hoje, passageiros, ônibus ativos)
- **Comparativos rápidos**: Semana atual vs anterior, Mês atual vs anterior
- Gráficos por turno
- Tendência dos últimos 7 dias

### Relatórios por Período
- Filtre por data, turno e **ano**
- Gráficos de KM por dia e por ônibus
- Tabelas detalhadas por dia/turno e por ônibus
- Exportação Excel (3 abas) e CSV

### 📈 Análise Temporal
- **Comparativo Semanal**: Semana atual vs anterior com variação percentual
- **Comparativo Mensal**: Mês atual vs anterior com variação percentual
- **KM por Semana do Ano**: Gráfico de barras semanal
- **KM por Mês**: Gráfico mensal completo
- **Análise por Dia da Semana**: Descubra quais dias são mais produtivos
- **Tendência**: Análise de 7 a 90 dias com médias
- **Resumo Mês a Mês**: Tabela comparativa completa

### 📸 Fotos de Evidência
- Upload de foto do **KM Inicial** e **KM Final** do hodômetro
- Preview das fotos antes de salvar
- Visualização das fotos em cada registro
- Fotos salvas automaticamente na pasta `fotos_evidencias/`
- Fotos são **excluídas automaticamente** ao excluir a viagem
- Badge indicador de fotos na lista de registros

### Gerenciamento
- Busca por ônibus, filtro por turno e **mês**
- Visualize detalhes completos e fotos expandindo cada registro
- Exclua registros individualmente (com fotos)
- Limpe todos os dados (com fotos)

## 🚀 Como Executar

### Instalação Local

1. Instale o Python 3.8+ (se não tiver)
2. Baixe os arquivos `app_controle_km.py` e `requirements.txt`
3. Abra o terminal na pasta dos arquivos:

```bash
pip install -r requirements.txt
streamlit run app_controle_km.py
```

4. O navegador abrirá automaticamente em `http://localhost:8501`

> Se `streamlit` não for reconhecido, use: `python -m streamlit run app_controle_km.py`

## 📸 Como usar as Fotos de Evidência

1. No cadastro de nova viagem, role até a seção **"Fotos de Evidência"**
2. Clique em **"Browse files"** e selecione a foto do hodômetro
3. Você verá um **preview** da foto antes de salvar
4. Faça o mesmo para o KM inicial e final
5. As fotos serão salvas automaticamente na pasta `fotos_evidencias/`
6. Na lista de registros, clique em **"Ver detalhes e fotos"** para visualizar

## 📊 Estrutura dos Dados

Cada viagem registra:
| Campo | Descrição |
|-------|-----------|
| data | Data da viagem |
| dia_semana | Segunda, Terça, etc. |
| semana_ano | Número da semana (1-53) |
| mes | Número do mês (1-12) |
| mes_nome | Janeiro, Fevereiro, etc. |
| ano | Ano da viagem |
| turno | ADM, A, B ou C |
| numero_onibus | Identificação do ônibus |
| km_inicial / km_final | Hodômetro |
| km_percorrido | Calculado automaticamente |
| passageiros | Quantidade transportada |
| tem_foto_inicial / tem_foto_final | Flag de evidência |
| foto_inicial / foto_final | Caminho do arquivo de foto |
| observacao | Campo livre |

## 💾 Armazenamento

- **Dados**: salvos automaticamente em `dados_viagens.json`
- **Fotos**: salvas na pasta `fotos_evidencias/` com nome no formato `viagem_{id}_inicial.jpg`
- Funciona 100% offline!

## 📁 Estrutura de Pastas

```
├── app_controle_km.py      # Aplicativo principal
├── requirements.txt        # Dependências
├── dados_viagens.json      # Banco de dados (gerado automaticamente)
└── fotos_evidencias/       # Pasta com as fotos (gerada automaticamente)
    ├── viagem_1_inicial.jpg
    ├── viagem_1_final.jpg
    ├── viagem_2_inicial.jpg
    └── ...
```

## 📈 Relatórios Temporais Disponíveis

1. **Semanal**: Comparativo semana a semana com variação %
2. **Mensal**: Comparativo mês a mês com variação %
3. **Dia da Semana**: Identifica padrões (ex: sextas têm mais KM?)
4. **Tendência**: Evolução diária com médias móveis
5. **Anual**: Resumo completo por mês e semana
