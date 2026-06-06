"""
utils.py — Constantes e funções auxiliares do sistema de controle de KM.

Contém:
- Constantes globais (turnos, meses, dias da semana)
- Detecção de ambiente (local vs cloud)
- Logging estruturado
- Funções de análise temporal
- Geração de relatório ZIP (adaptado para D1 e modo local)
"""

import os
import logging
import zipfile
import pandas as pd
from datetime import date, timedelta
from io import BytesIO

logger = logging.getLogger(__name__)

# ─── Constantes ───────────────────────────────────────────────────────────────
TURNOS    = ["ADM", "A", "B", "C"]
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


# ─── Detecção de ambiente ─────────────────────────────────────────────────────

def detectar_ambiente() -> str:
    """
    Retorna 'cloud' se o app estiver rodando no Render (ou similar),
    'local' caso contrário.
    Detecta via variável RENDER ou IS_CLOUD_ENV.
    """
    if os.environ.get("RENDER") or os.environ.get("IS_CLOUD_ENV"):
        return "cloud"
    return "local"


def esta_no_cloud() -> bool:
    return detectar_ambiente() == "cloud"


# ─── Logging ──────────────────────────────────────────────────────────────────

def log_acao(acao: str, detalhes: str = "") -> None:
    """Registra uma ação do usuário no log do console (sem dados sensíveis)."""
    logger.info("[ACAO] %s%s", acao, f" | {detalhes}" if detalhes else "")


