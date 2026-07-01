import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import engine
from menu import render_menu

# =====================================
# CONFIGURAÇÃO DA PÁGINA & ESTILOS
# =====================================
# Boa prática: Definir configurações de layout antes de renderizar componentes
st.set_page_config(
    page_title="Configuração de Estoque Mínimo",
    page_icon="⚠️",
    layout="wide"
)

def carregar_css():
    try:
        with open("assets/style.css", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

carregar_css()
render_menu()

# Restrição de Acesso de Sessão
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

perfil = st.session_state["usuario"]["perfil"]

# Regras de Negócio e Contexto de Filial (Sidebar)
if perfil == "ADMIN":
    with engine.connect() as conn:
        filiais = pd.read_sql("SELECT id, nome FROM filiais ORDER BY nome", conn)

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
# CABEÇALHO PRINCIPAL & KPIs
# =====================================
st.title("⚠️ Parâmetros de Segurança de Estoque")
st.markdown("Defina os níveis críticos de suprimentos. O sistema gerará notificações automáticas ao atingir os limites estipulados.")

# Busca e Sincronização de Dados Unificada
with engine.connect() as conn:
    materiais = pd.read_sql(
        """
        SELECT 
            m.id, 
            m.descricao, 
            m.unidade,
            COALESCE(em.quantidade_minima, 0.0) AS quantidade_minima
        FROM materiais m
        LEFT JOIN estoque_minimo em ON m.id = em.material_id
        ORDER BY m.descricao
        """, 
        conn
    )

# KPIs Executivos para Visibilidade de Cobertura
kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.metric("📦 Materiais Cadastrados", f"{len(materiais)} itens")
with kpi2:
    configurados = len(materiais[materiais["quantidade_minima"] > 0])
    st.metric("🔒 Limites Parametrizados", f"{configurados} itens")
with kpi3:
    pendentes = len(materiais) - configurados
    st.metric("⏳ Sem Mínimo Definido", f"{pendentes} itens")


# =====================================
# PAINEL DE CONTROLE (DIVISÃO EM COLUNAS)
# =====================================
st.markdown("---")
col_Form, col_Grid = st.columns([1, 1.3], gap="large")

# --- COLUNA 1: FORMULÁRIO DE ATUALIZAÇÃO ---
with col_Form:
    st.subheader("⚙️ Ajustar Nível de Segurança")
    
    material_nome = st.selectbox(
        "Selecione o Material para Parametrização", 
        materiais["descricao"].tolist(),
        key="select_material_form"
    )

    # Captura de Metadados do Registro Selecionado
    material_id = materiais.loc[materiais["descricao"] == material_nome, "id"].iloc[0]
    valor_atual = materiais.loc[materiais["descricao"] == material_nome, "quantidade_minima"].iloc[0]
    unidade_medida = materiais.loc[materiais["descricao"] == material_nome, "unidade"].iloc[0]

    with st.container(border=True):
        quantidade_minima = st.number_input(
            f"Quantidade Mínima Operacional ({unidade_medida})",
            min_value=0.0,
            value=float(valor_atual),
            step=10.0,
            help="Defina o ponto de ressuprimento crítico para esta unidade de medida."
        )
        
        salvar = st.button("💾 Atualizar Diretriz de Estoque", type="primary", use_container_width=True)

    if salvar:
        with engine.begin() as conn:
            existe = conn.execute(
                text("SELECT COUNT(*) FROM estoque_minimo WHERE material_id = :material_id"),
                {"material_id": int(material_id)}
            ).scalar()

            if existe > 0:
                conn.execute(
                    text("""
                        UPDATE estoque_minimo 
                        SET quantidade_minima = :quantidade_minima 
                        WHERE material_id = :material_id
                    """),
                    {"quantidade_minima": quantidade_minima, "material_id": int(material_id)}
                )
            else:
                conn.execute(
                    text("""
                        INSERT INTO estoque_minimo (material_id, quantidade_minima) 
                        VALUES (:material_id, :quantidade_minima)
                    """),
                    {"material_id": int(material_id), "quantidade_minima": quantidade_minima}
                )
        st.success(f"✔️ Limite de segurança para '{material_nome}' atualizado!")
        st.rerun()

    # Módulo Avançado: Reset/Remoção de Parâmetros dentro da mesma coluna
    with st.expander("🗑️ Redefinir Parâmetros Existentes", expanded=False):
        st.caption("Ao redefinir, o material deixará de gerar notificações de criticidade.")
        material_remover = st.selectbox(
            "Material para remover restrição", 
            materiais[materiais["quantidade_minima"] > 0]["descricao"].tolist(),
            key="remover_material"
        )
        
        if st.button("Remover Alertas de Estoque Mínimo", type="secondary", use_container_width=True):
            if material_remover:
                material_id_remover = materiais.loc[materiais["descricao"] == material_remover, "id"].iloc[0]
                with engine.begin() as conn:
                    conn.execute(
                        text("DELETE FROM estoque_minimo WHERE material_id = :material_id"),
                        {"material_id": int(material_id_remover)}
                    )
                st.success("Configuração restaurada com sucesso.")
                st.rerun()
            else:
                st.warning("Nenhum material com parametrização ativa selecionado.")

# --- COLUNA 2: VISUALIZAÇÃO GERAL DO CATÁLOGO ---
with col_Grid:
    st.subheader("📋 Relatório de Diretrizes Ativas")
    
    # Campo de pesquisa interna rápido para o Grid
    busca_filtro = st.text_input("🔎 Pesquisa rápida de materiais", placeholder="Filtrar por nome...")
    
    df_exibicao = materiais.copy()
    if busca_filtro:
        df_exibicao = df_exibicao[df_exibicao["descricao"].str.contains(busca_filtro, case=False, na=False)]

    # Grid de dados com formatação profissional avançada
    st.dataframe(
        df_exibicao,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("Cód. Insumo", format="%d"),
            "descricao": st.column_config.TextColumn("Descrição Comercial"),
            "unidade": st.column_config.TextColumn("U.M.", help="Unidade de Medida Cadastrada"),
            "quantidade_minima": st.column_config.NumberColumn(
                "Estoque Mínimo Exigido", 
                format="%.2f",
                help="Quantidade limite de segurança abaixo da qual o sistema dispara alertas."
            )
        }
    )
