from datetime import date, timedelta
from io import BytesIO
import pandas as pd
from openpyxl import Workbook
from seguranca_caixa import validar_caixa_aberto
from services.compras import salvar_compra
from services.financeiro import registrar_movimentacao
from sqlalchemy import text
import streamlit as st

from database import engine
from menu import render_menu

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA (Deve ser o primeiro comando Streamlit)
# =====================================
st.set_page_config(page_title="Compras", page_icon="🛒", layout="wide")


# CSS Customizado
def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css()

# Controladores de Data
vencimento = date.today() + timedelta(days=30)

# =====================================
# 2. SEGURANÇA E VALIDAÇÕES INICIAIS
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

render_menu()

perfil = st.session_state["usuario"]["perfil"]
filial_id = st.session_state.get("filial_operacao")

if filial_id is None:
    st.warning("Selecione uma filial no menu lateral.")
    st.stop()

# Valida se o caixa está aberto antes de qualquer coisa
validar_caixa_aberto(filial_id)

if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

# =====================================
# 3. CARREGAMENTO DE DADOS (DB)
# =====================================
with engine.connect() as conn:
    filial_nome = conn.execute(
        text("SELECT nome FROM filiais WHERE id = :id"), {"id": filial_id}
    ).scalar()

    fornecedores = pd.read_sql(
        "SELECT id, nome FROM fornecedores ORDER BY nome", conn
    )
    materiais = pd.read_sql(
        "SELECT id, descricao FROM materiais ORDER BY descricao", conn
    )

st.title(f"📦 Compras - {filial_nome}")

# Gerador do Modelo Excel (Cache em memória)
wb = Workbook()
ws = wb.active
ws.append(["Fornecedor", "Material", "Quantidade", "Valor_KG"])
arquivo_mod = BytesIO()
wb.save(arquivo_mod)
excel_modelo = arquivo_mod.getvalue()


# =====================================
# 4. LOGICA DE NEGÓCIO / PROCESSAMENTO DE FORMULÁRIOS
# =====================================


def verificar_saldo_caixa(valor_necessario):
    with engine.connect() as conn:
        saldo_db = conn.execute(
            text(
                """
                SELECT COALESCE(saldo_disponivel,0) 
                FROM caixa 
                WHERE filial_id = :filial AND fechado_em IS NULL 
                LIMIT 1
            """
            ),
            {"filial": filial_id},
        ).scalar()
    saldo_float = float(saldo_db or 0)
    if valor_necessario > saldo_float:
        st.error(
            f"Saldo insuficiente.\n\nSaldo disponível: R$ {saldo_float:,.2f}\n\nValor necessário: R$ {valor_necessario:,.2f}"
        )
        st.stop()


# =====================================
# 5. ESTRUTURA DA INTERFACE (TABS)
# =====================================
tab_manual, tab_importacao, tab_historico = st.tabs(
    ["🛒 Compra Manual / Carrinho", "📥 Importar Planilha", "📋 Histórico"]
)

