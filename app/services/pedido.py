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


def adicionar_cabecalho(linhas, pedido, cliente, nome_loja, status):
    linhas.append(f"Pedido #{pedido['id']}")

    linhas.append(f"Loja: {normalize_text(nome_loja)}")

    linhas.append(f"Cliente: {normalize_text(cliente['nome'])}")

    linhas.append(f"Telefone: {normalize_text(cliente['telefone'])}")

    if status:
        linhas.append(f"Status: {normalize_text(status)}")


def adicionar_entrega(linhas, pedido):
    data_entrega = br_date(pedido["data_entrega"])

    hora_entrega = br_time(pedido["hora_entrega"])

    linhas.append(f"Tipo Entrega: {normalize_text(pedido['tipo_entrega'])}")

    linhas.append(f"Data Entrega: {data_entrega} - {hora_entrega}")


def adicionar_observacoes(linhas, observacoes):
    if not observacoes:
        return

    linhas.append("")
    linhas.append("Observações do Pedido:")

    for linha in str(observacoes).splitlines():
        linha = linha.strip()

        if linha:
            linhas.append(normalize_text(linha))


def adicionar_produtos(linhas, itens):
    linhas.append("")
    linhas.append("Produtos (ordem alfabética):")

    for item in itens:
        linha = f"{item['quantidade_un']} un - " f"{normalize_text(item['descricao'])}"

        if item["observacao"]:
            linha += f" ({normalize_text(item['observacao'])})"

        linhas.append(linha)
