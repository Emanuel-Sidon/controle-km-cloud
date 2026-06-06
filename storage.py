"""
storage.py — Camada de persistência do sistema de controle de KM.

Suporta dois backends:
  1. Cloudflare D1 (via REST API) — persistência real no cloud
  2. JSON local (fallback) — comportamento original

O backend é selecionado automaticamente com base nas variáveis de ambiente:
  CF_ACCOUNT_ID, CF_D1_DATABASE_ID, CF_API_TOKEN

Fotos são armazenadas como base64 em campo TEXT do D1 (limite ~800 KB por foto).
No modo local, fotos continuam salvas em disco (comportamento original).
"""

import os
import json
import base64
import logging
import requests
from io import BytesIO
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── Configuração do D1 ───────────────────────────────────────────────────────
CF_ACCOUNT_ID   = os.environ.get("CF_ACCOUNT_ID", "").strip()
CF_D1_DB_ID     = os.environ.get("CF_D1_DATABASE_ID", "").strip()
CF_API_TOKEN    = os.environ.get("CF_API_TOKEN", "").strip()

D1_DISPONIVEL = bool(CF_ACCOUNT_ID and CF_D1_DB_ID and CF_API_TOKEN)

# ─── Caminhos locais (fallback) ───────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_FILE   = os.path.join(BASE_DIR, "dados_viagens.json")
PHOTOS_DIR  = os.path.join(BASE_DIR, "fotos_evidencias")
os.makedirs(PHOTOS_DIR, exist_ok=True)

# ─── Constantes ───────────────────────────────────────────────────────────────
D1_API_URL = (
    f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}"
    f"/d1/database/{CF_D1_DB_ID}/query"
)
D1_HEADERS = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json",
}
REQUEST_TIMEOUT = 15  # segundos


# ──────────────────────────────────────────────────────────────────────────────
#  Funções D1 (REST API)
# ──────────────────────────────────────────────────────────────────────────────

