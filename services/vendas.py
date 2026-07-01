from sqlalchemy import text

from database import engine
from services.estoque import saida_estoque
from services.teste_financeiro import criar_conta_receber
from services.auditoria import registrar_auditoria


def salvar_venda(
    filial_id: int,
    industria_id: int,
    material_id: int,
    quantidade: float,
    valor_unitario: float,
    categoria_financeira_id: int,
    vencimento,
    observacao: str,
    usuario_id: int,
    pagamento: str = "PRAZO"
):

    valor_total = quantidade * valor_unitario

    with engine.begin() as conn:

        venda_id = conn.execute(
            text("""
                INSERT INTO vendas
                (
                    filial_id,
                    industria_id,
                    material_id,
                    quantidade,
                    valor_unitario,
                    valor_total,
                    data_venda,
                    observacao,
                    usuario_id
                )
                VALUES
                (
                    :filial_id,
                    :industria_id,
                    :material_id,
                    :quantidade,
                    :valor_unitario,
                    :valor_total,
                    CURRENT_DATE,
                    :observacao,
                    :usuario_id
                )
                RETURNING id
            """),
            {
                "filial_id": filial_id,
                "industria_id": industria_id,
                "material_id": material_id,
                "quantidade": quantidade,
                "valor_unitario": valor_unitario,
                "valor_total": valor_total,
                "observacao": observacao,
                "usuario_id": usuario_id
            }
        ).scalar()

        # Baixa estoque
        saida_estoque(
            filial_id=filial_id,
            material_id=material_id,
            quantidade=quantidade,
            referencia_id=venda_id,
            origem="VENDA",
            conn=conn
        )

        # Cria a conta a receber
        criar_conta_receber(
            filial_id=filial_id,
            industria_id=industria_id,
            categoria_id=categoria_financeira_id,
            venda_id=venda_id,
            descricao=f"Venda nº {venda_id}",
            valor=valor_total,
            vencimento=vencimento,
            observacao=observacao,
            usuario_id=usuario_id,
            conn=conn
        )


        if pagamento == "AVISTA":

            conn.execute(
                text("""
                    UPDATE contas_receber
                    SET
                        status = 'RECEBIDO',
                        saldo = 0,
                        data_recebimento = CURRENT_DATE
                    WHERE venda_id = :venda
                """),
                {
                    "venda": venda_id
                }
            )

            conn.execute(
                text("""
                    UPDATE caixa
                    SET saldo_disponivel =
                        saldo_disponivel + :valor
                    WHERE filial_id = :filial
                    AND fechado_em IS NULL
                """),
                {
                    "valor": valor_total,
                    "filial": filial_id
                }
            )

        # Auditoria
        registrar_auditoria(
            usuario_id=usuario_id,
            acao=f"Cadastrou venda #{venda_id}",
            tabela="vendas",
            registro_id=venda_id,
            conn=conn
        )

        

    return venda_id

