"""
email_service.py — Serviço de envio de e-mail para o sistema de controle de KM.

Melhorias em relação ao código original:
- Credenciais via variáveis de ambiente (nunca gravadas em disco)
- Timeout de 30s na conexão SMTP
- Retry automático (até 3 tentativas)
- Log de erros sem expor senha
- Validação de e-mail antes de enviar
- Aviso se anexo > 20 MB
"""

import os
import re
import time
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from io import BytesIO

logger = logging.getLogger(__name__)

# ─── Credenciais via variáveis de ambiente ────────────────────────────────────
_SMTP_EMAIL_ENV    = os.environ.get("SMTP_EMAIL", "").strip()
_SMTP_PASSWORD_ENV = os.environ.get("SMTP_PASSWORD", "").strip()

# Limites
MAX_ANEXO_BYTES_AVISO = 20 * 1024 * 1024   # 20 MB — aviso (não bloqueia)
SMTP_TIMEOUT         = 30                   # segundos
MAX_TENTATIVAS       = 3
ESPERA_RETRY         = 5                    # segundos entre tentativas

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$")


# ─── Utilitários ─────────────────────────────────────────────────────────────

def obter_credenciais_env() -> tuple[str, str]:
    """
    Retorna (email, senha) lidos das variáveis de ambiente.
    Retorna ('', '') se não configurados.
    """
    return _SMTP_EMAIL_ENV, _SMTP_PASSWORD_ENV


def credenciais_env_disponiveis() -> bool:
    """True se SMTP_EMAIL e SMTP_PASSWORD estão definidos no ambiente."""
    return bool(_SMTP_EMAIL_ENV and _SMTP_PASSWORD_ENV)


def _validar_email(email: str) -> bool:
    return bool(_EMAIL_REGEX.match(email.strip()))


def _ocultar_senha(msg: str, senha: str) -> str:
    """Remove a senha de uma mensagem de erro para evitar vazamento em logs."""
    if senha:
        return msg.replace(senha, "****")
    return msg


# ─── Envio de e-mail ──────────────────────────────────────────────────────────

def enviar_email(
    destinatario: str,
    assunto: str,
    corpo: str,
    anexo_buffer: BytesIO | None = None,
    anexo_nome: str = "relatorio.zip",
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
    email_remetente: str | None = None,
    senha_app: str | None = None,
) -> tuple[bool, str]:
    """
    Envia e-mail com anexo ZIP opcional.

    Prioridade de credenciais:
      1. Parâmetros explícitos (email_remetente, senha_app)  — configuração manual via UI
      2. Variáveis de ambiente SMTP_EMAIL / SMTP_PASSWORD    — configuração de servidor

    Retorna (sucesso, mensagem).
    """

    # Resolver credenciais
    remetente = (email_remetente or _SMTP_EMAIL_ENV or "").strip()
    senha     = (senha_app      or _SMTP_PASSWORD_ENV or "").strip()

    # Validações
    if not remetente:
        return False, "E-mail remetente não configurado. Defina SMTP_EMAIL ou configure via UI."
    if not senha:
        return False, "Senha de app não configurada. Defina SMTP_PASSWORD ou configure via UI."
    if not _validar_email(destinatario):
        return False, f"E-mail do destinatário inválido: {destinatario}"
    if not _validar_email(remetente):
        return False, f"E-mail remetente inválido: {remetente}"

    # Aviso de tamanho do anexo
    aviso_tamanho = ""
    if anexo_buffer:
        tamanho = len(anexo_buffer.getvalue())
        if tamanho > MAX_ANEXO_BYTES_AVISO:
            tamanho_mb = tamanho / (1024 * 1024)
            aviso_tamanho = f" ⚠️ Anexo grande ({tamanho_mb:.1f} MB) — pode ser rejeitado pelo servidor."

    # Montar mensagem
    msg = MIMEMultipart()
    msg["From"]    = remetente
    msg["To"]      = destinatario
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    if anexo_buffer:
        anexo_buffer.seek(0)
        part = MIMEBase("application", "zip")
        part.set_payload(anexo_buffer.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={anexo_nome}")
        msg.attach(part)

    # Retry loop
    ultimo_erro = ""
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            logger.info("SMTP: tentativa %d/%d para %s via %s:%d",
                        tentativa, MAX_TENTATIVAS, destinatario, smtp_server, smtp_port)

            server = smtplib.SMTP(smtp_server, smtp_port, timeout=SMTP_TIMEOUT)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(remetente, senha)
            server.send_message(msg)
            server.quit()

            logger.info("SMTP: e-mail enviado com sucesso para %s.", destinatario)
            resultado = "✅ E-mail enviado com sucesso!"
            if aviso_tamanho:
                resultado += aviso_tamanho
            return True, resultado

        except smtplib.SMTPAuthenticationError:
            # Erro de autenticação — não adianta retry
            logger.error("SMTP: falha de autenticação para %s (remetente: %s).", smtp_server, remetente)
            return False, (
                "❌ Falha de autenticação SMTP. Verifique a 'Senha de App' e o e-mail remetente. "
                "Para Gmail, gere uma Senha de App em: Configurações → Segurança → Senhas de app."
            )

        except smtplib.SMTPRecipientsRefused:
            logger.error("SMTP: destinatário recusado: %s.", destinatario)
            return False, f"❌ Destinatário recusado pelo servidor: {destinatario}"

        except smtplib.SMTPException as e:
            ultimo_erro = _ocultar_senha(str(e), senha)
            logger.warning("SMTP: erro na tentativa %d: %s", tentativa, ultimo_erro)

        except TimeoutError:
            ultimo_erro = f"Timeout ao conectar ao servidor SMTP ({smtp_server}:{smtp_port})."
            logger.warning("SMTP: timeout na tentativa %d.", tentativa)

        except OSError as e:
            ultimo_erro = _ocultar_senha(str(e), senha)
            logger.warning("SMTP: erro de rede na tentativa %d: %s", tentativa, ultimo_erro)

        if tentativa < MAX_TENTATIVAS:
            logger.info("SMTP: aguardando %ds antes da próxima tentativa...", ESPERA_RETRY)
            time.sleep(ESPERA_RETRY)

    return False, f"❌ Falha após {MAX_TENTATIVAS} tentativas. Último erro: {ultimo_erro}"
