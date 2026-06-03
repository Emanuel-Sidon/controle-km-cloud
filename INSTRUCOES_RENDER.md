# 🚀 Deploy no Render - Passo a Passo

## 1. Preparar Arquivos

Baixe estes 3 arquivos:
- `app_controle_km_cloud.py`
- `requirements_cloud.txt`
- `README_CLOUD.md`

## 2. Criar Conta no Render

1. Acesse: https://render.com
2. Clique em **"Get Started for Free"**
3. Cadastre com **GitHub** (mais fácil) ou e-mail

## 3. Criar Repositório no GitHub

1. Acesse: https://github.com/new
2. Nome: `controle-km-cloud`
3. **NÃO** marque "Add a README"
4. Clique **"Create repository"**

## 4. Subir Código para GitHub

No seu computador (ou UserLAnd):

```bash
# Criar pasta
mkdir controle-km-cloud
cd controle-km-cloud

# Copiar os arquivos baixados para cá
cp /caminho/do/download/app_controle_km_cloud.py app.py
cp /caminho/do/download/requirements_cloud.txt requirements.txt

# Inicializar git
git init
git add .
git commit -m "Initial commit"

# Conectar ao GitHub (substitua SEU_USUARIO)
git remote add origin https://github.com/SEU_USUARIO/controle-km-cloud.git
git push -u origin main
```

## 5. Criar Serviço no Render

1. No Render, clique **"New +"** → **"Web Service"**
2. Conecte sua conta **GitHub**
3. Encontre e clique no repositório `controle-km-cloud`
4. Configure:
   - **Name**: `controle-km`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run app.py --server.port 10000 --server.address 0.0.0.0`
5. Clique **"Create Web Service"**

## 6. Aguardar Deploy

- O Render vai instalar dependências e iniciar o app
- Isso leva ~2-5 minutos na primeira vez
- Quando aparecer **"Live"**, clique na URL para acessar

## 7. URL do App

Será algo como:
```
https://controle-km.onrender.com
```

Guarde essa URL! É o endereço do seu app na nuvem.

## ⚠️ IMPORTANTE - Modo Cloud

| O que acontece | Solução |
|---------------|---------|
| App "dorme" após 15min | Primeiro acesso demora ~30s |
| Dados somem ao reiniciar | **Envie por e-mail regularmente** |
| Fotos somem ao reiniciar | **Envie por e-mail regularmente** |

### Fluxo de Trabalho Recomendado:
```
1. Use o app durante o dia (cadastre viagens + fotos)
2. Ao final do dia → Aba "📧 Enviar por E-mail"
3. Envie relatório ZIP para seu e-mail
4. Baixe no PC e salve como evidência
5. Pronto! Dados estão seguros no seu e-mail
```

## 🔐 Configurar E-mail (Gmail)

1. Acesse: https://myaccount.google.com/security
2. Ative **"Verificação em 2 etapas"**
3. Volte em Segurança → **"Senhas de app"**
4. Selecione app: **"Outro"** → Nomeie: `Controle KM`
5. Copie a senha gerada (16 caracteres)
6. Use essa senha no app (não sua senha normal!)

## 💰 Upgrade (Opcional)

Se quiser app sempre ligado (sem sleep):
- Plano **Starter**: $7/mês (~R$35)
- App nunca "dorme"
- Dados ainda são temporários, mas persistem mais

## 🆘 Problemas?

Verifique os logs:
Render Dashboard → seu serviço → **Logs**

Erros comuns:
- `Module not found` → Verifique requirements.txt
- `Port already in use` → Use porta 10000
- `File not found` → Verifique nome do arquivo (app.py)
