from app.utils.filtros import montar_filtros_pedidos


def marcar_pedido_impresso(cursor, conn, id_pedido):
    cursor.execute(
        """
        UPDATE pedidos
        SET impresso = true
        WHERE id = %s
    """,
        (id_pedido,),
    )

    conn.commit()


def buscar_pedido(cursor, id_pedido):
    cursor.execute(
        """
        SELECT
            id,
            id_cliente,
            id_loja,
            criado_em,
            data_entrega,
            hora_entrega,
            tipo_entrega,
            observacoes,
            id_status
        FROM pedidos
        WHERE id = %s
    """,
        (id_pedido,),
    )

    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": row[0],
        "id_cliente": row[1],
        "id_loja": row[2],
        "criado_em": row[3],
        "data_entrega": row[4],
        "hora_entrega": row[5],
        "tipo_entrega": row[6],
        "observacoes": row[7],
        "id_status": row[8],
    }


def buscar_pedidos(cursor, filtros):
    where, params = montar_filtros_pedidos(filtros)
    sql = f"""
        SELECT
            p.id,
            p.id_cliente,
            p.id_loja,
            p.criado_em,
            p.data_entrega,
            p.hora_entrega,
            p.tipo_entrega,
            p.observacoes,
            p.id_status,
            p.impresso,
            p.data_finalizacao
        FROM pedidos p
        WHERE {" AND ".join(where)}
        ORDER BY p.data_entrega ASC
    """

    cursor.execute(sql, tuple(params))
    return [
        {
            "id": row[0],
            "id_cliente": row[1],
            "id_loja": row[2],
            "criado_em": row[3],
            "data_entrega": row[4],
            "hora_entrega": row[5],
            "tipo_entrega": row[6],
            "observacoes": row[7],
            "id_status": row[8],
            "impresso": row[9],
            "data_finalizacao": row[10],
        }
        for row in cursor.fetchall()
    ]


def buscar_impressora(cursor, id_loja):
    cursor.execute(
        """
        SELECT caminho_impressora
        FROM impressora
        WHERE id_loja = %s
          AND id_setor IS NULL
        ORDER BY caminho_impressora ASC
        LIMIT 1
    """,
        (id_loja,),
    )

    row = cursor.fetchone()

    if not row or not row[0]:
        return None

    return row[0].strip()


def buscar_cliente(cursor, id_cliente):
    cursor.execute(
        """
        SELECT
            fc.nome,
            fct.telefone,
            CONCAT(
                fc.endereco,
                ', ',
                fc.numero,
                ', ',
                fc.bairro,
                ', ',
                m.descricao,
                ' - ',
                e.descricao
            ) AS endereco_completo
        FROM food.cliente fc
        LEFT JOIN food.clientetelefone fct
            ON fct.id_cliente = fc.id
        INNER JOIN public.municipio m
            ON m.id = fc.id_municipio
        INNER JOIN public.estado e
            ON e.id = m.id_estado
        WHERE fc.id = %s
        LIMIT 1
    """,
        (id_cliente,),
    )

    row = cursor.fetchone()

    if not row:
        return {"nome": "Cliente não encontrado",
                "telefone": "",
                "endereco": ""}

    return {"nome": row[0] or "",
            "telefone": row[1] or "",
            "endereco": row[2] or ""}


def buscar_nome_loja(cursor, id_loja):
    cursor.execute("SELECT descricao FROM loja WHERE id = %s", (id_loja,))

    row = cursor.fetchone()
    return row[0] if row else ""


def buscar_status(cursor, id_status):
    cursor.execute("SELECT descricao FROM status WHERE id = %s", (id_status,))

    row = cursor.fetchone()
    return row[0] if row else ""


def buscar_impresso(cursor, id_pedido):
    cursor.execute(
        "SELECT impresso FROM pedidos p WHERE p.id = %s", (id_pedido,))
    row = cursor.fetchone()
    return row[0] if row else ""


def buscar_valor_total(cursor, id_pedido):
    cursor.execute(
        """
        SELECT COALESCE(
            SUM(quantidade * valor_unitario),
            0
        )
        FROM pedido_itens
        WHERE id_pedido = %s
    """,
        (id_pedido,),
    )

    row = cursor.fetchone()

    return float(row[0]) if row else 0.0


def buscar_itens(cursor_app, cursor_vr, id_pedido):
    cursor_app.execute(
        """
        SELECT
            id_produto,
            quantidade,
            quantidade_un,
            observacao
        FROM pedido_itens
        WHERE id_pedido = %s
    """,
        (id_pedido,),
    )

    rows = cursor_app.fetchall()

    itens = []

    for row in rows:
        id_produto = row[0]

        cursor_vr.execute(
            """
            SELECT descricaocompleta
            FROM produto
            WHERE id = %s
        """,
            (id_produto,),
        )

        produto = cursor_vr.fetchone()

        descricao = produto[0] if produto else ""

        itens.append(
            {
                "descricao": descricao or "",
                "quantidade_un": row[2],
                "observacao": row[3] or "",
            }
        )

    itens.sort(key=lambda item: item["descricao"].casefold())

    return itens
