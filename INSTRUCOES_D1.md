# Instruções: Configurar Cloudflare D1 e variáveis de ambiente

Este documento descreve os passos mínimos para ativar persistência no Cloudflare D1 e preparar o deploy no Render.

1) Criar um banco D1
- Acesse Cloudflare → Workers & D1 → Databases → Create Database.
- Anote o `Account ID` e o `Database ID`.

2) Criar um API Token
- Em Cloudflare → My Profile → API Tokens → Create Token
- Permissões: configure pelo menos permissões para `D1` (escrita/leitura) ou use `Edit Cloudflare Workers` role conforme sua política.
- Copie o token (guarde em local seguro).

3) Variáveis de ambiente (Render)
- No painel do Render, abra seu service e vá em Environment → Environment Variables
- Adicione as variáveis abaixo (valores copiados do Cloudflare):
  - `CF_ACCOUNT_ID` = <seu Account ID>
  - `CF_D1_DATABASE_ID` = <seu D1 Database ID>
  - `CF_API_TOKEN` = <seu API Token>
- Adicione também credenciais SMTP:
  - `SMTP_EMAIL` = seu.email@provedor.com
  - `SMTP_PASSWORD` = SUA_SENHA_DE_APP_AQUI

4) Testar conexão D1 (local ou Render)
- A aplicação tentará inicializar o schema D1 automaticamente ao primeira leitura.
- Você pode checar logs do Render para mensagens de sucesso/erro de conexão.

5) Migração de dados locais (opcional)
- Se você possui `dados_viagens.json` local, a função `storage.migrar_local_para_d1()` pode migrar registros não duplicados para o D1.
- Use com cautela e revise logs retornados pela função para confirmar migração.

6) Observações e limites
- Fotos armazenadas como base64 no D1 têm limites práticos (recomendado ≤ 800 KB). Fotos grandes são armazenadas localmente no fallback.
- A aplicação oferece fallback local (JSON + pasta `fotos_evidencias`) quando o D1 não estiver configurado.

7) Segurança
- Não coloque tokens/credenciais em repositórios públicos.
- Use o painel de variáveis do Render para armazenar segredos.

Se desejar, posso adicionar um script de migração/CLI para executar `migrar_local_para_d1()` com segurança e log detalhado.
