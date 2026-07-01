from io import BytesIO
import pandas as pd
from openpyxl import Workbook
from sqlalchemy import text
import streamlit as st

from database import engine
from menu import render_menu

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA & CSS
# =====================================
st.set_page_config(page_title="Tabela de Preços", page_icon="💲", layout="wide")


def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css()

# =====================================
# 2. SEGURANÇA E CONTEXTO
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

render_menu()

filial_id = st.session_state.get("filial_operacao")
if filial_id is None:
    st.error("Selecione uma filial no menu lateral para gerenciar os preços.")
    st.stop()

st.title("💲 Gestão de Tabela de Preços Base (Compra)")

# =====================================
# 3. SINCRO DE NOVOS ITENS E CARGA DATA
# =====================================
with engine.begin() as conn:
    # Garante que todo material cadastrado tenha uma linha para esta filial
    conn.execute(
        text(
            """
            INSERT INTO tabela_preco_compra (filial_id, material_id, preco_compra)
            SELECT :filial, m.id, 0
            FROM materiais m
            WHERE NOT EXISTS (
                SELECT 1 
                FROM tabela_preco_compra tp 
                WHERE tp.material_id = m.id AND tp.filial_id = :filial
            )
        """
        ),
        {"filial": filial_id},
    )

    # Carga dos dados atuais
    df_atual = pd.read_sql(
        text(
            """
            SELECT 
                tp.id AS id_registro,
                m.descricao AS material,
                tp.preco_compra AS preco_kg
            FROM tabela_preco_compra tp
            INNER JOIN materiais m ON m.id = tp.material_id
            WHERE tp.filial_id = :filial
            ORDER BY m.descricao
        """
        ),
        conn,
        params={"filial": filial_id},
    )

# =====================================
# 4. CRIAÇÃO DAS ABAS GERENCIAIS
# =====================================
tab_em_tela, tab_lote = st.tabs(
    ["📝 Ajuste em Tela", "📊 Importar / Exportar em Lote (Excel)"]
)

# -------------------------------------
# ABA 1: AJUSTE EM TELA (CÓDIGO ANTERIOR OTIMIZADO)
# -------------------------------------
with tab_em_tela:
    st.subheader("Configuração de Preços Manual")

    df_editado = st.data_editor(
        df_atual,
        hide_index=True,
        use_container_width=True,
        disabled=["id_registro", "material"],
        key="editor_precos_manual",
        column_config={
            "id_registro": None,
            "material": st.column_config.TextColumn("Material Cadastrado"),
            "preco_kg": st.column_config.NumberColumn(
                "Preço Base (R$/KG)", min_value=0.0, step=0.01, format="R$ %.2f"
            ),
        },
    )

    if st.button("💾 Salvar Alterações Manuais", use_container_width=True):
        alteracoes = st.session_state.editor_precos_manual.get(
            "edited_rows", {}
        )

        if not alteracoes:
            st.info("Nenhuma modificação manual detectada.")
            st.stop()

        with engine.begin() as conn:
            for index, mudanca in alteracoes.items():
                id_registro = int(df_atual.iloc[int(index)]["id_registro"])
                if "preco_kg" in mudanca:
                    conn.execute(
                        text(
                            """
                            UPDATE tabela_preco_compra
                            SET preco_compra = :preco, atualizado_em = CURRENT_TIMESTAMP, usuario_id = :usuario
                            WHERE id = :id
                        """
                        ),
                        {
                            "preco": float(mudanca["preco_kg"]),
                            "usuario": st.session_state["usuario"]["id"],
                            "id": id_registro,
                        },
                    )
        st.success("Preços atualizados!")
        st.rerun()


# -------------------------------------
# ABA 2: PROCESSAMENTO EM LOTE (EXCEL)
# -------------------------------------
with tab_lote:
    st.subheader("📥 Atualização Massiva de Preços")
    st.write(
        "Baixe a tabela atual da filial, altere os valores na coluna **preco_kg** usando o Excel e envie o arquivo modificado de volta."
    )

    # --- GERADOR DE TEMPLATE DINÂMICO COM DADOS DO BANCO ---
    # Criamos o arquivo em memória para garantir que o Excel gerado contenha os IDs reais do banco de dados
    wb = Workbook()
    ws = wb.active
    ws.title = "Tabela Preços"

    # Cabeçalho idêntico ao esperado no Upload
    ws.append(["id_registro", "material", "preco_kg"])

    # Popula com os dados reais atuais para facilitar o trabalho do usuário
    for _, row in df_atual.iterrows():
        ws.append([row["id_registro"], row["material"], row["preco_kg"]])

    arquivo_memoria = BytesIO()
    wb.save(arquivo_memoria)
    excel_dinamico = arquivo_memoria.getvalue()

    # --- INTERFACE DE DOWNLOAD / UPLOAD ---
    with st.container(border=True):
        col_down, col_up = st.columns([1, 2], vertical_alignment="bottom")

        with col_down:
            st.download_button(
                label="⬇️ Baixar Tabela Atual (Excel)",
                data=excel_dinamico,
                file_name=f"Tabela_Precos_Filial_{filial_id}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        with col_up:
            arquivo_lote = st.file_uploader(
                "Carregar Planilha com Novos Preços",
                type=["xlsx"],
                key="uploader_lote_precos",
            )

    # --- PROCESSAMENTO DO UPLOAD ---
    if arquivo_lote is not None:
        try:
            df_lote = pd.read_excel(arquivo_lote)
        except Exception:
            st.error("Falha ao ler o arquivo Excel inserido.")
            st.stop()

        # Validação de Estrutura Básica
        colunas_obrigatorias = ["id_registro", "material", "preco_kg"]
        if not all(col in df_lote.columns for col in colunas_obrigatorias):
            st.error(
                "A planilha enviada não possui a estrutura correta (id_registro, material, preco_kg)."
            )
            st.stop()

        st.info(f"Planilha carregada com sucesso: {len(df_lote)} itens prontos para validação.")
        st.dataframe(
            df_lote,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id_registro": st.column_config.NumberColumn(format="%d"),
                "preco_kg": st.column_config.NumberColumn(format="R$ %.2f"),
            },
        )

        if st.button("⚡ Aplicar Atualização em Lote", use_container_width=True):
            linhas_atualizadas = 0

            try:
                with engine.begin() as conn:
                    for _, row in df_lote.iterrows():
                        # Validação simples para evitar valores nulos ou corrompidos na planilha
                        if pd.isna(row["id_registro"]) or pd.isna(
                            row["preco_kg"]
                        ):
                            continue

                        id_reg = int(row["id_registro"])
                        novo_preco = float(row["preco_kg"])

                        if novo_preco < 0:
                            st.error(
                                f"Erro: Preço negativo detectado para o material '{row['material']}'."
                            )
                            st.stop()

                        # Executa o update rápido usando a chave primária da tabela de preços
                        conn.execute(
                            text(
                                """
                                UPDATE tabela_preco_compra
                                SET 
                                    preco_compra = :preco,
                                    atualizado_em = CURRENT_TIMESTAMP,
                                    usuario_id = :usuario
                                WHERE id = :id AND filial_id = :filial
                            """
                            ),
                            {
                                "preco": novo_preco,
                                "usuario": st.session_state["usuario"]["id"],
                                "id": id_reg,
                                "filial": filial_id,
                            },
                        )
                        linhas_atualizadas += 1

                st.success(
                    f"Sucesso! {linhas_atualizadas} preços foram atualizados em lote para esta filial."
                )
                st.rerun()

            except Exception as e:
                st.error(f"Erro ao processar o banco de dados: {e}")