"""
validations.py — Validações de negócio do sistema de controle de KM.
Centraliza todas as regras de validação para evitar repetição e garantir consistência.
"""

import re
import logging
from datetime import date
from io import BytesIO

logger = logging.getLogger(__name__)

# ─── Constantes de validação ───────────────────────────────────────────────────
MAX_FOTO_BYTES = 5 * 1024 * 1024          # 5 MB por foto
MAX_FOTO_D1_BYTES = 800 * 1024            # 800 KB — limite para armazenamento base64 no D1
MAX_OBS_LEN = 500                          # caracteres na observação
MAX_ONIBUS_LEN = 20                        # caracteres no número do ônibus
EXTENSOES_VALIDAS = {"jpg", "jpeg", "png", "webp"}

# Magic bytes das extensões aceitas (evita upload de arquivo renomeado)
MAGIC_BYTES: dict[str, list[bytes]] = {
    "jpg":  [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png":  [b"\x89PNG"],
    "webp": [b"RIFF"],
}


# ─── Sanitização de texto ──────────────────────────────────────────────────────

def sanitizar_texto(texto: str, max_len: int = MAX_OBS_LEN) -> str:
    """Remove espaços extras e limita o comprimento do texto."""
    if not texto:
        return ""
    return str(texto).strip()[:max_len]


# ─── Número do ônibus ──────────────────────────────────────────────────────────

def validar_numero_onibus(valor: str) -> tuple[bool, str, str]:
    """
    Valida e normaliza o número do ônibus.
    Retorna (ok, mensagem_erro, valor_normalizado).
    """
    if not valor or not valor.strip():
        return False, "O número do ônibus é obrigatório.", ""

    normalizado = valor.strip().upper()

    if len(normalizado) > MAX_ONIBUS_LEN:
        return False, f"Número do ônibus muito longo (máx. {MAX_ONIBUS_LEN} caracteres).", ""

    if not re.match(r"^[A-Z0-9\-_/ ]+$", normalizado):
        return False, "Número do ônibus deve conter apenas letras, números e traços.", ""

    return True, "", normalizado


# ─── KM ───────────────────────────────────────────────────────────────────────

def validar_km(km_inicial: float, km_final: float) -> tuple[bool, str]:
    """
    Valida que km_inicial >= 0, km_final > km_inicial.
    Retorna (ok, mensagem_erro).
    """
    if km_inicial < 0:
        return False, "KM Inicial não pode ser negativo."
    if km_final < 0:
        return False, "KM Final não pode ser negativo."
    if km_final <= km_inicial:
        return False, "KM Final deve ser maior que KM Inicial."
    if (km_final - km_inicial) > 5000:
        return False, "Diferença de KM suspeita (> 5.000 km). Verifique os valores."
    return True, ""


# ─── Passageiros ──────────────────────────────────────────────────────────────

def validar_passageiros(n: int) -> tuple[bool, str]:
    """Passageiros não pode ser negativo."""
    if n < 0:
        return False, "Quantidade de passageiros não pode ser negativa."
    if n > 10_000:
        return False, "Quantidade de passageiros suspeita (> 10.000)."
    return True, ""


# ─── Data ─────────────────────────────────────────────────────────────────────

def validar_data(data: date) -> tuple[bool, str]:
    """A data da viagem não pode ser futura."""
    hoje = date.today()
    if data > hoje:
        return False, "A data da viagem não pode ser no futuro."
    return True, ""


# ─── E-mail ───────────────────────────────────────────────────────────────────

def validar_email(email: str) -> tuple[bool, str]:
    """Valida formato básico de e-mail."""
    if not email or not email.strip():
        return False, "E-mail não pode estar vazio."
    padrao = r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$"
    if not re.match(padrao, email.strip()):
        return False, f"E-mail inválido: {email}"
    return True, ""


# ─── Upload de foto ───────────────────────────────────────────────────────────

def validar_upload_foto(arquivo) -> tuple[bool, str]:
    """
    Valida um arquivo de foto carregado via st.file_uploader:
    - Extensão permitida
    - Tamanho máximo (MAX_FOTO_BYTES)
    - Magic bytes reais (evita arquivo renomeado)
    Retorna (ok, mensagem_erro).
    """
    if arquivo is None:
        return True, ""  # foto é opcional

    nome = arquivo.name.lower()
    ext = nome.rsplit(".", 1)[-1] if "." in nome else ""

    if ext not in EXTENSOES_VALIDAS:
        return False, f"Extensão não permitida: .{ext}. Use JPG, JPEG, PNG ou WEBP."

    conteudo = arquivo.getvalue()

    if len(conteudo) > MAX_FOTO_BYTES:
        tamanho_mb = len(conteudo) / (1024 * 1024)
        return False, f"Foto muito grande: {tamanho_mb:.1f} MB (máx. 5 MB)."

    if len(conteudo) < 4:
        return False, "Arquivo inválido ou vazio."

    # Verificar magic bytes
    magics = MAGIC_BYTES.get(ext, [])
    if magics:
        valido_magic = any(conteudo.startswith(m) for m in magics)
        if not valido_magic:
            return False, "O arquivo não parece ser uma imagem válida (conteúdo inválido)."

    return True, ""


def validar_foto_d1(arquivo) -> tuple[bool, str]:
    """
    Verifica se a foto cabe no limite do D1 (base64 em campo TEXT).
    Retorna (ok, mensagem_aviso). 'ok=False' apenas bloqueia — warning é apenas informativo.
    """
    if arquivo is None:
        return True, ""

    conteudo = arquivo.getvalue()
    if len(conteudo) > MAX_FOTO_D1_BYTES:
        tamanho_kb = len(conteudo) / 1024
        return False, (
            f"Foto muito grande para armazenamento no D1 ({tamanho_kb:.0f} KB). "
            f"Limite: 800 KB. Reduza a resolução ou envie por e-mail imediatamente após salvar."
        )
    return True, ""


# ─── Duplicidade de viagem ────────────────────────────────────────────────────

def verificar_duplicidade(
    dados: list[dict],
    numero_onibus: str,
    data_viagem,
    km_inicial: float,
) -> tuple[bool, str]:
    """
    Verifica se já existe uma viagem com mesmo ônibus + data + km_inicial.
    Retorna (duplicado, mensagem).
    """
    data_str = str(data_viagem)
    for v in dados:
        if (
            str(v.get("numero_onibus", "")).upper() == numero_onibus.upper()
            and str(v.get("data", ""))[:10] == data_str[:10]
            and abs(float(v.get("km_inicial", -1)) - float(km_inicial)) < 0.5
        ):
            return True, (
                f"Já existe uma viagem do ônibus {numero_onibus} "
                f"em {data_str[:10]} com KM inicial {km_inicial:.1f}. "
                "Verifique se não é duplicata."
            )
    return False, ""