# -------------------------------------
# ABA 1: COMPRA MANUAL & CARRINHO
# -------------------------------------
with tab_manual:
    st.subheader("Fornecedor")
    tipo_fornecedor = st.radio(
        "Origem do Material",
        ["Fornecedor Cadastrado", "Fornecedor Avulso"],
        horizontal=True,
    )

    fornecedor_id = None
    fornecedor_avulso = None

    if tipo_fornecedor == "Fornecedor Cadastrado":
        if fornecedores.empty:
            st.warning("Cadastre um fornecedor primeiro.")
            st.stop()
        fornecedor_nome = st.selectbox(
            "Fornecedor", fornecedores["nome"].tolist()
        )
        fornecedor_id = int(
            fornecedores.loc[
                fornecedores["nome"] == fornecedor_nome, "id"
            ].iloc[0]
        )
    else:
        fornecedor_avulso = st.text_input("Fornecedor Avulso").strip()

    st.divider()
    st.subheader("Adicionar Item")

    if materiais.empty:
        st.warning("Cadastre materiais primeiro.")
    else:
        col1, col2, col3 = st.columns(3)

        with col1:
            material_nome = st.selectbox(
                "Material", materiais["descricao"].tolist()
            )
            material_id = int(
                materiais.loc[
                    materiais["descricao"] == material_nome, "id"
                ].iloc[0]
            )

        # Busca o preço base padrão configurado na tabela_preco_compra
        with engine.connect() as conn:
            preco_sugerido = conn.execute(
                text(
                    """
                    SELECT COALESCE(preco_compra, 0) 
                    FROM tabela_preco_compra 
                    WHERE material_id = :material_id AND filial_id = :filial_id
                """
                ),
                {"material_id": material_id, "filial_id": filial_id},
            ).scalar() or 0.0

        with col2:
            quantidade = st.number_input(
                "Peso (KG)", min_value=0.0, step=0.01, format="%.3f"
            )

        with col3:
            # O campo já vem preenchido com o valor do banco, mas aceita edição manual livremente
            valor_unitario = st.number_input(
                "Valor por KG (R$)",
                min_value=0.0,
                step=0.01,
                value=float(preco_sugerido),
                format="%.2f",
                help="Preço sugerido automaticamente pela tabela de preços da filial.",
            )

        valor_total_item = quantidade * valor_unitario

        # Resumo Dinâmico do Item Atual
        c1, c2, c3 = st.columns(3)
        c1.metric("Peso", f"{quantidade:.3f} KG")
        c2.metric("Preço/KG", f"R$ {valor_unitario:.2f}")
        c3.metric("Valor do Item", f"R$ {valor_total_item:.2f}")

        if st.button("➕ Adicionar Item", use_container_width=True):
            if quantidade <= 0:
                st.warning("Informe uma quantidade válida.")
                st.stop()
            if valor_unitario <= 0:
                st.warning("Informe um valor válido.")
                st.stop()

            st.session_state.carrinho.append(
                {
                    "material_id": int(material_id),
                    "material": material_nome,
                    "quantidade": float(quantidade),
                    "valor_unitario": float(valor_unitario),
                    "valor_total": float(valor_total_item),
                }
            )
            st.success(f"{material_nome} adicionado ao carrinho!")
            st.rerun()

    # Seção do Carrinho de Compras
    st.divider()
    st.subheader("🛒 Carrinho Corrente")

    if len(st.session_state.carrinho) == 0:
        st.info("Nenhum item adicionado.")
    else:
        df_carrinho = pd.DataFrame(st.session_state.carrinho)
        st.dataframe(
            df_carrinho[
                ["material", "quantidade", "valor_unitario", "valor_total"]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "material": "Material",
                "quantidade": st.column_config.NumberColumn(
                    "Quantidade (KG)", format="%.3f"
                ),
                "valor_unitario": st.column_config.NumberColumn(
                    "Valor/KG", format="R$ %.2f"
                ),
                "valor_total": st.column_config.NumberColumn(
                    "Total", format="R$ %.2f"
                ),
            },
        )

        total_itens = len(st.session_state.carrinho)
        total_kg = sum(item["quantidade"] for item in st.session_state.carrinho)
        total_geral = sum(
            item["valor_total"] for item in st.session_state.carrinho
        )

        cx1, cx2, cx3 = st.columns(3)
        cx1.metric("Itens", total_itens)
        cx2.metric("Peso Total", f"{total_kg:,.3f} KG")
        cx3.metric("Valor Total", f"R$ {total_geral:,.2f}")

        st.markdown(
            f'<div style="background-color:rgb(22, 163, 74); padding:20px; border-radius:12px; text-align:center; margin: 15px 0; color: white;"><h3>TOTAL DA COMPRA</h3><h1>💰 R$ {total_geral:.2f}</h1></div>',
            unsafe_allow_html=True,
        )

        observacao = st.text_area("Observação", key="obs_manual")

        # Remover Itens
        st.write("---")
        item_remover = st.selectbox(
            "Selecione um item para remover",
            range(len(st.session_state.carrinho)),
            format_func=lambda x: f"{st.session_state.carrinho[x]['material']} ({st.session_state.carrinho[x]['quantidade']:.3f} KG)",
            key="remover_item",
        )
        if st.button("🗑️ Remover Item Selecionado", use_container_width=True):
            st.session_state.carrinho.pop(item_remover)
            st.rerun()

        # Botão de Finalização Manual
        st.write("---")
        if st.button("💾 Finalizar Compra Manual", use_container_width=True):
            if (
                tipo_fornecedor == "Fornecedor Avulso"
                and not fornecedor_avulso
            ):
                st.warning("Informe o fornecedor avulso.")
                st.stop()

            verificar_saldo_caixa(total_geral)

            compra_id = salvar_compra(
                filial_id=filial_id,
                fornecedor_id=fornecedor_id,
                fornecedor_avulso=fornecedor_avulso,
                itens=st.session_state.carrinho,
                observacao=observacao,
                usuario_id=st.session_state["usuario"]["id"],
            )
            st.session_state.carrinho = []
            st.success(f"Compra #{compra_id} cadastrada com sucesso!")
            st.rerun()

