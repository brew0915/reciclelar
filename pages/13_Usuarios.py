from database import engine
from menu import render_menu
import bcrypt
import pandas as pd
from sqlalchemy import text
import streamlit as st

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA (Sempre o primeiro comando)
# =====================================
st.set_page_config(
    page_title="Gestão de Identidades (IAM)", page_icon="👤", layout="wide"
)


def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css()

# =====================================
# 2. SEGURANÇA E GOVERNANÇA DE ACESSO
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_login.py")
    st.stop()

if st.session_state["usuario"]["perfil"] != "ADMIN":
    st.error("Acesso restrito. Esta página requer privilégios de Administrador.")
    st.stop()

render_menu()

# Carregamento de metadados das filiais para os seletores
try:
    with engine.connect() as conn:
        filiais_df = pd.read_sql(
            text("SELECT id, nome FROM filiais ORDER BY nome"), conn
        )
except Exception as e:
    st.error(f"Falha de infraestrutura ao carregar metadados: {e}")
    st.stop()

# =====================================
# 3. CABEÇALHO DA INTERFACE
# =====================================
st.title("👤 Controle de Identidades e Níveis de Acesso")
st.caption("Módulo de Governança de Usuários e Segurança da Informação")
st.write(" ")

# Divisão por Abas Corporativas
tab_lista, tab_cadastro, tab_seguranca = st.tabs(
    ["📋 Usuários Cadastrados", "➕ Provisionar Novo Usuário", "🔑 Políticas de Segurança"]
)

# =====================================
# TAB 1: LISTAGEM E EDIÇÃO EM MALHA (DATA EDITOR)
# =====================================
with tab_lista:
    with engine.connect() as conn:
        usuarios = pd.read_sql(
            text(
                """
                SELECT 
                    u.id AS "ID",
                    u.nome AS "Colaborador",
                    u.email AS "E-mail Corporativo",
                    u.perfil AS "Perfil de Acesso",
                    COALESCE(f.nome, 'Todas as Unidades') AS "Escopo Filial",
                    u.ativo AS "Status Ativo"
                FROM usuarios u
                LEFT JOIN filiais f ON u.filial_id = f.id
                ORDER BY u.nome
            """
            ),
            conn,
        )

    if usuarios.empty:
        st.info("Nenhum registro de usuário ativo localizado.")
    else:
        st.subheader("Diretório de Contas Ativas")
        st.caption("Dica: Altere diretamente o status de ativação na tabela abaixo.")
        
        # Grid interativo substituindo o loop manual de colunas
        usuarios_editados = st.data_editor(
            usuarios,
            use_container_width=True,
            hide_index=True,
            disabled=["ID", "Colaborador", "E-mail Corporativo", "Perfil de Acesso", "Escopo Filial"],
            column_config={
                "Status Ativo": st.column_config.CheckboxColumn(help="Ativar/Desativar acesso da conta de forma instantânea")
            },
            key="grid_usuarios"
        )
        
        # Processamento de alterações inline na tabela
        if st.session_state.get("grid_usuarios") and st.session_state["grid_usuarios"]["edited_rows"]:
            alteracoes = st.session_state["grid_usuarios"]["edited_rows"]
            with engine.begin() as conn:
                for idx, mudanca in alteracoes.items():
                    if "Status Ativo" in mudanca:
                        user_id = int(usuarios.iloc[idx]["ID"])
                        novo_status = mudanca["Status Ativo"]
                        conn.execute(
                            text("UPDATE usuarios SET ativo = :status WHERE id = :id"),
                            {"status": novo_status, "id": user_id}
                        )
            st.success("Alterações de privilégios e acessos sincronizadas com sucesso.")
            st.rerun()

