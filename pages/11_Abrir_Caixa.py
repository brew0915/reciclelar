
import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date

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
    st.switch_page("pages/00_Login.py")
    st.stop()

render_menu()

filial_id = st.session_state.get(
    "filial_operacao"
)

if filial_id is None:

    st.error(
        "Selecione uma filial no menu lateral."
    )

    st.stop()

st.info(
f"Filial selecionada: {filial_id}"
)

# OPERADOR e CONSULTA ficam presos à própria filial

st.set_page_config(
    page_title="Abrir Caixa",
    page_icon="💵",
    layout="wide"
)

# ==========================
# CSS
# ==========================

def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )

carregar_css()



# ==========================
# TITULO FILIAL
# ==========================


with engine.connect() as conn:

    filial_nome = conn.execute(
        text("""
            SELECT nome
            FROM filiais
            WHERE id = :id
        """),
        {
            "id": filial_id
        }
    ).scalar()


# =====================================
# TÍTULO
# =====================================

st.title(
    f"📦 Abrir Caixa  {filial_nome}"
)

hoje = date.today()

# ==========================
# VERIFICAR CAIXA
# ==========================

with engine.connect() as conn:

       caixa_aberto = conn.execute(
        text("""
            SELECT
                id,
                saldo_inicial,
                observacao
            FROM caixa
            WHERE data_caixa = :data
            AND filial_id = :filial_id
        """),
        {
            "data": hoje,
            "filial_id": filial_id
        }
            ).fetchone()

# ==========================
# CAIXA JÁ ABERTO
# ==========================

if caixa_aberto:

    st.success(
        "Caixa já aberto para hoje."
    )

    ...
    
else:

    st.warning(
        "Nenhum caixa aberto para hoje."
    )

    with st.form("form_caixa"):

        saldo_inicial = st.number_input(
            "Saldo Inicial (R$)",
            min_value=0.0,
            step=10.0,
            value=0.0
        )

        observacao = st.text_area(
            "Observação"
        )

        abrir = st.form_submit_button(
            "🔓 Abrir Caixa"
        )

        if abrir:

            with engine.begin() as conn:

                conn.execute(
                    text("""
                        INSERT INTO caixa
                        (
                            data_caixa,
                            saldo_inicial,
                            observacao,
                            filial_id
                        )
                        VALUES
                        (
                            :data_caixa,
                            :saldo_inicial,
                            :observacao,
                            :filial_id
                        )
                    """),
                    {
                        "data_caixa": hoje,
                        "saldo_inicial": saldo_inicial,
                        "observacao": observacao,
                        "filial_id": filial_id
                    }
                )

            st.success(
                "Caixa aberto com sucesso!"
            )

            st.rerun()

# ==========================
# HISTÓRICO
# ==========================

st.divider()

st.subheader("📋 Histórico de Aberturas")

with engine.connect() as conn:

    historico = pd.read_sql(
        """
        SELECT
            data_caixa,
            saldo_inicial,
            observacao,
            criado_em
        FROM caixa
        ORDER BY data_caixa DESC
        LIMIT 30
        """,
        conn
    )

if historico.empty:

    st.info(
        "Nenhuma abertura registrada."
    )

else:

    st.dataframe(
        historico,
        use_container_width=True,
        hide_index=True
    )


st.divider()

st.subheader("🔓 Reabrir Caixa")

from datetime import date

data_reabertura = st.date_input(
    "Data do fechamento",
    value=date.today(),
    key="reabrir_data"
)

with engine.connect() as conn:

    existe_fechamento = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM fechamento_caixa
            WHERE filial_id = :filial_id
            AND data_fechamento = :data
        """),
        {
            "filial_id": filial_id,
            "data": data_reabertura
        }
    ).scalar()

    if existe_fechamento > 0:

        st.warning(
            "Existe um fechamento para esta data."
        )

        if st.button(
            "🔓 Reabrir Caixa",
            type="primary",
            use_container_width=True
        ):
            
            with engine.begin() as conn:

                conn.execute(
                    text("""
                        DELETE
                        FROM fechamento_caixa
                        WHERE filial_id = :filial_id
                        AND data_fechamento = :data
                    """),
                    {
                        "filial_id": filial_id,
                        "data": data_reabertura
                    }
                )


                conn.execute(
            text("""
                INSERT INTO auditoria
                (
                    usuario_id,
                    acao,
                    tabela,
                    registro_id
                )
                VALUES
                (
                    :usuario_id,
                    :acao,
                    :tabela,
                    :registro_id
                )
            """),
            {
                "usuario_id": st.session_state["usuario"]["id"],
                "acao": f"Reabriu caixa da filial {filial_id} em {data_reabertura}",
                "tabela": "fechamento_caixa",
                "registro_id": 0
            }
        )

            st.success(
                "Caixa reaberto com sucesso."
            )

            st.rerun()

            confirmar = st.checkbox(
                "Confirmo que desejo reabrir o caixa."
            )

            if confirmar:
                if st.button("🔓 Reabrir Caixa"):
                    ...