def _d1_query(sql: str, params: list | None = None) -> list[dict]:
    """
    Executa uma query no Cloudflare D1 via REST API.
    Retorna lista de linhas como dicionários.
    Lança RuntimeError em caso de falha.
    """
    payload = {"sql": sql, "params": params or []}
    try:
        resp = requests.post(D1_API_URL, headers=D1_HEADERS, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            erros = data.get("errors", [])
            raise RuntimeError(f"D1 error: {erros}")
        resultados = data.get("result", [])
        if resultados and isinstance(resultados, list):
            return resultados[0].get("results", [])
        return []
    except requests.Timeout:
        raise RuntimeError("Timeout ao conectar ao Cloudflare D1.")
    except requests.RequestException as e:
        raise RuntimeError(f"Erro de rede ao acessar D1: {e}")


def _d1_execute(sql: str, params: list | None = None) -> None:
    """Executa uma instrução SQL de escrita (INSERT, UPDATE, DELETE, CREATE)."""
    _d1_query(sql, params)


def _d1_inicializar_schema() -> None:
    """Cria a tabela de viagens no D1, caso ainda não exista."""
    _d1_execute("""
        CREATE TABLE IF NOT EXISTS viagens (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            data             TEXT NOT NULL,
            dia_semana       TEXT,
            semana_ano       INTEGER,
            mes              INTEGER,
            mes_nome         TEXT,
            ano              INTEGER,
            turno            TEXT,
            numero_onibus    TEXT,
            km_inicial       REAL,
            km_final         REAL,
            km_percorrido    REAL,
            passageiros      INTEGER,
            observacao       TEXT,
            tem_foto_inicial INTEGER DEFAULT 0,
            tem_foto_final   INTEGER DEFAULT 0,
            foto_inicial_b64 TEXT,
            foto_final_b64   TEXT,
            foto_inicial_ext TEXT,
            foto_final_ext   TEXT,
            data_registro    TEXT
        )
    """)
    logger.info("D1: schema verificado/criado com sucesso.")


def testar_conexao_d1() -> tuple[bool, str]:
    """
    Testa a conectividade com o Cloudflare D1.
    Retorna (ok, mensagem).
    """
    if not D1_DISPONIVEL:
        return False, "Variáveis de ambiente D1 não configuradas."
    try:
        _d1_inicializar_schema()
        _d1_query("SELECT 1 AS ping")
        return True, "D1 conectado com sucesso."
    except Exception as e:
        logger.error("Falha na conexão D1: %s", e)
        return False, str(e)


# ──────────────────────────────────────────────────────────────────────────────
#  Funções de dados — leitura e escrita
# ──────────────────────────────────────────────────────────────────────────────

def _linha_d1_para_dict(row: dict) -> dict:
    """Converte uma linha do D1 para o formato de dicionário usado pela aplicação."""
    return {
        "id":              row["id"],
        "data":            row["data"],
        "dia_semana":      row.get("dia_semana", ""),
        "semana_ano":      row.get("semana_ano", 0),
        "mes":             row.get("mes", 0),
        "mes_nome":        row.get("mes_nome", ""),
        "ano":             row.get("ano", 0),
        "turno":           row.get("turno", ""),
        "numero_onibus":   row.get("numero_onibus", ""),
        "km_inicial":      row.get("km_inicial", 0.0),
        "km_final":        row.get("km_final", 0.0),
        "km_percorrido":   row.get("km_percorrido", 0.0),
        "passageiros":     row.get("passageiros", 0),
        "observacao":      row.get("observacao", ""),
        "tem_foto_inicial": bool(row.get("tem_foto_inicial", 0)),
        "tem_foto_final":   bool(row.get("tem_foto_final", 0)),
        # Caminhos locais não existem no D1; usamos placeholder
        "foto_inicial":    None,
        "foto_final":      None,
        "data_registro":   row.get("data_registro", ""),
    }


def carregar_dados() -> list[dict]:
    """
    Carrega todas as viagens.
    Prioridade: D1 → JSON local.
    """
    if D1_DISPONIVEL:
        try:
            _d1_inicializar_schema()
            linhas = _d1_query(
                "SELECT id, data, dia_semana, semana_ano, mes, mes_nome, ano, turno, "
                "numero_onibus, km_inicial, km_final, km_percorrido, passageiros, "
                "observacao, tem_foto_inicial, tem_foto_final, data_registro "
                "FROM viagens ORDER BY id"
            )
            return [_linha_d1_para_dict(r) for r in linhas]
        except Exception as e:
            logger.warning("Falha ao carregar dados do D1, usando local: %s", e)

    # Fallback local
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Erro ao ler arquivo local: %s", e)
    return []


def salvar_dados_local(dados: list[dict]) -> None:
    """Salva lista completa de viagens no JSON local (modo fallback)."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("Erro ao salvar dados locais: %s", e)
        raise


def inserir_viagem_d1(viagem: dict) -> int:
    """
    Insere uma viagem no D1 e retorna o ID gerado.
    Não inclui campos de foto nesta etapa.
    """
    _d1_execute("""
        INSERT INTO viagens
            (data, dia_semana, semana_ano, mes, mes_nome, ano, turno,
             numero_onibus, km_inicial, km_final, km_percorrido, passageiros,
             observacao, tem_foto_inicial, tem_foto_final,
             foto_inicial_b64, foto_final_b64, foto_inicial_ext, foto_final_ext,
             data_registro)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        viagem["data"], viagem["dia_semana"], viagem["semana_ano"],
        viagem["mes"], viagem["mes_nome"], viagem["ano"], viagem["turno"],
        viagem["numero_onibus"], viagem["km_inicial"], viagem["km_final"],
        viagem["km_percorrido"], viagem["passageiros"], viagem.get("observacao", ""),
        int(viagem.get("tem_foto_inicial", False)),
        int(viagem.get("tem_foto_final", False)),
        viagem.get("foto_inicial_b64", None),
        viagem.get("foto_final_b64", None),
        viagem.get("foto_inicial_ext", None),
        viagem.get("foto_final_ext", None),
        viagem["data_registro"],
    ])

    # Recuperar o ID gerado
    linhas = _d1_query("SELECT last_insert_rowid() AS id")
    if linhas:
        return int(linhas[0]["id"])
    return -1


def excluir_viagem_d1(id_viagem: int) -> None:
    """Remove uma viagem do D1 pelo ID."""
    _d1_execute("DELETE FROM viagens WHERE id = ?", [id_viagem])
    logger.info("D1: viagem #%d excluída.", id_viagem)


def excluir_todos_d1() -> None:
    """Remove todas as viagens do D1."""
    _d1_execute("DELETE FROM viagens")
    logger.info("D1: todos os dados excluídos.")


# ──────────────────────────────────────────────────────────────────────────────
#  Funções de foto
# ──────────────────────────────────────────────────────────────────────────────

def _arquivo_para_b64(arquivo) -> tuple[str, str]:
    """
    Converte UploadedFile do Streamlit para (base64_str, extensão).
    """
    conteudo = arquivo.getvalue()
    b64 = base64.b64encode(conteudo).decode("utf-8")
    ext = arquivo.name.rsplit(".", 1)[-1].lower() if "." in arquivo.name else "jpg"
    return b64, ext


