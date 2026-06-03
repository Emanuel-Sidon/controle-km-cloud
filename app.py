import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import json
import os
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import zipfile
import shutil

st.set_page_config(page_title="Controle de KM - Ônibus", page_icon="🚌", layout="wide")

st.markdown("""
<style>
.main-header {font-size: 2.5rem; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 2rem;}
.metric-card {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 1rem; color: white; text-align: center;}
.warning-box {background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 1rem; border-radius: 0.5rem; margin: 1rem 0; color: #000000;}
.success-box {background-color: #d4edda; border-left: 4px solid #28a745; padding: 1rem; border-radius: 0.5rem; margin: 1rem 0;}
.email-box {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 1rem; color: white; margin: 1rem 0;}
</style>
""", unsafe_allow_html=True)

# ==================== CONFIGURAÇÃO DE PASTAS ====================
# Detectar ambiente (local vs cloud)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "dados_viagens.json")
PHOTOS_DIR = os.path.join(BASE_DIR, "fotos_evidencias")
EMAIL_CONFIG_FILE = os.path.join(BASE_DIR, "email_config.json")

os.makedirs(PHOTOS_DIR, exist_ok=True)

TURNOS = ["ADM", "A", "B", "C"]
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

st.sidebar.markdown(f"<div style='font-size: 0.7rem; color: gray;'>📁 Dados: {BASE_DIR}</div>", unsafe_allow_html=True)

# ==================== FUNÇÕES DE PERSISTÊNCIA ====================

