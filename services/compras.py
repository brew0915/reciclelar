from datetime import date, timedelta
from sqlalchemy import text

from database import engine
from services.teste_financeiro import criar_conta_pagar
from services.estoque import entrada_estoque
from services.auditoria import registrar_auditoria
from services.financeiro import registrar_movimentacao


def salvar_compra(
    filial_id: int,
    fornecedor_id: int | None,
    fornecedor_avulso: str |None,
    itens: list,
    observacao: str,
    usuario_id: int
):

    valor_total_compra = sum(
        item["quantidade"] * item["valor_unitario"]
        for item in itens
    )

    with engine.begin() as conn:

        # ===============================
        # VALIDA SALDO DO CAIXA
        # ===============================

        saldo = conn.execute(
            text("""
                SELECT COALESCE(saldo_disponivel,0)
                FROM caixa
                WHERE filial_id=:filial
                AND fechado_em IS NULL
                LIMIT 1
            """),
            {
                "filial": filial_id
            }
        ).scalar()

        saldo = float(saldo or 0)

        if valor_total_compra > saldo:

            raise Exception(
                f"Saldo insuficiente. Saldo disponível: R$ {saldo:,.2f}"
            )

        # ===============================
        # COMPRA
        # ===============================

        compra_id = conn.execute(
            text("""
                INSERT INTO compras
                (
                    filial_id,
                    fornecedor_id,
                    fornecedor_avulso,
                    data_compra,
                    observacao
                )
                VALUES
                (
                    :filial_id,
                    :fornecedor_id,
                    :fornecedor_avulso,
                    CURRENT_DATE,
                    :observacao
                )
                RETURNING id
            """),
            {
                "filial_id": filial_id,
                "fornecedor_id": fornecedor_id,
                "fornecedor_avulso": fornecedor_avulso,
                "observacao": observacao
            }
        ).scalar()

        categoria_financeira_id = conn.execute(
            text("""
                SELECT id
                FROM categorias_financeiras
                WHERE descricao='Compra de Material'
            """)
        ).scalar()

        vencimento = date.today() + timedelta(days=30)

        # ===============================
        # ITENS
        # ===============================

        for item in itens:

            valor_total_item = (
                item["quantidade"] *
                item["valor_unitario"]
            )

            conn.execute(
                text("""
                    INSERT INTO itens_compra
                    (
                        compra_id,
                        material_id,
                        quantidade,
                        valor_unitario,
                        valor_total
                    )
                    VALUES
                    (
                        :compra_id,
                        :material_id,
                        :quantidade,
                        :valor_unitario,
                        :valor_total
                    )
                """),
                {
                    "compra_id": compra_id,
                    "material_id": item["material_id"],
                    "quantidade": item["quantidade"],
                    "valor_unitario": item["valor_unitario"],
                    "valor_total": valor_total_item
                }
            )

            entrada_estoque(
                filial_id=filial_id,
                material_id=item["material_id"],
                quantidade=item["quantidade"],
                referencia_id=compra_id,
                origem="COMPRA",
                conn=conn
            )

        # ===============================
        # UMA CONTA A PAGAR
        # ===============================

        criar_conta_pagar(
            filial_id=filial_id,
            fornecedor_id=fornecedor_id,
            categoria_id=categoria_financeira_id,
            compra_id=compra_id,
            descricao=f"Compra nº {compra_id}",
            valor=valor_total_compra,
            vencimento=vencimento,
            observacao=observacao,
            usuario_id=usuario_id,
            conn=conn
        )

        # ===============================
        # MOVIMENTAÇÃO FINANCEIRA
        # ===============================

        registrar_movimentacao(
            conn=conn,
            filial_id=filial_id,
            usuario_id=usuario_id,
            origem="COMPRA",
            referencia_id=compra_id,
            tipo="SAIDA",
            descricao=f"Compra nº {compra_id}",
            valor=valor_total_compra,
            observacao=observacao
        )

        # ===============================
        # ATUALIZA SALDO DO CAIXA
        # ===============================

        conn.execute(
            text("""
                UPDATE caixa
                SET saldo_disponivel =
                    saldo_disponivel - :valor
                WHERE filial_id=:filial
                AND fechado_em IS NULL
            """),
            {
                "valor": valor_total_compra,
                "filial": filial_id
            }
        )

        # ===============================
        # AUDITORIA
        # ===============================

        registrar_auditoria(
            usuario_id=usuario_id,
            acao=f"Cadastrou compra #{compra_id}",
            tabela="compras",
            registro_id=compra_id,
            conn=conn
        )

        return compra_id