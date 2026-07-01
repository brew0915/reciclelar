import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import engine
from menu import render_menu
from io import BytesIO
from openpyxl import Workbook

# 1. CONFIGURAÇÃO DA PÁGINA (Sempre o primeiro comando)
st.set_page_config(
    page_title="Materiais | Painel Executivo",
    page_icon="📦",
    layout="wide"
)

# 2. CARREGAMENTO DE ESTILOS E AUTENTICAÇÃO
def carregar_css():
    try:
        with open("assets/style.css", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass  # Evita quebra caso o arquivo mude de diretório

carregar_css()

if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

render_menu()

# =====================================
# REGRAS DE NEGÓCIO / PERFIL
# =====================================
perfil = st.session_state["usuario"]["perfil"]

if perfil == "ADMIN":
    with engine.connect() as conn:
        filiais = pd.read_sql(
            "SELECT id, nome FROM filiais ORDER BY nome", 
            conn
        )
    
    st.sidebar.markdown("### 🏢 Gestão Institucional")
    filial_escolhida = st.sidebar.selectbox(
        "Filial Ativa",
        ["Todas"] + filiais["nome"].tolist(),
        key="filial_admin"
    )
    st.session_state["filial_ativa"] = filial_escolhida
else:
    st.session_state["filial_ativa"] = st.session_state["usuario"]["filial_id"]

# =====================================
# CABEÇALHO PRINCIPAL
# =====================================
st.title("📦 Cadastro de Materiais")
st.markdown("Gerencie o catálogo unificado de insumos e categorias operacionais.")

# =====================================
# OPERAÇÕES DE ENTRADA (Módulos em Abas)
# =====================================
tab_individual, tab_lote = st.tabs(["➕ Cadastro Individual", "📥 Importação em Lote (Excel)"])

# --- ABA 1: CADASTRO INDIVIDUAL ---
with tab_individual:
    with st.form("form_material", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            descricao = st.text_input("Descrição do Material", placeholder="Ex: Garrafa PET Transparente")
        with col2:
            categoria = st.selectbox("Categoria", ["Papel", "Plástico", "Metal", "Vidro", "Eletrônico", "Outros"])
        with col3:
            unidade = st.selectbox("Unidade de Medida", ["KG", "TON", "UN", "GR"])
        
        salvar = st.form_submit_button("💾 Salvar Novo Material", use_container_width=True)

    if salvar:
        descricao = descricao.strip()
        if not descricao:
            st.warning("⚠️ Por favor, informe a descrição do material.")
        else:
            with engine.begin() as conn:
                existe = conn.execute(
                    text("SELECT COUNT(*) FROM materiais WHERE UPPER(descricao) = UPPER(:descricao)"),
                    {"descricao": descricao}
                ).scalar()

                if existe > 0:
                    st.error("🛑 Este material já está cadastrado no sistema.")
                else:
                    conn.execute(
                        text("""
                            INSERT INTO materiais (descricao, categoria, unidade)
                            VALUES (:descricao, :categoria, :unidade)
                        """),
                        {"descricao": descricao, "categoria": categoria, "unidade": unidade}
                    )
                    st.success(f"✔️ Material '{descricao}' cadastrado com sucesso!")
                    st.rerun()

# --- ABA 2: IMPORTAÇÃO EM LOTE ---
with tab_lote:
    # Gerador Dinâmico do Modelo Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Modelos"
    ws.append(["Descrição", "Categoria", "Unidade"])
    ws.append(["PET", "Plástico", "KG"])
    ws.append(["Papelão", "Papel", "KG"])
    
    arquivo_excel = BytesIO()
    wb.save(arquivo_excel)
    excel_modelo = arquivo_excel.getvalue()

    c_down, c_up = st.columns(2)
    with c_down:
        st.markdown("### 1. Baixe o Padrão")
        st.download_button(
            "⬇️ Baixar Planilha Modelo",
            data=excel_modelo,
            file_name="Modelo_Materiais.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with c_up:
        st.markdown("### 2. Envie o Arquivo")
        arquivo = st.file_uploader("Arraste ou selecione o arquivo editado", type=["xlsx"], label_visibility="collapsed")

    if arquivo is not None:
        df_import = pd.read_excel(arquivo)
        st.metric("Registros Detectados", len(df_import))
        st.dataframe(df_import, use_container_width=True, hide_index=True)

        if st.button("💾 Executar Importação em Lote", type="primary", use_container_width=True):
            obrigatorias = ["Descrição", "Categoria", "Unidade"]
            if not all(col in df_import.columns for col in obrigatorias):
                st.error("❌ Erro de layout: A planilha enviada não corresponde ao modelo oficial.")
                st.stop()

            total_importado = 0
            with engine.begin() as conn:
                for _, row in df_import.iterrows():
                    desc_row = str(row["Descrição"]).strip()
                    cat_row = str(row["Categoria"]).strip()
                    uni_row = str(row["Unidade"]).strip().upper()

                    if not desc_row or desc_row.upper() == "NAN":
                        continue

                    existe = conn.execute(
                        text("SELECT COUNT(*) FROM materiais WHERE UPPER(descricao) = UPPER(:descricao)"),
                        {"descricao": desc_row}
                    ).scalar()

                    if existe == 0:
                        conn.execute(
                            text("""
                                INSERT INTO materiais (descricao, categoria, unidade)
                                VALUES (:descricao, :categoria, :unidade)
                            """),
                            {"descricao": desc_row, "categoria": cat_row, "unidade": uni_row}
                        )
                        total_importado += 1

            st.success(f"🚀 Sucesso! {total_importado} novos materiais integrados à base de dados.")
            st.rerun()


# =====================================
# VISUALIZAÇÃO E PERFORMANCE (GRID)
# =====================================
st.subheader("📋 Painel de Monitoramento")

with engine.connect() as conn:
    df_lista = pd.read_sql("SELECT id, descricao, categoria, unidade FROM materiais ORDER BY descricao", conn)

if df_lista.empty:
    st.info("ℹ️ Nenhum material registrado até o momento.")
    st.stop()

# Busca Executiva Avançada
busca = st.text_input("🔎 Filtragem rápida por descrição", placeholder="Digite o termo para buscar...")
if busca:
    df_lista = df_lista[df_lista["descricao"].str.contains(busca, case=False, na=False)]

# Indicadores de Performance (KPIs) de Alto Impacto
kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.metric("📦 Catálogo Ativo", f"{len(df_lista)} itens")
with kpi2:
    st.metric("📂 Categorias Utilizadas", df_lista["categoria"].nunique())
with kpi3:
    st.metric("📐 Tipos de Unidades", df_lista["unidade"].nunique())

# Grid de Dados Formatado
st.dataframe(
    df_lista,
    use_container_width=True,
    hide_index=True,
    column_config={
        "id": st.column_config.NumberColumn("ID Interno", format="%d"),
        "descricao": "Descrição Comercial",
        "categoria": "Segmentação de Categoria",
        "unidade": st.column_config.TextColumn("U.M.", help="Unidade de Medida Padronizada")
    }
)

# =====================================
# MÓDULO DE DELEÇÃO PROTEGIDA
# =====================================
with st.expander("🗑️ Zona de Risco (Exclusão de Registros)", expanded=False):
    st.markdown("Selecione um material abaixo para removê-lo definitivamente do sistema.")
    
    material_excluir = st.selectbox("Selecione o registro para deleção", df_lista["descricao"].tolist(), key="select_del")
    
    # Aciona o gatilho de confirmação usando Session State de forma segura
    if st.button("Solicitar Exclusão", type="secondary", use_container_width=True):
        st.session_state["confirmar_exclusao"] = True

    if st.session_state.get("confirmar_exclusao", False):
        st.error(f"⚠️ Atenção! Confirma a exclusão definitiva do item: **{material_excluir}**?")
        
        c_conf, c_canc = st.columns(2)
        with c_conf:
            if st.button("✅ Sim, Confirmar", type="primary", use_container_width=True):
                material_id = df_lista.loc[df_lista["descricao"] == material_excluir, "id"].iloc[0]
                
                with engine.begin() as conn:
                    conn.execute(
                        text("DELETE FROM materiais WHERE id = :id"),
                        {"id": int(material_id)}
                    )
                
                st.session_state["confirmar_exclusao"] = False
                st.success("Registro removido!")
                st.rerun()
                
        with c_canc:
            if st.button("❌ Cancelar Operação", use_container_width=True):
                st.session_state["confirmar_exclusao"] = False
                st.rerun()