def carregar_dados():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def salvar_dados(dados):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_config_email():
    if os.path.exists(EMAIL_CONFIG_FILE):
        with open(EMAIL_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def salvar_config_email(config):
    with open(EMAIL_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def salvar_foto(uploaded_file, nome_arquivo):
    """Salva foto e retorna caminho relativo para portabilidade"""
    if uploaded_file is not None:
        caminho = os.path.join(PHOTOS_DIR, nome_arquivo)
        with open(caminho, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return caminho
    return None

def adicionar_viagem(data_viagem, turno, numero_onibus, km_inicial, km_final, passageiros, 
                     observacao="", foto_inicial=None, foto_final=None):
    dados = carregar_dados()
    dt = pd.to_datetime(data_viagem)
    dia_semana = DIAS_SEMANA[dt.weekday()]
    mes_nome = MESES[dt.month - 1]
    novo_id = len(dados) + 1

    foto_inicial_path = None
    foto_final_path = None

    if foto_inicial is not None:
        ext = foto_inicial.name.split('.')[-1]
        foto_inicial_path = salvar_foto(foto_inicial, f"viagem_{novo_id}_inicial.{ext}")

    if foto_final is not None:
        ext = foto_final.name.split('.')[-1]
        foto_final_path = salvar_foto(foto_final, f"viagem_{novo_id}_final.{ext}")

    viagem = {
        "id": novo_id,
        "data": str(data_viagem),
        "dia_semana": dia_semana,
        "semana_ano": dt.isocalendar()[1],
        "mes": dt.month,
        "mes_nome": mes_nome,
        "ano": dt.year,
        "turno": turno,
        "numero_onibus": numero_onibus,
        "km_inicial": float(km_inicial),
        "km_final": float(km_final),
        "km_percorrido": round(float(km_final) - float(km_inicial), 2),
        "passageiros": int(passageiros),
        "observacao": observacao,
        "tem_foto_inicial": foto_inicial_path is not None,
        "tem_foto_final": foto_final_path is not None,
        "foto_inicial": foto_inicial_path,
        "foto_final": foto_final_path,
        "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    dados.append(viagem)
    salvar_dados(dados)
    return viagem

def excluir_viagem(id_viagem):
    dados = carregar_dados()
    viagem = next((v for v in dados if v["id"] == id_viagem), None)
    if viagem:
        if viagem.get("foto_inicial") and os.path.exists(viagem["foto_inicial"]):
            os.remove(viagem["foto_inicial"])
        if viagem.get("foto_final") and os.path.exists(viagem["foto_final"]):
            os.remove(viagem["foto_final"])
    dados = [v for v in dados if v["id"] != id_viagem]
    for i, v in enumerate(dados, 1):
        v["id"] = i
    salvar_dados(dados)

def df_viagens():
    dados = carregar_dados()
    if not dados:
        return pd.DataFrame(columns=["id", "data", "dia_semana", "semana_ano", "mes", "mes_nome", "ano", "turno", "numero_onibus", "km_inicial", "km_final", "km_percorrido", "passageiros", "observacao", "tem_foto_inicial", "tem_foto_final"])
    df = pd.DataFrame(dados)
    df["data"] = pd.to_datetime(df["data"])
    return df

# ==================== FUNÇÕES DE E-MAIL E ZIP ====================

def verificar_fotos_existentes(df_periodo):
    """Verifica quais fotos realmente existem no disco"""
    fotos_existentes = []
    for _, row in df_periodo.iterrows():
        if row.get("foto_inicial") and os.path.exists(row["foto_inicial"]):
            fotos_existentes.append({
                "id": row["id"],
                "tipo": "inicial",
                "caminho": row["foto_inicial"],
                "onibus": row["numero_onibus"],
                "data": row["data"]
            })
        if row.get("foto_final") and os.path.exists(row["foto_final"]):
            fotos_existentes.append({
                "id": row["id"],
                "tipo": "final",
                "caminho": row["foto_final"],
                "onibus": row["numero_onibus"],
                "data": row["data"]
            })
    return fotos_existentes

def criar_relatorio_zip(data_inicio=None, data_fim=None, incluir_fotos=True):
    """Cria um ZIP com relatório Excel + fotos de evidência"""
    df = df_viagens()

    if data_inicio and data_fim:
        df = df[(df["data"].dt.date >= data_inicio) & (df["data"].dt.date <= data_fim)]

    if df.empty:
        return None, "Nenhum dado para exportar."

    buffer = BytesIO()

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. Relatório Excel com múltiplas abas
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            # Aba 1: Viagens completas
            df.to_excel(writer, sheet_name='Viagens', index=False)

            # Aba 2: Resumo por Dia e Turno
            resumo_dia_turno = df.groupby([df["data"].dt.date, "turno"]).agg({
                "km_percorrido": "sum",
                "passageiros": "sum",
                "numero_onibus": "nunique",
                "id": "count"
            }).rename(columns={"numero_onibus": "onibus_unicos", "id": "viagens"})
            resumo_dia_turno.columns = ["KM Total", "Passageiros", "Ônibus Únicos", "Viagens"]
            resumo_dia_turno.to_excel(writer, sheet_name='Resumo Dia-Turno')

            # Aba 3: Resumo por Ônibus
            resumo_onibus = df.groupby("numero_onibus").agg({
                "km_percorrido": ["sum", "mean", "count"],
                "passageiros": "sum",
                "data": ["min", "max"]
            })
            resumo_onibus.columns = ["KM Total", "KM Médio", "Viagens", "Passageiros", "Primeira Viagem", "Última Viagem"]
            resumo_onibus.sort_values("KM Total", ascending=False).to_excel(writer, sheet_name='Resumo Ônibus')

            # Aba 4: Resumo Mensal
            resumo_mensal = df.groupby(["mes", "mes_nome"]).agg({
                "km_percorrido": ["sum", "mean"],
                "passageiros": ["sum", "mean"],
                "numero_onibus": "nunique",
                "id": "count"
            })
            resumo_mensal.columns = ["KM Total", "KM Médio/Viagem", "Passageiros", "Pass Médio/Viagem", "Ônibus Únicos", "Total Viagens"]
            resumo_mensal.reset_index().set_index("mes_nome").to_excel(writer, sheet_name='Resumo Mensal')

            # Aba 5: Resumo por Dia da Semana
            resumo_dia_sem = df.groupby("dia_semana").agg({
                "km_percorrido": ["sum", "mean"],
                "passageiros": ["sum", "mean"],
                "id": "count"
            })
            resumo_dia_sem.columns = ["KM Total", "KM Médio", "Pass Total", "Pass Médio", "Viagens"]
            resumo_dia_sem.to_excel(writer, sheet_name='Resumo Dia Semana')

        zf.writestr("relatorio_km.xlsx", excel_buffer.getvalue())

        # 2. Fotos de evidência (SEMPRE verificar se existem)
        if incluir_fotos:
            fotos_encontradas = verificar_fotos_existentes(df)

            if fotos_encontradas:
                # Criar índice de fotos
                indice_fotos = []
                for foto in fotos_encontradas:
                    nome_arquivo = f"viagem_{foto['id']}_{foto['tipo']}_{os.path.basename(foto['caminho'])}"
                    zf.write(foto['caminho'], f"fotos_evidencias/{nome_arquivo}")
                    indice_fotos.append({
                        "Viagem ID": foto['id'],
                        "Data": foto['data'].strftime('%d/%m/%Y') if hasattr(foto['data'], 'strftime') else str(foto['data']),
                        "Ônibus": foto['onibus'],
                        "Tipo": "KM Inicial" if foto['tipo'] == "inicial" else "KM Final",
                        "Arquivo": nome_arquivo
                    })

                # Adicionar índice de fotos como CSV dentro do ZIP
                if indice_fotos:
                    df_indice = pd.DataFrame(indice_fotos)
                    zf.writestr("fotos_evidencias/INDICE_FOTOS.csv", df_indice.to_csv(index=False))
            else:
                zf.writestr("fotos_evidencias/README.txt", 
                    "Nenhuma foto de evidência foi encontrada para o período selecionado.\n\n"
                    "Possíveis motivos:\n"
                    "1. As viagens não tinham fotos anexadas\n"
                    "2. As fotos foram perdidas devido a reinicialização do servidor (modo cloud)\n"
                    "3. O período selecionado não possui registros com fotos\n\n"
                    "DICA: No modo cloud, envie o relatório imediatamente após cadastrar as fotos!"
                )

    buffer.seek(0)
    return buffer, None

def enviar_email(destinatario, assunto, corpo, anexo_buffer=None, anexo_nome="relatorio.zip",
                 smtp_server="smtp.gmail.com", smtp_port=587, email_remetente=None, senha_app=None):
    """Envia e-mail com anexo ZIP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = email_remetente
        msg['To'] = destinatario
        msg['Subject'] = assunto

        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))

        if anexo_buffer:
            part = MIMEBase('application', 'zip')
            part.set_payload(anexo_buffer.getvalue())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename= {anexo_nome}')
            msg.attach(part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_remetente, senha_app)
        server.send_message(msg)
        server.quit()

        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        return False, f"Erro ao enviar e-mail: {str(e)}"

# ==================== FUNÇÕES DE ANÁLISE TEMPORAL ====================

def get_semana_atual(): return date.today().isocalendar()[1]
def get_mes_atual(): return date.today().month
def get_ano_atual(): return date.today().year

def comparacao_semanal(df):
    semana_atual, ano_atual = get_semana_atual(), get_ano_atual()
    df_atual = df[(df["semana_ano"] == semana_atual) & (df["ano"] == ano_atual)]
    semana_ant, ano_ant = (semana_atual - 1 if semana_atual > 1 else 52), (ano_atual if semana_atual > 1 else ano_atual - 1)
    df_anterior = df[(df["semana_ano"] == semana_ant) & (df["ano"] == ano_ant)]
    return {"atual_km": df_atual["km_percorrido"].sum() if not df_atual.empty else 0, "anterior_km": df_anterior["km_percorrido"].sum() if not df_anterior.empty else 0, "atual_viagens": len(df_atual), "anterior_viagens": len(df_anterior), "atual_passageiros": df_atual["passageiros"].sum() if not df_atual.empty else 0, "anterior_passageiros": df_anterior["passageiros"].sum() if not df_anterior.empty else 0}

def comparacao_mensal(df):
    mes_atual, ano_atual = get_mes_atual(), get_ano_atual()
    df_atual = df[(df["mes"] == mes_atual) & (df["ano"] == ano_atual)]
    mes_ant, ano_ant = (mes_atual - 1 if mes_atual > 1 else 12), (ano_atual if mes_atual > 1 else ano_atual - 1)
    df_anterior = df[(df["mes"] == mes_ant) & (df["ano"] == ano_ant)]
    return {"atual_km": df_atual["km_percorrido"].sum() if not df_atual.empty else 0, "anterior_km": df_anterior["km_percorrido"].sum() if not df_anterior.empty else 0, "atual_viagens": len(df_atual), "anterior_viagens": len(df_anterior), "atual_passageiros": df_atual["passageiros"].sum() if not df_atual.empty else 0, "anterior_passageiros": df_anterior["passageiros"].sum() if not df_anterior.empty else 0}

def tendencia_ultimos_dias(df, dias=7):
    hoje = pd.Timestamp.now()
    data_limite = hoje - timedelta(days=dias)
    df_periodo = df[df["data"] >= data_limite]
    if df_periodo.empty: return pd.DataFrame()
    return df_periodo.groupby(df_periodo["data"].dt.date).agg({"km_percorrido": "sum", "passageiros": "sum", "id": "count"}).rename(columns={"id": "viagens"})

# ==================== SIDEBAR ====================
st.sidebar.markdown("## 🚌 Menu Principal")
pagina = st.sidebar.radio("", ["🏠 Dashboard", "➕ Nova Viagem", "📊 Relatórios", "📈 Análise Temporal", "📧 Enviar por E-mail", "🗂️ Dados Completos"])
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚠️ Modo Cloud (Render)")
st.sidebar.markdown("<div style='font-size: 0.75rem; color: orange;'>Dados são temporários. Envie por e-mail para preservar!</div>", unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.markdown("### 📈 Resumo Rápido")
dados = carregar_dados()
if dados:
    df = df_viagens()
    st.sidebar.metric("Total de Viagens", len(dados))
    st.sidebar.metric("KM Total", f"{df['km_percorrido'].sum():,.2f}")
    st.sidebar.metric("Passageiros", f"{df['passageiros'].sum():,}")
    st.sidebar.metric("📸 Fotos", int(df["tem_foto_inicial"].sum() + df["tem_foto_final"].sum()))
else:
    st.sidebar.info("Nenhuma viagem registrada ainda.")

# ==================== DASHBOARD ====================
if pagina == "🏠 Dashboard":
    st.markdown('<div class="main-header">🚌 Controle de KM Rodado</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="warning-box">
    <strong>⚠️ Modo Cloud Ativo</strong><br>
    Este app está rodando na nuvem (Render). Os dados são <strong>temporários</strong> e serão perdidos quando o app reiniciar.<br>
    <strong>Recomendação:</strong> Envie o relatório por e-mail <strong>imediatamente</strong> após cadastrar as fotos!
    </div>
    """, unsafe_allow_html=True)

    dados = carregar_dados()
    if not dados:
        st.info("👈 Comece registrando uma nova viagem no menu lateral!")
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.markdown('<div class="metric-card"><div style="font-size: 2rem; font-weight: bold;">0</div><div>Viagens Hoje</div></div>', unsafe_allow_html=True)
        with col2: st.markdown('<div class="metric-card" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);"><div style="font-size: 2rem; font-weight: bold;">0 km</div><div>KM Hoje</div></div>', unsafe_allow_html=True)
        with col3: st.markdown('<div class="metric-card" style="background: linear-gradient(135deg, #f83600 0%, #f9d423 100%);"><div style="font-size: 2rem; font-weight: bold;">0</div><div>Passageiros Hoje</div></div>', unsafe_allow_html=True)
        with col4: st.markdown('<div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);"><div style="font-size: 2rem; font-weight: bold;">0</div><div>Ônibus Ativos</div></div>', unsafe_allow_html=True)
    else:
        df = df_viagens()
        hoje = pd.Timestamp.now().date()
        df_hoje = df[df["data"].dt.date == hoje]

        col1, col2, col3, col4 = st.columns(4)
        with col1: st.markdown(f'<div class="metric-card"><div style="font-size: 2rem; font-weight: bold;">{len(df_hoje)}</div><div>Viagens Hoje</div></div>', unsafe_allow_html=True)
        with col2: st.markdown(f'<div class="metric-card" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);"><div style="font-size: 2rem; font-weight: bold;">{df_hoje["km_percorrido"].sum():,.1f} km</div><div>KM Hoje</div></div>', unsafe_allow_html=True)
        with col3: st.markdown(f'<div class="metric-card" style="background: linear-gradient(135deg, #f83600 0%, #f9d423 100%);"><div style="font-size: 2rem; font-weight: bold;">{df_hoje["passageiros"].sum():,}</div><div>Passageiros Hoje</div></div>', unsafe_allow_html=True)
        with col4: st.markdown(f'<div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);"><div style="font-size: 2rem; font-weight: bold;">{df_hoje["numero_onibus"].nunique()}</div><div>Ônibus Ativos</div></div>', unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("📊 Comparativos Rápidos")
        comp_sem, comp_mes = comparacao_semanal(df), comparacao_mensal(df)
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("#### 📅 Semana Atual vs Anterior")
            var_km_sem = ((comp_sem["atual_km"] - comp_sem["anterior_km"]) / comp_sem["anterior_km"] * 100) if comp_sem["anterior_km"] > 0 else 0
            st.metric("KM Semana Atual", f"{comp_sem['atual_km']:,.1f} km", f"{var_km_sem:+.1f}%" if comp_sem["anterior_km"] > 0 else "Sem dados anterior")
            st.metric("Viagens", comp_sem["atual_viagens"], f"{comp_sem['atual_viagens'] - comp_sem['anterior_viagens']:+d}" if comp_sem["anterior_viagens"] > 0 else "Sem dados anterior")
        with col_c2:
            st.markdown("#### 📆 Mês Atual vs Anterior")
            var_km_mes = ((comp_mes["atual_km"] - comp_mes["anterior_km"]) / comp_mes["anterior_km"] * 100) if comp_mes["anterior_km"] > 0 else 0
            st.metric("KM Mês Atual", f"{comp_mes['atual_km']:,.1f} km", f"{var_km_mes:+.1f}%" if comp_mes["anterior_km"] > 0 else "Sem dados anterior")
            st.metric("Viagens", comp_mes["atual_viagens"], f"{comp_mes['atual_viagens'] - comp_mes['anterior_viagens']:+d}" if comp_mes["anterior_viagens"] > 0 else "Sem dados anterior")

        st.markdown("---")
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("📊 KM por Turno (Total)")
            st.bar_chart(df.groupby("turno")["km_percorrido"].sum().reindex(TURNOS, fill_value=0))
        with col_right:
            st.subheader("👥 Passageiros por Turno (Total)")
            st.bar_chart(df.groupby("turno")["passageiros"].sum().reindex(TURNOS, fill_value=0))

        st.markdown("---")
        st.subheader("📈 Tendência Últimos 7 Dias")
        tendencia = tendencia_ultimos_dias(df, 7)
        if not tendencia.empty: st.line_chart(tendencia[["km_percorrido", "passageiros"]])
        else: st.info("Dados insuficientes para tendência de 7 dias.")

        st.subheader("🚌 Top 5 Ônibus - Maior KM Percorrido")
        km_por_onibus = df.groupby("numero_onibus").agg({"km_percorrido": "sum", "passageiros": "sum", "id": "count"}).rename(columns={"id": "viagens"}).sort_values("km_percorrido", ascending=False).head(5)
        km_por_onibus.columns = ["KM Total", "Passageiros", "Viagens"]
        st.dataframe(km_por_onibus, use_container_width=True)

        st.subheader("📝 Últimas 10 Viagens Registradas")
        df_display = df.sort_values("id", ascending=False).head(10)[["data", "dia_semana", "turno", "numero_onibus", "km_percorrido", "passageiros", "tem_foto_inicial", "tem_foto_final"]]
        df_display.columns = ["Data", "Dia", "Turno", "Ônibus", "KM", "Passageiros", "📸 Inicial", "📸 Final"]
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("📧 Enviar Relatório Rápido")
        st.warning("⚠️ IMPORTANTE: No modo cloud, envie o relatório IMEDIATAMENTE após cadastrar as fotos, antes que o app reinicie!")
        if st.button("🚀 Ir para Envio de E-mail", use_container_width=True, type="primary"):
            st.info("Vá para a aba '📧 Enviar por E-mail' para configurar e enviar o relatório completo com fotos.")

# ==================== NOVA VIAGEM ====================
elif pagina == "➕ Nova Viagem":
    st.markdown('<div class="main-header">➕ Registrar Nova Viagem</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="warning-box">
    <strong>💡 Dica do Modo Cloud:</strong><br>
    Após cadastrar esta viagem e suas fotos, vá imediatamente para <strong>"📧 Enviar por E-mail"</strong> 
    e envie o relatório. As fotos são temporárias e podem ser perdidas se o app reiniciar!
    </div>
    """, unsafe_allow_html=True)

    with st.form("form_viagem", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            data_viagem = st.date_input("📅 Data da Viagem", value=date.today())
            turno = st.selectbox("🕐 Turno", TURNOS)
            numero_onibus = st.text_input("🚌 Número do Ônibus", placeholder="Ex: 001, 102, etc.")
        with col2:
            km_inicial = st.number_input("📍 KM Inicial", min_value=0.0, step=0.1, format="%.1f")
            km_final = st.number_input("🏁 KM Final", min_value=0.0, step=0.1, format="%.1f")
            passageiros = st.number_input("👥 Quantidade de Passageiros", min_value=0, step=1)
        observacao = st.text_area("📝 Observação (opcional)", placeholder="Alguma observação sobre a viagem...")
        st.markdown("---")
        st.markdown("### 📸 Fotos de Evidência (IMPORTANTE - Serão enviadas por e-mail)")
        st.info("Tire fotos do hodômetro. Elas serão incluídas no ZIP enviado por e-mail.")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            foto_inicial = st.file_uploader("📷 Foto do KM INICIAL", type=["jpg", "jpeg", "png"], key="foto_ini")
            if foto_inicial is not None: st.image(foto_inicial, caption="Preview KM Inicial", use_container_width=True)
        with col_f2:
            foto_final = st.file_uploader("📷 Foto do KM FINAL", type=["jpg", "jpeg", "png"], key="foto_fim")
            if foto_final is not None: st.image(foto_final, caption="Preview KM Final", use_container_width=True)
        dt_preview = pd.to_datetime(data_viagem)
        st.info(f"📅 Será registrado como: **{DIAS_SEMANA[dt_preview.weekday()]}**, Semana {dt_preview.isocalendar()[1]}, {MESES[dt_preview.month-1]}/{dt_preview.year}")
        if km_final > km_inicial: st.success(f"📏 KM a ser percorrido: **{km_final - km_inicial:,.2f} km**")
        elif km_final > 0 and km_final <= km_inicial: st.warning("⚠️ KM Final deve ser maior que KM Inicial!")
        submitted = st.form_submit_button("✅ Salvar Viagem", use_container_width=True)
        if submitted:
            if not numero_onibus: st.error("❌ Informe o número do ônibus!")
            elif km_final <= km_inicial: st.error("❌ KM Final deve ser maior que KM Inicial!")
            else:
                viagem = adicionar_viagem(data_viagem, turno, numero_onibus, km_inicial, km_final, passageiros, observacao, foto_inicial, foto_final)
                msg_foto = ""
                if viagem["tem_foto_inicial"]: msg_foto += " 📸 Foto inicial salva!"
                if viagem["tem_foto_final"]: msg_foto += " 📸 Foto final salva!"
                st.success(f"✅ Viagem #{viagem['id']} registrada!{msg_foto}")
                st.markdown("""
                <div class="success-box">
                <strong>✅ Viagem salva com sucesso!</strong><br>
                <strong>⚠️ PRÓXIMO PASSO IMPORTANTE:</strong><br>
                Vá para a aba <strong>"📧 Enviar por E-mail"</strong> e envie o relatório AGORA para preservar as fotos!<br>
                No modo cloud, as fotos podem ser perdidas se o app reiniciar.
                </div>
                """, unsafe_allow_html=True)
                st.balloons()

# ==================== RELATÓRIOS ====================
elif pagina == "📊 Relatórios":
    st.markdown('<div class="main-header">📊 Relatórios e Análises</div>', unsafe_allow_html=True)
    dados = carregar_dados()
    if not dados: st.warning("Nenhum dado disponível para gerar relatórios.")
    else:
        df = df_viagens()
        st.subheader("🔍 Filtros")
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1: data_inicio = st.date_input("Data Início", value=df["data"].min().date())
        with col_f2: data_fim = st.date_input("Data Fim", value=df["data"].max().date())
        with col_f3: turno_filtro = st.multiselect("Turno", TURNOS, default=TURNOS)
        with col_f4: ano_filtro = st.multiselect("Ano", sorted(df["ano"].unique().tolist()), default=sorted(df["ano"].unique().tolist()))
        df_filtrado = df[(df["data"].dt.date >= data_inicio) & (df["data"].dt.date <= data_fim) & (df["turno"].isin(turno_filtro)) & (df["ano"].isin(ano_filtro))]
        if df_filtrado.empty: st.warning("Nenhum dado encontrado com os filtros selecionados.")
        else:
            st.markdown("---")
            st.subheader("📋 Resumo do Período Selecionado")
            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            with col_r1: st.metric("Total de Viagens", len(df_filtrado))
            with col_r2: st.metric("KM Total", f"{df_filtrado['km_percorrido'].sum():,.2f}")
            with col_r3: st.metric("Passageiros", f"{df_filtrado['passageiros'].sum():,}")
            with col_r4: st.metric("Média KM/Viagem", f"{df_filtrado['km_percorrido'].mean():,.2f}")
            st.markdown("---")
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.subheader("📈 KM por Dia")
                st.line_chart(df_filtrado.groupby(df_filtrado["data"].dt.date)["km_percorrido"].sum())
            with col_g2:
                st.subheader("📊 KM por Ônibus")
                st.bar_chart(df_filtrado.groupby("numero_onibus")["km_percorrido"].sum().sort_values(ascending=False))
            st.markdown("---")
            st.subheader("📑 Resumo por Dia e Turno")
            resumo_dia_turno = df_filtrado.groupby([df_filtrado["data"].dt.date, "turno"]).agg({"km_percorrido": "sum", "passageiros": "sum", "numero_onibus": "nunique", "id": "count"}).rename(columns={"numero_onibus": "onibus_unicos", "id": "viagens"})
            resumo_dia_turno.columns = ["KM Total", "Passageiros", "Ônibus Únicos", "Viagens"]
            st.dataframe(resumo_dia_turno, use_container_width=True)
            st.markdown("---")
            st.subheader("🚌 Detalhamento por Ônibus")
            resumo_onibus = df_filtrado.groupby("numero_onibus").agg({"km_percorrido": ["sum", "mean", "count"], "passageiros": "sum", "data": ["min", "max"]})
            resumo_onibus.columns = ["KM Total", "KM Médio", "Viagens", "Passageiros", "Primeira Viagem", "Última Viagem"]
            st.dataframe(resumo_onibus.sort_values("KM Total", ascending=False), use_container_width=True)
            st.markdown("---")
            st.subheader("💾 Exportar Dados")
            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_filtrado.to_excel(writer, sheet_name='Viagens', index=False)
                    resumo_dia_turno.to_excel(writer, sheet_name='Resumo Dia-Turno')
                    resumo_onibus.to_excel(writer, sheet_name='Resumo Ônibus')
                st.download_button(label="📥 Baixar Relatório Excel", data=buffer.getvalue(), file_name=f"relatorio_km_{data_inicio}_a_{data_fim}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with col_exp2:
                csv = df_filtrado.to_csv(index=False).encode('utf-8')
                st.download_button(label="📥 Baixar Dados CSV", data=csv, file_name=f"dados_viagens_{data_inicio}_a_{data_fim}.csv", mime="text/csv", use_container_width=True)

# ==================== ANÁLISE TEMPORAL ====================
elif pagina == "📈 Análise Temporal":
    st.markdown('<div class="main-header">📈 Análise Temporal e Comparativos</div>', unsafe_allow_html=True)
    dados = carregar_dados()
    if not dados: st.warning("Nenhum dado disponível para análise temporal.")
    else:
        df = df_viagens()
        anos_disponiveis = sorted(df["ano"].unique().tolist())
        ano_selecionado = st.selectbox("📅 Selecione o Ano para Análise", anos_disponiveis, index=len(anos_disponiveis)-1)
        df_ano = df[df["ano"] == ano_selecionado]
        if df_ano.empty: st.warning(f"Nenhum dado para o ano {ano_selecionado}.")
        else:
            st.subheader("📅 Comparativo Semanal")
            comp_sem = comparacao_semanal(df_ano)
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1: st.metric("KM Semana Atual", f"{comp_sem['atual_km']:,.1f} km", f"{((comp_sem['atual_km'] - comp_sem['anterior_km']) / comp_sem['anterior_km'] * 100) if comp_sem['anterior_km'] > 0 else 0:+.1f}%")
            with col_s2: st.metric("Viagens", comp_sem["atual_viagens"], f"{comp_sem['atual_viagens'] - comp_sem['anterior_viagens']:+d}")
            with col_s3: st.metric("Passageiros", comp_sem["atual_passageiros"], f"{comp_sem['atual_passageiros'] - comp_sem['anterior_passageiros']:+d}")
            st.subheader("📊 KM por Semana do Ano")
            st.bar_chart(df_ano.groupby("semana_ano")["km_percorrido"].sum().sort_index())
            st.markdown("---")
            st.subheader("📆 Comparativo Mensal")
            comp_mes = comparacao_mensal(df_ano)
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1: st.metric("KM Mês Atual", f"{comp_mes['atual_km']:,.1f} km", f"{((comp_mes['atual_km'] - comp_mes['anterior_km']) / comp_mes['anterior_km'] * 100) if comp_mes['anterior_km'] > 0 else 0:+.1f}%")
            with col_m2: st.metric("Viagens", comp_mes["atual_viagens"], f"{comp_mes['atual_viagens'] - comp_mes['anterior_viagens']:+d}")
            with col_m3: st.metric("Passageiros", comp_mes["atual_passageiros"], f"{comp_mes['atual_passageiros'] - comp_mes['anterior_passageiros']:+d}")
            st.subheader("📊 KM por Mês")
            km_por_mes = df_ano.groupby("mes")["km_percorrido"].sum().reindex(range(1,13), fill_value=0)
            km_por_mes.index = MESES
            st.bar_chart(km_por_mes)
            st.markdown("---")
            st.subheader("📅 Análise por Dia da Semana")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.markdown("#### KM por Dia da Semana")
                km_por_dia_sem = df_ano.groupby("dia_semana")["km_percorrido"].sum()
                st.bar_chart(km_por_dia_sem.reindex([d for d in DIAS_SEMANA if d in km_por_dia_sem.index]))
            with col_d2:
                st.markdown("#### Passageiros por Dia da Semana")
                pass_por_dia_sem = df_ano.groupby("dia_semana")["passageiros"].sum()
                st.bar_chart(pass_por_dia_sem.reindex([d for d in DIAS_SEMANA if d in pass_por_dia_sem.index]))
            resumo_dia_sem = df_ano.groupby("dia_semana").agg({"km_percorrido": ["sum", "mean"], "passageiros": ["sum", "mean"], "id": "count"})
            resumo_dia_sem.columns = ["KM Total", "KM Médio", "Pass Total", "Pass Médio", "Viagens"]
            st.dataframe(resumo_dia_sem.reindex([d for d in DIAS_SEMANA if d in resumo_dia_sem.index]), use_container_width=True)
            st.markdown("---")
            st.subheader("📈 Tendência e Evolução")
            dias_tendencia = st.slider("Período de Análise (dias)", 7, 90, 30)
            tendencia = tendencia_ultimos_dias(df_ano, dias_tendencia)
            if not tendencia.empty:
                st.line_chart(tendencia[["km_percorrido", "passageiros"]])
                col_t1, col_t2, col_t3 = st.columns(3)
                with col_t1: st.metric("KM Médio/Dia", f"{tendencia['km_percorrido'].mean():,.1f}")
                with col_t2: st.metric("Passageiros Médio/Dia", f"{tendencia['passageiros'].mean():,.0f}")
                with col_t3: st.metric("Viagens Médio/Dia", f"{tendencia['viagens'].mean():,.1f}")
            else: st.info(f"Dados insuficientes para tendência de {dias_tendencia} dias.")
            st.markdown("---")
            st.subheader("📊 Comparativo Mês a Mês - Resumo Completo")
            resumo_mensal = df_ano.groupby(["mes", "mes_nome"]).agg({"km_percorrido": ["sum", "mean"], "passageiros": ["sum", "mean"], "numero_onibus": "nunique", "id": "count"})
            resumo_mensal.columns = ["KM Total", "KM Médio/Viagem", "Passageiros", "Pass Médio/Viagem", "Ônibus Únicos", "Total Viagens"]
            st.dataframe(resumo_mensal.reset_index().set_index("mes_nome"), use_container_width=True)
            st.markdown("---")
            st.subheader("💾 Exportar Análise Temporal")
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                resumo_mensal.reset_index().set_index("mes_nome").to_excel(writer, sheet_name='Resumo Mensal')
                df_ano.groupby("semana_ano").agg({"km_percorrido": "sum", "passageiros": "sum", "id": "count"}).rename(columns={"id": "viagens"}).to_excel(writer, sheet_name='Resumo Semanal')
                resumo_dia_sem.to_excel(writer, sheet_name='Resumo Dia Semana')
                df_ano.to_excel(writer, sheet_name='Dados Ano', index=False)
            st.download_button(label="📥 Baixar Análise Temporal (Excel)", data=buffer.getvalue(), file_name=f"analise_temporal_{ano_selecionado}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

# ==================== ENVIAR POR E-MAIL ====================
elif pagina == "📧 Enviar por E-mail":
    st.markdown('<div class="main-header">📧 Enviar Relatório por E-mail</div>', unsafe_allow_html=True)
    dados = carregar_dados()
    if not dados: st.warning("Nenhum dado para enviar. Cadastre viagens primeiro.")
    else:
        df = df_viagens()
        st.markdown("""
        <div class="email-box">
        <h3>📧 Envio Automático de Relatórios</h3>
        <p>Configure o e-mail e envie o relatório completo (Excel + Fotos) em um único ZIP.</p>
        <p><strong>Importante:</strong> No modo cloud, os dados são temporários. Envie regularmente!</p>
        </div>
        """, unsafe_allow_html=True)

        # Verificar fotos disponíveis
        fotos_disp = verificar_fotos_existentes(df)
        st.markdown("---")
        st.subheader("📸 Status das Fotos")
        if fotos_disp:
            st.success(f"✅ {len(fotos_disp)} fotos de evidência encontradas no servidor e prontas para envio!")
            with st.expander("Ver lista de fotos disponíveis"):
                for f in fotos_disp:
                    st.write(f"   • Viagem #{f['id']} - {f['onibus']} - {f['tipo']} - {os.path.basename(f['caminho'])}")
        else:
            st.error("❌ NENHUMA foto encontrada no servidor!")
            st.info("💡 Se você acabou de cadastrar fotos, elas ainda estão aqui. Envie o relatório AGORA antes que o app reinicie!")

        st.markdown("---")
        st.markdown("""
        <div class="warning-box">
        <strong>🔐 Configuração de E-mail:</strong><br>
        Use <strong>Senha de App</strong> do Gmail/Outlook, não sua senha normal.<br>
        Gmail: Configurações → Segurança → Verificação em 2 etapas → Senhas de app
        </div>
        """, unsafe_allow_html=True)

        st.subheader("⚙️ Configuração do E-mail")
        config = carregar_config_email()
        with st.expander("Configurar E-mail Remetente (salvo localmente)"):
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                email_remetente = st.text_input("Seu E-mail", value=config.get("email", ""), placeholder="seu.email@gmail.com")
                smtp_server = st.selectbox("Servidor SMTP", ["smtp.gmail.com", "smtp.office365.com", "smtp.mail.yahoo.com", "smtp.outlook.com", "Outro"], index=0 if config.get("smtp") == "smtp.gmail.com" else 4)
                if smtp_server == "Outro": smtp_server = st.text_input("Servidor SMTP Customizado", value=config.get("smtp", ""))
            with col_e2:
                senha_app = st.text_input("Senha de App", value=config.get("senha", ""), type="password", help="Não use sua senha normal! Use 'Senha de App' do Gmail/Outlook.")
                smtp_port = st.number_input("Porta SMTP", value=config.get("porta", 587), min_value=1, max_value=65535)
            if st.button("💾 Salvar Configuração"):
                if email_remetente and senha_app:
                    salvar_config_email({"email": email_remetente, "senha": senha_app, "smtp": smtp_server, "porta": smtp_port})
                    st.success("✅ Configuração salva! (Armazenada localmente)")
                else: st.error("❌ Preencha e-mail e senha.")

        st.markdown("---")
        st.subheader("📅 Período do Relatório")
        col_p1, col_p2 = st.columns(2)
        with col_p1: data_inicio = st.date_input("Data Início", value=df["data"].min().date())
        with col_p2: data_fim = st.date_input("Data Fim", value=df["data"].max().date())
        st.subheader("📎 Opções do Anexo")
        incluir_fotos = st.checkbox("📸 Incluir fotos de evidência no ZIP", value=True)
        df_periodo = df[(df["data"].dt.date >= data_inicio) & (df["data"].dt.date <= data_fim)]

        st.markdown("---")
        st.subheader("📊 Resumo do Período Selecionado")
        col_pr1, col_pr2, col_pr3, col_pr4 = st.columns(4)
        with col_pr1: st.metric("Viagens", len(df_periodo))
        with col_pr2: st.metric("KM Total", f"{df_periodo['km_percorrido'].sum():,.2f}")
        with col_pr3: st.metric("Passageiros", f"{df_periodo['passageiros'].sum():,}")
        with col_pr4: st.metric("Fotos", int(df_periodo["tem_foto_inicial"].sum() + df_periodo["tem_foto_final"].sum()))

        # Verificar fotos reais do período
        fotos_periodo = verificar_fotos_existentes(df_periodo)
        if fotos_periodo:
            st.success(f"✅ {len(fotos_periodo)} fotos reais encontradas e serão incluídas no ZIP!")
        else:
            st.warning("⚠️ Nenhuma foto física encontrada para este período. O ZIP conterá apenas o Excel.")

        st.markdown("---")
        st.subheader("📧 Enviar Relatório")
        destinatario = st.text_input("📧 E-mail do Destinatário", placeholder="chefe@empresa.com.br")
        if config.get("email"): st.info(f"📤 Enviando de: **{config['email']}**")
        else: st.warning("⚠️ Configure o e-mail remetente acima primeiro!")

        if st.button("🚀 Gerar ZIP e Enviar E-mail", use_container_width=True, type="primary"):
            if not destinatario: st.error("❌ Informe o e-mail do destinatário!")
            elif not config.get("email") or not config.get("senha"): st.error("❌ Configure o e-mail remetente primeiro!")
            else:
                with st.spinner("📦 Gerando relatório ZIP..."):
                    zip_buffer, erro = criar_relatorio_zip(data_inicio, data_fim, incluir_fotos)
                    if erro: st.error(f"❌ {erro}")
                    else:
                        st.success("✅ ZIP gerado com sucesso!")
                        tamanho_kb = len(zip_buffer.getvalue()) / 1024
                        st.info(f"📦 Tamanho do anexo: **{tamanho_kb:,.1f} KB**")

                        # Listar conteúdo do ZIP
                        with zipfile.ZipFile(zip_buffer, 'r') as zf:
                            arquivos = zf.namelist()
                            st.write("📁 Arquivos no ZIP:")
                            for arq in arquivos[:15]: st.write(f"   • {arq}")
                            if len(arquivos) > 15: st.write(f"   ... e mais {len(arquivos)-15} arquivos")
                            # Contar fotos
                            fotos_no_zip = [a for a in arquivos if a.startswith("fotos_evidencias/") and not a.endswith("README.txt") and not a.endswith("INDICE_FOTOS.csv")]
                            if fotos_no_zip: st.success(f"📸 {len(fotos_no_zip)} fotos incluídas no ZIP!")
                            else: st.warning("⚠️ Nenhuma foto no ZIP (apenas relatório Excel)")

                        zip_buffer.seek(0)

                        with st.spinner("📧 Enviando e-mail..."):
                            assunto = f"Relatório de KM - {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
                            corpo = f"""Olá,

Segue em anexo o relatório de controle de KM rodado.

Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}
Total de Viagens: {len(df_periodo)}
KM Total: {df_periodo['km_percorrido'].sum():,.2f} km
Passageiros: {df_periodo['passageiros'].sum():,}
Fotos de evidência: {len(fotos_periodo)}

O ZIP contém:
- relatorio_km.xlsx (5 abas com análises)
- fotos_evidencias/ (fotos do hodômetro)
- INDICE_FOTOS.csv (lista organizada das fotos)

Relatório gerado automaticamente pelo sistema de controle de KM.
"""

                            sucesso, msg = enviar_email(destinatario, assunto, corpo, zip_buffer, f"relatorio_km_{data_inicio}_{data_fim}.zip", config.get("smtp", "smtp.gmail.com"), config.get("porta", 587), config.get("email"), config.get("senha"))
                            if sucesso:
                                st.success(f"✅ {msg}")
                                st.markdown("""
                                <div class="success-box">
                                <strong>📧 E-mail enviado com sucesso!</strong><br>
                                O relatório e as fotos estão no seu e-mail.<br>
                                <strong>Próximo passo:</strong> Baixe o ZIP no PC e salve como evidência permanente!
                                </div>
                                """, unsafe_allow_html=True)
                                st.balloons()
                            else:
                                st.error(f"❌ {msg}")
                                st.info("💡 Dica: Verifique se a 'Senha de App' está correta e se o servidor SMTP está correto.")

        st.markdown("---")
        st.subheader("💾 Ou Baixar ZIP Manualmente")
        if st.button("📥 Baixar Relatório ZIP", use_container_width=True):
            with st.spinner("📦 Gerando ZIP..."):
                zip_buffer, erro = criar_relatorio_zip(data_inicio, data_fim, incluir_fotos)
                if erro: st.error(f"❌ {erro}")
                else:
                    st.download_button(label="⬇️ Clique para baixar", data=zip_buffer.getvalue(), file_name=f"relatorio_km_{data_inicio}_{data_fim}.zip", mime="application/zip", use_container_width=True)

# ==================== DADOS COMPLETOS ====================
elif pagina == "🗂️ Dados Completos":
    st.markdown('<div class="main-header">🗂️ Todos os Registros</div>', unsafe_allow_html=True)
    dados = carregar_dados()
    if not dados: st.info("Nenhuma viagem registrada.")
    else:
        df = df_viagens()
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1: busca_onibus = st.text_input("🔍 Buscar Ônibus", placeholder="Digite o número...")
        with col_f2: turno_filter = st.multiselect("Filtrar Turno", TURNOS, default=TURNOS)
        with col_f3: mes_filter = st.multiselect("Filtrar Mês", MESES, default=MESES)
        df_filtered = df[df["turno"].isin(turno_filter) & df["mes_nome"].isin(mes_filter)]
        if busca_onibus: df_filtered = df_filtered[df_filtered["numero_onibus"].astype(str).str.contains(busca_onibus, case=False)]
        st.markdown(f"**{len(df_filtered)}** registros encontrados")
        for idx, row in df_filtered.iterrows():
            with st.container():
                col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([0.7, 1.1, 0.9, 0.8, 1.1, 1, 0.8, 0.8])
                with col1: st.write(f"**#{row['id']}**")
                with col2: st.write(f"📅 {row['data'].strftime('%d/%m/%Y')}")
                with col3: st.write(f"📆 {row['dia_semana']}")
                with col4: st.write(f"🕐 {row['turno']}")
                with col5: st.write(f"🚌 {row['numero_onibus']}")
                with col6: st.write(f"📏 {row['km_percorrido']:,.2f} km")
                with col7: st.write(f"👥 {row['passageiros']}")
                with col8:
                    fotos = []
                    if row.get("tem_foto_inicial"): fotos.append("📷I")
                    if row.get("tem_foto_final"): fotos.append("📷F")
                    if fotos: st.markdown(f'<span style="background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); color: white; padding: 0.3rem 0.8rem; border-radius: 1rem; font-size: 0.8rem; font-weight: bold;">{" ".join(fotos)}</span>', unsafe_allow_html=True)
                    else: st.write("—")
            with st.expander("🔍 Ver detalhes e fotos"):
                viagem_completa = next((v for v in dados if v["id"] == row["id"]), None)
                if viagem_completa:
                    col_det1, col_det2, col_det3 = st.columns(3)
                    with col_det1:
                        st.write(f"**KM Inicial:** {viagem_completa['km_inicial']:,.1f}")
                        st.write(f"**KM Final:** {viagem_completa['km_final']:,.1f}")
                        st.write(f"**KM Percorrido:** {viagem_completa['km_percorrido']:,.2f}")
                    with col_det2:
                        st.write(f"**Semana:** {viagem_completa['semana_ano']}")
                        st.write(f"**Mês:** {viagem_completa['mes_nome']}")
                        st.write(f"**Ano:** {viagem_completa['ano']}")
                    with col_det3: st.write(f"**Observação:** {viagem_completa.get('observacao', '—')}")
                    col_foto1, col_foto2 = st.columns(2)
                    with col_foto1:
                        if viagem_completa.get("foto_inicial") and os.path.exists(viagem_completa["foto_inicial"]):
                            st.markdown("**📷 Foto KM Inicial:**")
                            st.image(viagem_completa["foto_inicial"], use_container_width=True)
                        elif viagem_completa.get("tem_foto_inicial"): st.warning("📷 Foto inicial não encontrada no disco.")
                        else: st.info("Sem foto do KM inicial.")
                    with col_foto2:
                        if viagem_completa.get("foto_final") and os.path.exists(viagem_completa["foto_final"]):
                            st.markdown("**📷 Foto KM Final:**")
                            st.image(viagem_completa["foto_final"], use_container_width=True)
                        elif viagem_completa.get("tem_foto_final"): st.warning("📷 Foto final não encontrada no disco.")
                        else: st.info("Sem foto do KM final.")
            if st.button("🗑️ Excluir Viagem", key=f"del_{row['id']}"):
                excluir_viagem(row['id'])
                st.success(f"Viagem #{row['id']} e fotos associadas excluídas!")
                st.rerun()
            st.divider()
        st.markdown("---")
        if st.button("⚠️ Limpar Todos os Dados", type="secondary", use_container_width=True):
            confirm = st.checkbox("Confirmar exclusão de TODOS os dados e fotos?")
            if confirm:
                for v in dados:
                    if v.get("foto_inicial") and os.path.exists(v["foto_inicial"]): os.remove(v["foto_inicial"])
                    if v.get("foto_final") and os.path.exists(v["foto_final"]): os.remove(v["foto_final"])
                salvar_dados([])
                st.success("Todos os dados e fotos foram removidos!")
                st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align: center; color: gray; font-size: 0.8rem;'>🚌 Controle de KM Cloud v2.0 - Fotos Corrigidas</div>", unsafe_allow_html=True)