#!/bin/bash
# Script de deploy rápido para Render

echo "🚀 Preparando deploy no Render..."

# Verificar se tem git
if ! command -v git &> /dev/null; then
    echo "❌ Git não instalado. Instale primeiro."
    exit 1
fi

# Criar pasta do projeto
PROJECT_NAME="controle-km-cloud"
mkdir -p $PROJECT_NAME
cd $PROJECT_NAME

# Copiar arquivos (ajuste os caminhos se necessário)
echo "📁 Copiando arquivos..."
cp ../app_controle_km_cloud.py app.py 2>/dev/null || cp app_controle_km_cloud.py app.py 2>/dev/null || echo "⚠️ Arquivo app_controle_km_cloud.py não encontrado. Coloque-o nesta pasta manualmente."
cp ../requirements_cloud.txt requirements.txt 2>/dev/null || cp requirements_cloud.txt requirements.txt 2>/dev/null || echo "⚠️ Arquivo requirements_cloud.txt não encontrado."

# Criar render.yaml
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

# Inicializar git
git init
git add .
git commit -m "Initial commit - Controle de KM Cloud"

echo ""
echo "✅ Projeto preparado!"
echo ""
echo "Próximos passos:"
echo "1. Crie um repositório no GitHub (sem README)"
echo "2. Execute: git remote add origin https://github.com/SEU_USUARIO/controle-km-cloud.git"
echo "3. Execute: git push -u origin main"
echo "4. No Render.com, clique 'New +' → 'Web Service' e conecte o GitHub"
echo ""
echo "📁 Arquivos na pasta $PROJECT_NAME:"
ls -la
