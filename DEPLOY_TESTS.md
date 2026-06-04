# Resumo: Deploy e Testes Locais

Este documento resume passos rápidos para testar e subir a aplicação.

Passos rápidos (Linux):

1) Criar e ativar venv

```bash
python3 -m venv venv
# fish shell
source venv/bin/activate.fish
# bash/zsh
# source venv/bin/activate
```

2) Instalar dependências

```bash
pip install -r requirements.txt
```

3) Variáveis de ambiente (exemplo)

```bash
export SMTP_EMAIL=you@example.com
export SMTP_PASSWORD=your_app_password
# Opcional D1
export CF_ACCOUNT_ID=your_account_id
export CF_D1_DATABASE_ID=your_database_id
export CF_API_TOKEN=your_api_token
```

4) Testar conexão com D1 (one-shot)

```bash
python3 -c "from storage import testar_conexao_d1; print(testar_conexao_d1())"
```

5) Rodar a app (Streamlit)

```bash
streamlit run app.py --server.port 10000 --server.address 0.0.0.0
```

6) Testar envio de e-mail (após configurar `SMTP_EMAIL`/`SMTP_PASSWORD`)

```bash
python3 -c "from email_service import enviar_email; print(enviar_email('dest@dominio.com','Assunto de teste','Corpo do teste', None))"
```

Observações:
- Use senhas de app (Gmail) em produção. Não comite credenciais.
- Caso o D1 não esteja configurado, a aplicação roda no fallback local (`dados_viagens.json` + `fotos_evidencias/`).
- Verifique logs do Render ao fazer deploy e adicione as mesmas variáveis de ambiente na UI de serviços do Render.
