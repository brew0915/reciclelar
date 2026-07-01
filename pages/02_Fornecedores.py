import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import engine
from menu import render_menu

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA (Sempre o primeiro comando)
# =====================================
st.set_page_config(
    page_title="Gestão de Fornecedores | Supply Chain",
    page_icon="👥",
    layout="wide"
)

def carregar_css():
    try:
        with open("assets/style.css", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

carregar_css()

if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()
    
render_menu()

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
# 2. INTERFACE CORPORATIVA (TABS)
# =====================================
st.title("👥 Central de Fornecedores")
st.caption("Homologação, triagem e consulta analítica de parceiros e fornecedores integrados à rede.")

tab_consulta, tab_cadastro = st.tabs(["🔎 Consultar Carteira", "➕ Homologar Fornecedor"])

# -------------------------------------
# ABA 1: CONSULTA E MANUTENÇÃO
# -------------------------------------
with tab_consulta:
    col_busca, _ = st.columns([2, 2])
    with col_busca:
        busca = st.text_input("Filtrar por Nome ou Razão Social", placeholder="Digite o nome para pesquisar...")

    with engine.connect() as conn:
        df = pd.read_sql(
            """
            SELECT id AS "ID", nome AS "Nome / Razão Social", tipo AS "Tipo", 
                   documento AS "CPF/CNPJ", telefone AS "Telefone", 
                   email AS "E-mail", endereco AS "Endereço", observacoes AS "Observações"
            FROM fornecedores
            ORDER BY nome
            """,
            conn
        )

    if busca:
        df = df[df["Nome / Razão Social"].str.contains(busca, case=False, na=False)]

    if df.empty:
        st.info("Nenhum fornecedor registrado atende aos critérios informados.")
    else:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn(format="%d", width="small"),
                "Tipo": st.column_config.TextColumn(width="medium"),
                "E-mail": st.column_config.LinkColumn(),
                "Endereço": st.column_config.TextColumn(width="medium"),
                "Observações": st.column_config.TextColumn(width="large")
            }
        )

        # Seção de Descredenciamento / Moderação Segura
        st.markdown("---")
        with st.expander("⚠️ Área de Descredenciamento de Fornecedor"):
            st.markdown("<small>A exclusão removerá o registro de forma definitiva. Transações financeiras históricas associadas não serão deletadas, mas o vínculo cadastral será corrompido.</small>", unsafe_allow_html=True)
            fornecedor_para_excluir = st.selectbox(
                "Selecione o parceiro para remoção",
                options=df["Nome / Razão Social"].tolist(),
                index=None,
                placeholder="Escolha o fornecedor..."
            )

            if fornecedor_para_excluir:
                id_alvo = df[df["Nome / Razão Social"] == fornecedor_para_excluir]["ID"].values[0]
                st.warning(f"Confirma a remoção permanente de '{fornecedor_para_excluir}'?")
                
                col_c1, col_c2, _ = st.columns([1, 1, 2])
                with col_c1:
                    if st.button("✅ Confirmar Exclusão", use_container_width=True, type="primary"):
                        with engine.begin() as conn:
                            conn.execute(
                                text("DELETE FROM fornecedores WHERE id = :id"),
                                {"id": int(id_alvo)}
                            )
                        st.success("Fornecedor removido com sucesso!")
                        st.rerun()
                with col_c2:
                    if st.button("❌ Cancelar Operação", use_container_width=True):
                        st.rerun()

# -------------------------------------
# ABA 2: FORMULÁRIO DE CADASTRO
# -------------------------------------
with tab_cadastro:
    st.markdown("### Formulário de Homologação Cadastral")
    
    with st.form("form_fornecedor", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            nome = st.text_input("Nome / Razão Social", placeholder="Ex: Cooperativa AgroRecicla")
            tipo = st.selectbox("Classificação Jurídica / Perfil", ["Pessoa", "Condomínio", "Empresa", "Cooperativa"])
            documento = st.text_input("Documento de Identificação (CPF/CNPJ)", placeholder="Apenas números ou formato padrão")
            telefone = st.text_input("Telefone de Contato", placeholder="(00) 00000-0000")
            
        with col_f2:
            email = st.text_input("E-mail Comercial / Financeiro", placeholder="contato@fornecedor.com")
            endereco = st.text_area("Endereço Completo", placeholder="Logradouro, Nº, Bairro, Cidade - UF", height=68)
            observacoes = st.text_area("Notas e Condições Comerciais", placeholder="Prazos de entrega acordados, restrições ou dados bancários para PIX...", height=68)

        st.markdown("<br>", unsafe_allow_html=True)
        salvar = st.form_submit_button("Concluir Cadastro Comercial", type="primary")

    if salvar:
        if not nome.strip():
            st.error("Erro na validação: O campo 'Nome / Razão Social' é de preenchimento obrigatório.")
            st.stop()

        with engine.begin() as conn:
            # Validação de Duplicidade Preventiva
            existe = conn.execute(
                text("SELECT COUNT(*) FROM fornecedores WHERE UPPER(nome) = UPPER(:nome)"),
                {"nome": nome.strip()}
            ).scalar()

            if existe > 0:
                st.error("Conflito detectado: Um fornecedor com este mesmo nome já está ativo no banco de dados.")
                st.stop()

            # Execução do Insert Em Bloco Protegido
            conn.execute(
                text("""
                    INSERT INTO fornecedores (nome, tipo, documento, telefone, email, endereco, observacoes)
                    VALUES (:nome, :tipo, :documento, :telefone, :email, :endereco, :observacoes)
                """),
                {
                    "nome": nome.strip(),
                    "tipo": tipo,
                    "documento": documento.strip(),
                    "telefone": telefone.strip(),
                    "email": email.strip(),
                    "endereco": endereco.strip(),
                    "observacoes": observacoes.strip()
                }
            )

        st.success(f"Parceiro comercial '{nome}' registrado com sucesso!")
        st.rerun()