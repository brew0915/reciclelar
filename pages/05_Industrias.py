import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import engine
from menu import render_menu

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA (Sempre o primeiro comando)
# =====================================
st.set_page_config(
    page_title="Gestão de Indústrias | Controladoria",
    page_icon="🏭",
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

# =====================================
# 2. SEGURANÇA E CONTEXTO DE CONEXÃO
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

perfil = st.session_state["usuario"]["perfil"]

# ADMIN escolhe a filial
if perfil == "ADMIN":
    with engine.connect() as conn:
        filiais = pd.read_sql(
            "SELECT id, nome FROM filiais ORDER BY nome",
            conn
        )
    
    filial_escolhida = st.sidebar.selectbox(
        "🏢 Unidade Operacional",
        ["Todas"] + filiais["nome"].tolist(),
        key="filial_admin"
    )
    st.session_state["filial_ativa"] = filial_escolhida
else:
    st.session_state["filial_ativa"] = st.session_state["usuario"]["filial_id"]

# =====================================
# 3. INTERFACE CORPORATIVA (TABS)
# =====================================
st.title("🏭 Central de Indústrias Parceiras")
st.caption("Gerenciamento, homologação e manutenção cadastral de indústrias para escoamento.")

tab_consulta, tab_cadastro = st.tabs(["🔎 Consultar e Auditar", "➕ Homologar Nova Indústria"])

# -------------------------------------
# ABA 1: CONSULTA E MANUTENÇÃO
# -------------------------------------
with tab_consulta:
    # Busca e Filtros Avançados
    col_busca, col_vazia = st.columns([2, 2])
    with col_busca:
        busca = st.text_input("Filtrar por Nome da Organização", placeholder="Digite o nome para pesquisar...")

    # Carga de Dados Dinâmica
    with engine.connect() as conn:
        df = pd.read_sql(
            """
            SELECT id AS "ID", nome AS "Nome da Indústria", cnpj AS "CNPJ", 
                   contato AS "Ponto de Contato", telefone AS "Telefone", 
                   email AS "E-mail", endereco AS "Endereço"
            FROM industrias
            ORDER BY nome
            """,
            conn
        )

    if busca:
        df = df[df["Nome da Indústria"].str.contains(busca, case=False, na=False)]

    if df.empty:
        st.info("Nenhuma organização industrial mapeada no momento.")
    else:
        # Exibição Analítica com st.dataframe de alta performance
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn(format="%d", width="small"),
                "CNPJ": st.column_config.TextColumn(width="medium"),
                "E-mail": st.column_config.LinkColumn(),
                "Endereço": st.column_config.TextColumn(width="large")
            }
        )

        # Seção de Moderação / Exclusão Segura e Centralizada
        st.markdown("---")
        with st.expander("⚠️ Área de Descredenciamento / Exclusão"):
            st.markdown("<small>Selecione uma indústria para remover de forma permanente do ecossistema de banco de dados.</small>", unsafe_allow_html=True)
            industria_para_excluir = st.selectbox(
                "Selecione a empresa alvo",
                options=df["Nome da Indústria"].tolist(),
                index=None,
                placeholder="Escolha a indústria para exclusão..."
            )

            if industria_para_excluir:
                id_alvo = df[df["Nome da Indústria"] == industria_para_excluir]["ID"].values[0]
                
                st.warning(f"Atenção: A remoção de '{industria_para_excluir}' pode afetar históricos de vendas vinculados.")
                col_c1, col_c2, _ = st.columns([1, 1, 2])
                
                with col_c1:
                    if st.button("✅ Confirmar Remoção", use_container_width=True, type="primary"):
                        with engine.begin() as conn:
                            conn.execute(
                                text("DELETE FROM industrias WHERE id = :id"),
                                {"id": int(id_alvo)}
                            )
                        st.success("Organização removida com sucesso!")
                        st.rerun()
                with col_c2:
                    if st.button("❌ Abortar", use_container_width=True):
                        st.rerun()

# -------------------------------------
# ABA 2: FORMULÁRIO DE CADASTRO
# -------------------------------------
with tab_cadastro:
    st.markdown("### Formulário de Cadastro de Parceiro")
    
    with st.form("form_industria", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            nome = st.text_input("Nome Comercial / Razão Social", placeholder="Ex: Metalúrgica Alfa S.A.")
            cnpj = st.text_input("CNPJ (Apenas números)", placeholder="00.000.000/0000-00")
            contato = st.text_input("Gerente de Contas / Representante", placeholder="Ex: João Silva")
        
        with col_f2:
            telefone = st.text_input("Telefone Corporativo", placeholder="(00) 00000-0000")
            email = st.text_input("E-mail de Faturamento / XML", placeholder="suprimentos@empresa.com")
            endereco = st.text_area("Endereço Fiscal Completo", placeholder="Rua, Número, Bairro, Cidade - UF", height=68)

        st.markdown("<br>", unsafe_allow_html=True)
        salvar = st.form_submit_button("Salvar Registro Corporativo", type="primary")

    if salvar:
        if not nome.strip():
            st.error("Falha no envio: O campo 'Nome Comercial / Razão Social' é obrigatório.")
            st.stop()

        with engine.begin() as conn:
            # Validação de Duplicidade
            existe = conn.execute(
                text("SELECT COUNT(*) FROM industrias WHERE UPPER(nome) = UPPER(:nome)"),
                {"nome": nome.strip()}
            ).scalar()

            if existe > 0:
                st.error("Conflito cadastral: Esta indústria já se encontra ativa no sistema.")
                st.stop()

            # Inserção Limpa de Dados
            conn.execute(
                text("""
                    INSERT INTO industrias (nome, cnpj, contato, telefone, email, endereco)
                    VALUES (:nome, :cnpj, :contato, :telefone, :email, :endereco)
                """),
                {
                    "nome": nome.strip(),
                    "cnpj": cnpj.strip(),
                    "contato": contato.strip(),
                    "telefone": telefone.strip(),
                    "email": email.strip(),
                    "endereco": endereco.strip()
                }
            )

        st.success(f"Sucesso: Indústria '{nome}' homologada na plataforma!")
        st.rerun()