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
        return {"nome": "Cliente não encontrado", "telefone": "", "endereco": ""}

    return {"nome": row[0] or "", "telefone": row[1] or "", "endereco": row[2] or ""}


def buscar_nome_loja(cursor, id_loja):
    cursor.execute("SELECT descricao FROM loja WHERE id = %s", (id_loja,))

    row = cursor.fetchone()
    return row[0] if row else ""


def buscar_status(cursor, id_status):
    cursor.execute("SELECT descricao FROM status WHERE id = %s", (id_status,))

    row = cursor.fetchone()
    return row[0] if row else ""


def buscar_impresso(cursor, id_pedido):
    cursor.execute("SELECT impresso FROM pedidos p WHERE p.id = %s", (id_pedido,))
    row = cursor.fetchone()
    return row[0] if row else ""


def buscar_pago(cursor, id_pedido):
    cursor.execute("SELECT pago FROM pedidos p WHERE p.id = %s", (id_pedido,))
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
                "quantidade_un": row[2] or 0,
                "observacao": row[3] or "",
                "quantidade": row[1] or 0,
            }
        )

    itens.sort(key=lambda item: item["descricao"].casefold())
    return itens


def buscar_cabecalho(cur, id_pedido):
    cur.execute("SELECT id_loja, id_cliente FROM pedidos WHERE id = %s", (id_pedido,))
    return cur.fetchone()


def buscar_operador(cur, id_pedido):
    cur.execute("""SELECT p.id_operador, u.nome FROM pedidos p
                JOIN usuarios u ON u.id = p.id_operador
                WHERE p.id = %s""", (id_pedido,))
    return cur.fetchone()


def buscar_observacoes(cur, id_pedido):
    cur.execute(
        """SELECT id_produto,
        COALESCE(observacao,'')
        FROM pedido_itens WHERE id_pedido = %s""",
        (id_pedido,),
    )
    obs = {}
    for pid, o in cur.fetchall():
        obs.setdefault(str(pid), o)
    return obs


def substituir_itens(cur, id_pedido, itens):
    """itens: lista de dicts já normalizados (ver services)."""
    cur.execute("DELETE FROM pedido_itens WHERE id_pedido = %s", (id_pedido,))
    for it in itens:
        cur.execute(
            """
    INSERT INTO pedido_itens
        (id_pedido, id_produto, id_setor, quantidade, quantidade_un,
         peso, valor_unitario, observacao, id_produto_associado, id_status)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """,
            (id_pedido, it["cod_produto"], it["id_setor"] or 0, it["quantidade"],
             it["quantidade_un"], it.get("peso_bruto") or 0, it["valor_unitario"],
                it["observacao"], it.get("cod_produto_associado") or None,
                it.get("id_status", 0)),
        )


def buscar_itens_finalizacao(cur, id_pedido):
    cur.execute(
        """
        SELECT id_produto, quantidade, valor_unitario,
               COALESCE(observacao,''), id_setor
          FROM pedido_itens WHERE id_pedido = %s
         ORDER BY id
        """,
        (id_pedido,),
    )
    return cur.fetchall()


def marcar_finalizado(cur, id_pedido, tipo):
    cur.execute(
        """
        UPDATE pedidos
           SET id_status = 7, data_finalizacao = NOW(), tipo_finalizacao = %s
         WHERE id = %s
        """,
        (tipo, id_pedido),
    )


def proximo_id_venda(cur):
    cur.execute("LOCK TABLE food.venda IN EXCLUSIVE MODE")
    cur.execute("SELECT COALESCE(MAX(id),0) FROM food.venda")
    return (cur.fetchone()[0] or 0) + 1


def inserir_venda(cur, id_venda, id_loja, id_cliente, codigo):
    cur.execute(
        """
        INSERT INTO food.venda (
            id, id_loja, id_cliente, id_tipopagamento, datahora, tempoentrega,
            troco, desconto, entrega, id_usuario, importado, id_situacaovenda,
            codigo, id_ifood, json, isretirada, dataretirada, horaretirada,
            id_entregador, id_vendedor
        ) VALUES (
            %s, %s, %s, 3, NOW(), '00:00:00',
            0, 0, 0, 0, FALSE, 0,
            %s, NULL, NULL, FALSE, NULL, NULL,
            NULL, NULL
        )
        """,
        (id_venda, id_loja, id_cliente, codigo),
    )


def inserir_item(cur, id_venda, it):
    cur.execute(
        """
        INSERT INTO food.vendaitem
            (id, id_venda, id_produto, quantidade, precovenda,
             valortotal, observacao, id_setor)
        VALUES (nextval('food.vendaitem_id_seq'), %s, %s, %s, %s, %s, %s, %s)
        """,
        (id_venda, it["id_produto"], it["quantidade"], it["precovenda"],
         it["valortotal"], it["observacao"], it["id_setor"]),
    )


def buscar_ficha(cur, numero_ficha, id_loja):
    cur.execute(
        "SELECT id FROM pdv.ficha WHERE numeroficha = %s AND id_loja = %s",
        (numero_ficha, id_loja),
    )
    row = cur.fetchone()
    return row[0] if row else None


def atualizar_ficha(cur, id_ficha, numero_ficha):
    cur.execute(
        """
        UPDATE pdv.ficha
           SET data = CURRENT_DATE, datahora = NOW(), numeroficha = %s
         WHERE id = %s
        """,
        (numero_ficha, id_ficha),
    )


def remover_itens(cur, id_ficha):
    cur.execute("DELETE FROM pdv.fichaitem WHERE id_ficha = %s", (id_ficha,))


def inserir_ficha(cur, id_loja, numero_ficha):
    cur.execute("SELECT nextval('ficha.ficha_id_seq')")
    id_ficha = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO pdv.ficha (id, id_loja,
        numeroficha, data, datahora, id_mesa, cliente)
        VALUES (%s, %s, %s, CURRENT_DATE, NOW(), %s, %s)
        """,
        (id_ficha, id_loja, numero_ficha, 1, None),
    )
    return id_ficha


def buscar_codigobarras(cur, id_produto):
    cur.execute(
        "SELECT codigobarras FROM produtoautomacao WHERE id_produto = %s LIMIT 1",
        (id_produto,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def inserir_item_ficha(cur, id_ficha, sequencia, codigobarras, quantidade, preco):
    cur.execute("SELECT nextval('ficha.fichaitem_id_seq')")
    id_fichaitem = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO pdv.fichaitem (
            id, id_ficha, sequencia, codigobarras, quantidade,
            precovenda, id_atendente, iscancelado, isimpresso
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (id_fichaitem, id_ficha, sequencia,
         codigobarras, quantidade, preco, -1, False, False),
    )
