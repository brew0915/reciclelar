from sqlalchemy import text


def registrar_movimentacao(
    conn,
    filial_id,
    usuario_id,
    origem,
    referencia_id,
    tipo,
    descricao,
    valor,
    observacao=None
):

    entrada = valor if tipo == "ENTRADA" else 0
    saida = valor if tipo == "SAIDA" else 0

    conn.execute(
        text("""
            INSERT INTO movimentacao_financeira
            (
                filial_id,
                usuario_id,
                origem,
                referencia_id,
                tipo,
                descricao,
                entrada,
                saida,
                observacao
            )
            VALUES
            (
                :filial_id,
                :usuario_id,
                :origem,
                :referencia_id,
                :tipo,
                :descricao,
                :entrada,
                :saida,
                :observacao
            )
        """),
        {
            "filial_id": filial_id,
            "usuario_id": usuario_id,
            "origem": origem,
            "referencia_id": referencia_id,
            "tipo": tipo,
            "descricao": descricao,
            "entrada": entrada,
            "saida": saida,
            "observacao": observacao
        }
    )