def configurar_logging() -> None:
    """Configura o logging global da aplicação."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ─── Análise temporal ─────────────────────────────────────────────────────────

def get_semana_atual() -> int:
    return date.today().isocalendar()[1]


def get_mes_atual() -> int:
    return date.today().month


def get_ano_atual() -> int:
    return date.today().year


def comparacao_semanal(df: pd.DataFrame) -> dict:
    """Compara KM/viagens/passageiros da semana atual vs. semana anterior."""
    semana_atual, ano_atual = get_semana_atual(), get_ano_atual()
    df_atual = df[(df["semana_ano"] == semana_atual) & (df["ano"] == ano_atual)]
    semana_ant = semana_atual - 1 if semana_atual > 1 else 52
    ano_ant    = ano_atual if semana_atual > 1 else ano_atual - 1
    df_anterior = df[(df["semana_ano"] == semana_ant) & (df["ano"] == ano_ant)]
    return {
        "atual_km":           df_atual["km_percorrido"].sum() if not df_atual.empty else 0,
        "anterior_km":        df_anterior["km_percorrido"].sum() if not df_anterior.empty else 0,
        "atual_viagens":      len(df_atual),
        "anterior_viagens":   len(df_anterior),
        "atual_passageiros":  df_atual["passageiros"].sum() if not df_atual.empty else 0,
        "anterior_passageiros": df_anterior["passageiros"].sum() if not df_anterior.empty else 0,
    }


def comparacao_mensal(df: pd.DataFrame) -> dict:
    """Compara KM/viagens/passageiros do mês atual vs. mês anterior."""
    mes_atual, ano_atual = get_mes_atual(), get_ano_atual()
    df_atual = df[(df["mes"] == mes_atual) & (df["ano"] == ano_atual)]
    mes_ant = mes_atual - 1 if mes_atual > 1 else 12
    ano_ant = ano_atual if mes_atual > 1 else ano_atual - 1
    df_anterior = df[(df["mes"] == mes_ant) & (df["ano"] == ano_ant)]
    return {
        "atual_km":            df_atual["km_percorrido"].sum() if not df_atual.empty else 0,
        "anterior_km":         df_anterior["km_percorrido"].sum() if not df_anterior.empty else 0,
        "atual_viagens":       len(df_atual),
        "anterior_viagens":    len(df_anterior),
        "atual_passageiros":   df_atual["passageiros"].sum() if not df_atual.empty else 0,
        "anterior_passageiros": df_anterior["passageiros"].sum() if not df_anterior.empty else 0,
    }


def tendencia_ultimos_dias(df: pd.DataFrame, dias: int = 7) -> pd.DataFrame:
    """Retorna DataFrame com KM/passageiros/viagens por dia dos últimos N dias."""
    hoje = pd.Timestamp.now()
    data_limite = hoje - timedelta(days=dias)
    df_periodo = df[df["data"] >= data_limite]
    if df_periodo.empty:
        return pd.DataFrame()
    return (
        df_periodo
        .groupby(df_periodo["data"].dt.date)
        .agg({"km_percorrido": "sum", "passageiros": "sum", "id": "count"})
        .rename(columns={"id": "viagens"})
    )


# ─── Geração de DataFrame a partir dos dados ──────────────────────────────────

def dados_para_df(dados: list[dict]) -> pd.DataFrame:
    """Converte lista de viagens para DataFrame pandas com tipos corretos."""
    colunas = [
        "id", "data", "dia_semana", "semana_ano", "mes", "mes_nome", "ano",
        "turno", "numero_onibus", "km_inicial", "km_final", "km_percorrido",
        "passageiros", "observacao", "tem_foto_inicial", "tem_foto_final",
    ]
    if not dados:
        return pd.DataFrame(columns=colunas)
    df = pd.DataFrame(dados)
    df["data"] = pd.to_datetime(df["data"])
    return df


# ─── Geração de relatório ZIP ─────────────────────────────────────────────────

def criar_relatorio_zip(
    df: pd.DataFrame,
    data_inicio=None,
    data_fim=None,
    incluir_fotos: bool = True,
    fotos_d1_fn=None,        # callable(id, tipo) -> (bytes|None, ext|None)  [modo D1]
    fotos_locais: list | None = None,  # lista de dicts [modo local]
) -> tuple[BytesIO | None, str | None]:
    """
    Cria um ZIP com relatório Excel (5 abas) + fotos de evidência.

    Parâmetros:
      df            : DataFrame completo (já filtrado por período, se desejado)
      data_inicio   : date — para filtrar df internamente (opcional)
      data_fim      : date — para filtrar df internamente (opcional)
      incluir_fotos : bool
      fotos_d1_fn   : função (id, tipo) → (bytes, ext) para modo D1
      fotos_locais  : lista de dicts para modo local

    Retorna (BytesIO com ZIP, None) ou (None, mensagem_erro).
    """
    if data_inicio and data_fim:
        df = df[(df["data"].dt.date >= data_inicio) & (df["data"].dt.date <= data_fim)]

    if df.empty:
        return None, "Nenhum dado para exportar no período selecionado."

    buffer = BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # ── Aba 1: Viagens completas ──────────────────────────────────────────
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Viagens", index=False)

            # Aba 2: Resumo por Dia e Turno
            resumo_dia_turno = df.groupby([df["data"].dt.date, "turno"]).agg({
                "km_percorrido": "sum",
                "passageiros":   "sum",
                "numero_onibus": "nunique",
                "id":            "count",
            }).rename(columns={"numero_onibus": "onibus_unicos", "id": "viagens"})
            resumo_dia_turno.columns = ["KM Total", "Passageiros", "Ônibus Únicos", "Viagens"]
            resumo_dia_turno.to_excel(writer, sheet_name="Resumo Dia-Turno")

            # Aba 3: Resumo por Ônibus
            resumo_onibus = df.groupby("numero_onibus").agg({
                "km_percorrido": ["sum", "mean", "count"],
                "passageiros":   "sum",
                "data":          ["min", "max"],
            })
            resumo_onibus.columns = ["KM Total", "KM Médio", "Viagens", "Passageiros", "Primeira Viagem", "Última Viagem"]
            resumo_onibus.sort_values("KM Total", ascending=False).to_excel(writer, sheet_name="Resumo Ônibus")

            # Aba 4: Resumo Mensal
            resumo_mensal = df.groupby(["mes", "mes_nome"]).agg({
                "km_percorrido": ["sum", "mean"],
                "passageiros":   ["sum", "mean"],
                "numero_onibus": "nunique",
                "id":            "count",
            })
            resumo_mensal.columns = ["KM Total", "KM Médio/Viagem", "Passageiros",
                                     "Pass Médio/Viagem", "Ônibus Únicos", "Total Viagens"]
            resumo_mensal.reset_index().set_index("mes_nome").to_excel(writer, sheet_name="Resumo Mensal")

            # Aba 5: Resumo por Dia da Semana
            resumo_dia_sem = df.groupby("dia_semana").agg({
                "km_percorrido": ["sum", "mean"],
                "passageiros":   ["sum", "mean"],
                "id":            "count",
            })
            resumo_dia_sem.columns = ["KM Total", "KM Médio", "Pass Total", "Pass Médio", "Viagens"]
            resumo_dia_sem.to_excel(writer, sheet_name="Resumo Dia Semana")

        zf.writestr("relatorio_km.xlsx", excel_buffer.getvalue())

        # ── Fotos de evidência ────────────────────────────────────────────────
        if incluir_fotos:
            indice_fotos = []
            fotos_adicionadas = 0

            # Modo D1: buscar fotos via função callback
            if fotos_d1_fn is not None:
                for _, row in df.iterrows():
                    for tipo in ("inicial", "final"):
                        col = f"tem_foto_{tipo}"
                        if row.get(col):
                            try:
                                img_bytes, ext = fotos_d1_fn(row["id"], tipo)
                                if img_bytes:
                                    data_str = (
                                        row["data"].strftime("%Y%m%d")
                                        if hasattr(row["data"], "strftime")
                                        else str(row["data"])[:10]
                                    )
                                    nome_arquivo = (
                                        f"viagem_{row['id']}_{tipo}_"
                                        f"{row['numero_onibus']}_{data_str}.{ext}"
                                    )
                                    zf.writestr(f"fotos_evidencias/{nome_arquivo}", img_bytes)
                                    indice_fotos.append({
                                        "Viagem ID": row["id"],
                                        "Data":      row["data"].strftime("%d/%m/%Y") if hasattr(row["data"], "strftime") else str(row["data"]),
                                        "Ônibus":    row["numero_onibus"],
                                        "Tipo":      "KM Inicial" if tipo == "inicial" else "KM Final",
                                        "Arquivo":   nome_arquivo,
                                    })
                                    fotos_adicionadas += 1
                            except Exception as e:
                                logger.warning("Erro ao incluir foto no ZIP (viagem #%d/%s): %s", row["id"], tipo, e)

            # Modo local: incluir fotos do disco
            elif fotos_locais:
                for foto in fotos_locais:
                    try:
                        data_str = (
                            foto["data"].strftime("%Y%m%d")
                            if hasattr(foto["data"], "strftime")
                            else str(foto["data"])[:10]
                        )
                        nome_arquivo = (
                            f"viagem_{foto['id']}_{foto['tipo']}_"
                            f"{foto['onibus']}_{data_str}"
                            f"_{os.path.basename(foto['caminho'])}"
                        )
                        zf.write(foto["caminho"], f"fotos_evidencias/{nome_arquivo}")
                        indice_fotos.append({
                            "Viagem ID": foto["id"],
                            "Data":      foto["data"].strftime("%d/%m/%Y") if hasattr(foto["data"], "strftime") else str(foto["data"]),
                            "Ônibus":    foto["onibus"],
                            "Tipo":      "KM Inicial" if foto["tipo"] == "inicial" else "KM Final",
                            "Arquivo":   nome_arquivo,
                        })
                        fotos_adicionadas += 1
                    except Exception as e:
                        logger.warning("Erro ao incluir foto local no ZIP: %s", e)

            if indice_fotos:
                df_indice = pd.DataFrame(indice_fotos)
                zf.writestr("fotos_evidencias/INDICE_FOTOS.csv", df_indice.to_csv(index=False))
                logger.info("ZIP: %d fotos incluídas.", fotos_adicionadas)
            else:
                zf.writestr(
                    "fotos_evidencias/README.txt",
                    "Nenhuma foto de evidência encontrada para o período selecionado.\n\n"
                    "Possíveis motivos:\n"
                    "1. As viagens não tinham fotos anexadas\n"
                    "2. As fotos foram perdidas devido a reinicialização do servidor (modo cloud sem D1)\n"
                    "3. O período selecionado não possui registros com fotos\n\n"
                    "DICA: Configure o Cloudflare D1 para armazenamento persistente de fotos!\n"
                    "      Ou envie o relatório imediatamente após cadastrar as fotos.",
                )

    buffer.seek(0)
    return buffer, None