# -------------------------------------
# ABA 2: IMPORTAÇÃO DE PLANILHA
# -------------------------------------
with tab_importacao:
    st.subheader("📥 Importação de Compras por Excel")

    with st.container(border=True):
        col_down, col_up = st.columns([1, 2], vertical_alignment="bottom")
        with col_down:
            st.download_button(
                "⬇️ Baixar Modelo Excel",
                data=excel_modelo,
                file_name="Modelo_Compras.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col_up:
            arquivo_upload = st.file_uploader(
                "Importar arquivo Excel", type=["xlsx"], key="uploader_excel"
            )

    if arquivo_upload is not None:
        try:
            df = pd.read_excel(arquivo_upload)
        except Exception:
            st.error("Não foi possível ler o arquivo Excel.")
            st.stop()

        st.success(f"{len(df)} itens encontrados no arquivo.")
        st.dataframe(df, use_container_width=True, hide_index=True)

        obrigatorias = ["Fornecedor", "Material", "Quantidade", "Valor_KG"]
        if not all(col in df.columns for col in obrigatorias):
            st.error(
                "O arquivo não corresponde ao modelo estrutural exigido."
            )
            st.stop()

        if st.button(
            "💾 Processar e Importar Planilha", use_container_width=True
        ):
            itens_importacao = []
            total_compra_importacao = 0
            fornecedor_nome = str(df.iloc[0]["Fornecedor"]).strip()

            with engine.begin() as conn:
                fornecedor_id_imp = conn.execute(
                    text(
                        "SELECT id FROM fornecedores WHERE UPPER(nome) LIKE UPPER(:nome) LIMIT 1"
                    ),
                    {"nome": f"%{fornecedor_nome}%"},
                ).scalar()

                fornecedor_avulso_imp = (
                    fornecedor_nome if fornecedor_id_imp is None else None
                )

                for indice, row in df.iterrows():
                    if str(row["Fornecedor"]).strip() != fornecedor_nome:
                        st.error(
                            f"Linha {indice+2}: Existe mais de um fornecedor na planilha."
                        )
                        st.stop()

                    material_nome_imp = str(row["Material"]).strip()
                    material_id_imp = conn.execute(
                        text(
                            "SELECT id FROM materiais WHERE UPPER(descricao)=UPPER(:descricao)"
                        ),
                        {"descricao": material_nome_imp},
                    ).scalar()

                    if material_id_imp is None:
                        st.error(
                            f"Linha {indice+2}: Material '{material_nome_imp}' não encontrado no cadastro."
                        )
                        st.stop()

                    qnt = float(row["Quantidade"])
                    v_uni = float(row["Valor_KG"])

                    if qnt <= 0 or v_uni <= 0:
                        st.error(
                            f"Linha {indice+2}: Valores de Quantidade ou Preço inválidos."
                        )
                        st.stop()

                    v_tot = qnt * v_uni
                    total_compra_importacao += v_tot

                    itens_importacao.append(
                        {
                            "material_id": int(material_id_imp),
                            "material": material_nome_imp,
                            "quantidade": qnt,
                            "valor_unitario": v_uni,
                            "valor_total": v_tot,
                        }
                    )

            verificar_saldo_caixa(total_compra_importacao)

            compra_id = salvar_compra(
                filial_id=filial_id,
                fornecedor_id=fornecedor_id_imp,
                fornecedor_avulso=fornecedor_avulso_imp,
                itens=itens_importacao,
                observacao="Importação via Planilha Excel",
                usuario_id=st.session_state["usuario"]["id"],
            )

            st.success(
                f"Compra #{compra_id} importada com sucesso via planilha!"
            )
            st.rerun()

# -------------------------------------
# ABA 3: HISTÓRICO DE COMPRAS
# -------------------------------------
with tab_historico:
    st.subheader("📋 Histórico de Compras Registradas")

    with engine.connect() as conn:
        historico = pd.read_sql(
            text(
                """
                SELECT 
                    c.id AS "Cód. Compra",
                    COALESCE(f.nome, c.fornecedor_avulso) AS "Fornecedor",
                    m.descricao AS "Material",
                    ic.quantidade AS "Quantidade (KG)",
                    ic.valor_unitario AS "Valor/KG",
                    ic.valor_total AS "Valor Total",
                    c.data_compra AS "Data Emissão"
                FROM compras c
                LEFT JOIN fornecedores f ON c.fornecedor_id = f.id
                INNER JOIN itens_compra ic ON c.id = ic.compra_id
                INNER JOIN materiais m ON ic.material_id = m.id
                WHERE c.filial_id = :filial_id
                ORDER BY c.id DESC
            """
                ),
                conn,
                params={"filial_id": filial_id},
            )

    if historico.empty:
        st.info("Nenhuma compra registrada para esta filial.")
    else:
        st.dataframe(
            historico,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Cód. Compra": st.column_config.NumberColumn(format="%d"),
                "Quantidade (KG)": st.column_config.NumberColumn(
                    format="%.3f"
                ),
                "Valor/KG": st.column_config.NumberColumn(format="R$ %.2f"),
                "Valor Total": st.column_config.NumberColumn(format="R$ %.2f"),
                "Data Emissão": st.column_config.DatetimeColumn(
                    format="DD/MM/YYYY HH:mm"
                ),
            },
        )