# =====================================
# TAB 2: PROVISIONAMENTO DE CONTAS
# =====================================
with tab_cadastro:
    st.subheader("Formulário de Provisionamento de Credenciais")
    
    with st.form("form_usuario", clear_on_submit=True):
        col_dados1, col_dados2 = st.columns(2)
        
        with col_dados1:
            nome = st.text_input("Nome Completo", placeholder="Ex: João Silva")
            email = st.text_input("E-mail Corporativo", placeholder="nome.sobrenome@empresa.com")
            senha = st.text_input("Senha Provisória", type="password")
            
        with col_dados2:
            perfil_novo = st.selectbox("Perfil de Acesso (RBAC)", ["ADMIN", "OPERADOR", "CONSULTA"])
            filial_nome = st.selectbox("Escopo Operacional da Filial", filiais_df["nome"].tolist())
            ativo = st.checkbox("Liberar acesso imediatamente", value=True)
            
        st.write(" ")
        salvar = st.form_submit_button("Confirmar Provisionamento", use_container_width=True)

    if salvar:
        if not nome.strip() or not email.strip() or not senha.strip():
            st.error("Campos mandatórios ausentes. Certifique-se de preencher Nome, E-mail e Senha.")
            st.stop()

        senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

        with engine.begin() as conn:
            existe = conn.execute(
                text("SELECT COUNT(*) FROM usuarios WHERE LOWER(email) = LOWER(:email)"),
                {"email": email}
            ).scalar()

            if existe > 0:
                st.error("Inconsistência cadastral: O e-mail informado já encontra-se vinculado a outro colaborador.")
                st.stop()

            filial_id = (
                None if perfil_novo == "ADMIN"
                else int(filiais_df.loc[filiais_df["nome"] == filial_nome, "id"].iloc[0])
            )

            conn.execute(
                text("""
                    INSERT INTO usuarios (nome, email, senha, perfil, filial_id, ativo)
                    VALUES (:nome, :email, :senha, :perfil, :filial_id, :ativo)
                """),
                {"nome": nome, "email": email, "senha": senha_hash, "perfil": perfil_novo, "filial_id": filial_id, "ativo": ativo}
            )
            
        st.success(f"Conta corporativa para '{nome}' provisionada no sistema.")
        st.rerun()

# =====================================
# TAB 3: SENHAS E ALTERAÇÕES ESTRUTURAIS
# =====================================
with tab_seguranca:
    if usuarios.empty:
        st.info("Nenhum usuário disponível para redefinição.")
    else:
        col_pwd, col_edt = st.columns(2)
        
        # Bloco A: Reset de Senhas (Compliance)
        with col_pwd:
            with st.container(border=True):
                st.subheader("🔑 Forçar Redefinição de Credencial")
                usuario_alterar = st.selectbox("Identificação do Colaborador", usuarios["E-mail Corporativo"].tolist(), key="sb_pwd")
                nova_senha = st.text_input("Nova Senha Operacional", type="password", key="ti_pwd")
                
                if st.button("Gravar Nova Senha", use_container_width=True):
                    if usuario_alterar and nova_senha:
                        nova_hash = bcrypt.hashpw(nova_senha.encode(), bcrypt.gensalt()).decode()
                        with engine.begin() as conn:
                            conn.execute(
                                text("UPDATE usuarios SET senha = :senha WHERE email = :email"),
                                {"senha": nova_hash, "email": usuario_alterar}
                            )
                        st.success("Nova credencial de segurança criptografada e salva.")
                        st.rerun()
        
        # Bloco B: Modificação de Perfil de Governança
        with col_edt:
            with st.container(border=True):
                st.subheader("✏️ Alterar Escopo / Perfil Existente")
                usuario_email = st.selectbox("Identificação do Colaborador", usuarios["E-mail Corporativo"].tolist(), key="sb_edt")
                novo_perfil = st.selectbox("Novo Nível Hierárquico", ["ADMIN", "OPERADOR", "CONSULTA"], key="sb_perf")
                nova_filial = st.selectbox("Nova Unidade de Atuação", filiais_df["nome"].tolist(), key="sb_fil")
                
                if st.button("Modificar Escopo", use_container_width=True):
                    filial_id = (
                        None if novo_perfil == "ADMIN"
                        else int(filiais_df.loc[filiais_df["nome"] == nova_filial, "id"].iloc[0])
                    )
                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                UPDATE usuarios 
                                SET perfil = :perfil, filial_id = :filial_id
                                WHERE email = :email
                            """),
                            {"perfil": novo_perfil, "filial_id": filial_id, "email": usuario_email}
                        )
                    st.success("Matriz de permissões atualizada com sucesso.")
                    st.rerun()