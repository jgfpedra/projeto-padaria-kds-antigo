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
