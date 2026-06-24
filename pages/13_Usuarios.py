import streamlit as st
import pandas as pd
import bcrypt
from sqlalchemy import text

from database import engine
from menu import render_menu

def carregar_css():

    with open(
        "assets/style.css",
        encoding="utf-8"
    ) as f:

        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )

carregar_css()

if "usuario" not in st.session_state:
    st.switch_page("pages/00_login.py")
    st.stop()

render_menu()

if st.session_state["usuario"]["perfil"] != "ADMIN":
    st.error("Acesso permitido apenas para administradores.")
    st.stop()

try:

    with engine.connect() as conn:

        filiais_df = pd.read_sql(
            """
            SELECT
                id,
                nome
            FROM filiais
            ORDER BY nome
            """,
            conn
        )

except Exception as e:

    st.error(f"Erro ao carregar filiais: {e}")
    st.stop()


# ==========================
# TÍTULO
# ==========================

st.title("👤 Cadastro de Usuários")

# ==========================
# FORMULÁRIO
# ==========================

with st.form("form_usuario"):

    nome = st.text_input("Nome")

    email = st.text_input("E-mail")

    senha = st.text_input(
        "Senha",
        type="password"
    )

    col1, col2 = st.columns(2)

    with col1:

        perfil_novo = st.selectbox(
            "Perfil",
            [
                "ADMIN",
                "OPERADOR",
                "CONSULTA"
            ]
        )

    with col2:

        filial_nome = st.selectbox(
            "Filial",
            filiais_df["nome"].tolist()
        )

    ativo = st.checkbox(
        "Usuário ativo",
        value=True
    )

    salvar = st.form_submit_button(
        "Salvar Usuário"
    )

# ==========================
# SALVAR
# ==========================

if salvar:

    if not nome.strip():
        st.warning("Informe o nome.")
        st.stop()

    if not email.strip():
        st.warning("Informe o e-mail.")
        st.stop()

    if not senha.strip():
        st.warning("Informe a senha.")
        st.stop()

    senha_hash = bcrypt.hashpw(
        senha.encode(),
        bcrypt.gensalt()
    ).decode()

    with engine.begin() as conn:

        existe = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM usuarios
                WHERE LOWER(email)=LOWER(:email)
            """),
            {
                "email": email
            }
        ).scalar()

        if existe > 0:

            st.error(
                "Já existe usuário com este e-mail."
            )

            st.stop()

        if perfil_novo == "ADMIN":

            filial_id = None

        else:

            filial_id = int(
                filiais_df.loc[
                    filiais_df["nome"] == filial_nome,
                    "id"
                ].iloc[0]
            )

        conn.execute(
            text("""
                INSERT INTO usuarios
                (
                    nome,
                    email,
                    senha,
                    perfil,
                    filial_id,
                    ativo
                )
                VALUES
                (
                    :nome,
                    :email,
                    :senha,
                    :perfil,
                    :filial_id,
                    :ativo
                )
            """),
            {
                "nome": nome,
                "email": email,
                "senha": senha_hash,
                "perfil": perfil_novo,
                "filial_id": filial_id,
                "ativo": ativo
            }
        )

    st.success(
        "Usuário criado com sucesso!"
    )

    st.rerun()

# ==========================
# LISTAGEM
# ==========================

st.divider()

st.subheader("Usuários cadastrados")

with engine.connect() as conn:

   usuarios = pd.read_sql(
    """
    SELECT
        u.id,
        u.nome,
        u.email,
        u.perfil,
        COALESCE(
            f.nome,
            'Todas'
        ) AS filial,
        u.ativo
    FROM usuarios u

    LEFT JOIN filiais f
        ON u.filial_id = f.id

    ORDER BY u.nome
    """,
    conn
)

if usuarios.empty:

    st.info(
        "Nenhum usuário cadastrado."
    )

else:

    for _, usuario in usuarios.iterrows():

        col1, col2, col3, col4, col5, col6, col7 = st.columns(
        [1, 3, 3, 2, 3, 1, 1]
        )

        with col1:
            st.write(usuario["id"])

        with col2:
            st.write(usuario["nome"])

        with col3:
            st.write(usuario["email"])

        with col4:
            st.write(usuario["perfil"])

        with col5:
            st.write(usuario["filial"])

        with col6:
            if usuario["ativo"]:
                st.success("Ativo")
            else:
                st.error("Inativo")

        with col7:

            if st.button(
                "🔄",
                key=f"toggle_{usuario['id']}"
            ):

                with engine.begin() as conn:

                    conn.execute(
                        text("""
                            UPDATE usuarios
                            SET ativo = NOT ativo
                            WHERE id = :id
                        """),
                        {
                            "id": int(usuario["id"])
                        }
                    )

                st.rerun()

# ==========================
# ALTERAR SENHA
# ==========================

st.divider()

st.subheader("🔑 Alterar Senha")

usuario_alterar = st.selectbox(
    "Usuário",
    usuarios["email"].tolist()
    if not usuarios.empty
    else []
)

nova_senha = st.text_input(
    "Nova senha",
    type="password"
)

if st.button("Atualizar Senha"):

    if usuario_alterar and nova_senha:

        nova_hash = bcrypt.hashpw(
            nova_senha.encode(),
            bcrypt.gensalt()
        ).decode()

        with engine.begin() as conn:

            conn.execute(
                text("""
                    UPDATE usuarios
                    SET senha = :senha
                    WHERE email = :email
                """),
                {
                    "senha": nova_hash,
                    "email": usuario_alterar
                }
            )

        st.success(
            "Senha atualizada com sucesso!"
        )

        st.rerun()

        st.divider()

with st.expander("✏️ Editar Usuário"):

    usuario_email = st.selectbox(
        "Usuário",
        usuarios["email"].tolist(),
        key="editar_usuario"
    )

    novo_perfil = st.selectbox(
        "Novo Perfil",
        [
            "ADMIN",
            "OPERADOR",
            "CONSULTA"
        ],
        key="novo_perfil"
    )

    nova_filial = st.selectbox(
        "Nova Filial",
        filiais_df["nome"].tolist(),
        key="nova_filial"
    )

    if st.button(
        "Salvar Alterações",
        use_container_width=True
    ):

        if novo_perfil == "ADMIN":

            filial_id = None

        else:

            filial_id = int(
                filiais_df.loc[
                    filiais_df["nome"] == nova_filial,
                    "id"
                ].iloc[0]
            )

        with engine.begin() as conn:

            conn.execute(
                text("""
                    UPDATE usuarios
                    SET
                        perfil = :perfil,
                        filial_id = :filial_id
                    WHERE email = :email
                """),
                {
                    "perfil": novo_perfil,
                    "filial_id": filial_id,
                    "email": usuario_email
                }
            )

        st.success(
            "✅ Usuário atualizado com sucesso!"
        )

        st.rerun()