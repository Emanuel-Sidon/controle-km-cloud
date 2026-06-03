# 🚌 Controle de KM - Versão Cloud (Render)

Versão otimizada para deploy no Render.com com avisos de dados temporários.

## 🚀 Deploy no Render

### 1. Criar conta no Render
- Acesse [render.com](https://render.com)
- Cadastre-se com GitHub ou e-mail

### 2. Criar repositório no GitHub
```bash
# Criar pasta do projeto
mkdir controle-km-cloud
cd controle-km-cloud

# Inicializar git
git init

# Copiar arquivos
cp /caminho/do/app_controle_km_cloud.py app.py
cp /caminho/do/requirements_cloud.txt requirements.txt

# Criar arquivo de configuração do Render
cat > render.yaml << 'EOF'
services:
  - type: web
    name: controle-km
    runtime: python
    plan: free
    buildCommand: "pip install -r requirements.txt"
    startCommand: "streamlit run app.py --server.port 10000 --server.address 0.0.0.0"
    envVars:
      - key: PYTHON_VERSION
        value: 3.9.0
EOF

# Commit e push
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/SEU_USUARIO/controle-km-cloud.git
git push -u origin main
```

### 3. Conectar no Render
1. No Render, clique em **"New +"** → **"Web Service"**
2. Conecte seu repositório GitHub
3. Selecione o repositório `controle-km-cloud`
4. Configure:
   - **Name**: `controle-km`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run app.py --server.port 10000 --server.address 0.0.0.0`
5. Clique em **"Create Web Service"**

### 4. Acessar o app
- O Render gerará uma URL: `https://controle-km.onrender.com`
- Compartilhe essa URL com sua equipe!

## ⚠️ Importante: Modo Cloud

| Aspecto | Comportamento |
|---------|--------------|
| **Dados** | Temporários — apagados quando o app reinicia |
| **Fotos** | Temporárias — apagadas quando o app reinicia |
| **E-mail** | Funciona normalmente — envie relatórios para preservar |
| **Sleep** | App "dorme" após 15 min de inatividade (plano gratuito) |

### Fluxo recomendado:
1. Cadastre viagens e fotos durante o dia
2. Ao final do dia, vá em **"📧 Enviar por E-mail"**
3. Envie o relatório ZIP para seu e-mail
4. Baixe o ZIP no PC como evidência permanente

## 🔐 Configurando E-mail

### Gmail:
1. Ative **Verificação em 2 etapas**
2. Gere uma **Senha de App** em: `Configurações → Segurança → Senhas de app`
3. Use essa senha no app (não sua senha normal!)

### Outlook:
1. Ative autenticação de 2 fatores
2. Gere senha de app em: `Configurações de segurança → Senhas de app`

## 📧 Estrutura do ZIP Enviado

```
relatorio_km.zip
├── relatorio_km.xlsx          # Excel com 4 abas
│   ├── Viagens
│   ├── Resumo Dia-Turno
│   ├── Resumo Ônibus
│   └── Resumo Mensal
└── fotos/
    ├── 1_inicial_viagem_1.jpg
    ├── 1_final_viagem_1.jpg
    └── ...
```

## 💰 Custo

| Plano | Preço | Recursos |
|-------|-------|----------|
| **Free** | $0 | Sleep após 15min, dados temporários |
| **Starter** | $7/mês | Sempre ligado, ideal para produção |

## 🆘 Suporte

Se o app não iniciar no Render, verifique os logs em:
Render Dashboard → seu serviço → Logs