def salvar_foto_local(arquivo, nome_arquivo: str) -> str | None:
    """Salva foto no disco local e retorna o caminho absoluto."""
    if arquivo is None:
        return None
    # Sanitizar nome para evitar path traversal
    nome_seguro = os.path.basename(nome_arquivo)
    caminho = os.path.join(PHOTOS_DIR, nome_seguro)
    try:
        with open(caminho, "wb") as f:
            f.write(arquivo.getvalue())
        return caminho
    except OSError as e:
        logger.error("Erro ao salvar foto local '%s': %s", nome_seguro, e)
        return None


def buscar_foto_d1(id_viagem: int, tipo: str) -> tuple[bytes | None, str | None]:
    """
    Busca foto armazenada em base64 no D1.
    tipo: 'inicial' ou 'final'
    Retorna (bytes_da_imagem, extensão) ou (None, None) se não encontrada.
    """
    coluna_b64 = "foto_inicial_b64" if tipo == "inicial" else "foto_final_b64"
    coluna_ext = "foto_inicial_ext" if tipo == "inicial" else "foto_final_ext"
    try:
        linhas = _d1_query(
            f"SELECT {coluna_b64}, {coluna_ext} FROM viagens WHERE id = ?",
            [id_viagem],
        )
        if linhas and linhas[0].get(coluna_b64):
            b64_str = linhas[0][coluna_b64]
            ext = linhas[0].get(coluna_ext, "jpg")
            img_bytes = base64.b64decode(b64_str)
            return img_bytes, ext
    except Exception as e:
        logger.warning("Erro ao buscar foto #%d/%s do D1: %s", id_viagem, tipo, e)
    return None, None


def verificar_fotos_existentes_local(df_periodo) -> list[dict]:
    """
    Verifica quais fotos realmente existem no disco (modo local).
    Retorna lista de dicts com id, tipo, caminho, onibus, data.
    """
    fotos = []
    for _, row in df_periodo.iterrows():
        if row.get("foto_inicial") and os.path.exists(row["foto_inicial"]):
            fotos.append({
                "id":      row["id"],
                "tipo":    "inicial",
                "caminho": row["foto_inicial"],
                "onibus":  row["numero_onibus"],
                "data":    row["data"],
            })
        if row.get("foto_final") and os.path.exists(row["foto_final"]):
            fotos.append({
                "id":      row["id"],
                "tipo":    "final",
                "caminho": row["foto_final"],
                "onibus":  row["numero_onibus"],
                "data":    row["data"],
            })
    return fotos


def contar_fotos_d1(df_periodo) -> int:
    """Retorna a quantidade de fotos disponíveis no D1 para o período dado."""
    total = 0
    for _, row in df_periodo.iterrows():
        if row.get("tem_foto_inicial"):
            total += 1
        if row.get("tem_foto_final"):
            total += 1
    return total


# ──────────────────────────────────────────────────────────────────────────────
#  Migração: JSON local → D1
# ──────────────────────────────────────────────────────────────────────────────

def migrar_local_para_d1() -> tuple[int, list[str]]:
    """
    Migra dados do JSON local para o D1.
    Retorna (quantidade_migrada, lista_de_erros).
    Não duplica registros que já existem no D1 (por data + ônibus + km_inicial).
    """
    if not D1_DISPONIVEL:
        return 0, ["D1 não configurado."]

    dados_locais = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            dados_locais = json.load(f)

    if not dados_locais:
        return 0, []

    existentes = _d1_query(
        "SELECT data, numero_onibus, km_inicial FROM viagens"
    )
    chaves_existentes = {
        (r["data"][:10], r["numero_onibus"].upper(), float(r["km_inicial"]))
        for r in existentes
    }

    migradas = 0
    erros = []
    for viagem in dados_locais:
        chave = (
            str(viagem.get("data", ""))[:10],
            str(viagem.get("numero_onibus", "")).upper(),
            float(viagem.get("km_inicial", 0)),
        )
        if chave in chaves_existentes:
            continue  # já existe
        try:
            viagem.setdefault("data_registro", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            inserir_viagem_d1(viagem)
            chaves_existentes.add(chave)
            migradas += 1
        except Exception as e:
            erros.append(f"Viagem #{viagem.get('id', '?')}: {e}")

    logger.info("Migração concluída: %d viagens migradas, %d erros.", migradas, len(erros))
    return migradas, erros
