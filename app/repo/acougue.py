import logging
from app.conexao_app import conectar_app
from app.conexao_vr import conectar_vr

logger = logging.getLogger("repo.acougue")

STATUS_CANCELADO = 5


def repo_get_pendencias(id_cliente: int) -> list[tuple]:
    conn = conectar_app()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT ap.id, ap.id_produto, ap.id_pedido_criacao, ap.id_pedido_atual,
                   ap.total_pedido, ap.falta, ap.data
              FROM acougue_pendencias ap
              LEFT JOIN pedidos ped ON ped.id = ap.id_pedido_atual
             WHERE ap.id_cliente = %s
               AND ap.resolvido = FALSE
               AND ap.falta > 0
               AND (ap.id_pedido_atual IS NULL
                    OR ped.id_status = %s)
             ORDER BY ap.id
        """,
            (id_cliente, STATUS_CANCELADO),
        )
        return cursor.fetchall()
    except Exception as e:
        logger.error(e)
        return []
    finally:
        cursor.close()
        conn.close()


def repo_get_produtos_vr(ids_produto: list[int], id_loja: int) -> dict:
    if not ids_produto:
        return {}
    conn_vr = conectar_vr()
    cursor_vr = conn_vr.cursor()
    try:
        cursor_vr.execute(
            """
            SELECT DISTINCT ON (p.id)
                   p.id, p.descricaocompleta, p.pesoliquido,
                   te.descricao AS embalagem,
                   s.id, s.descricao,
                   pc.precovenda
              FROM produto p
              LEFT JOIN produtocomplemento pc ON pc.id_produto = p.id
                     AND pc.id_loja = %s
              LEFT JOIN tipoembalagem te ON te.id = pc.id_tipoembalagem
              LEFT JOIN ficha.setorproduto sp ON sp.id_produto = p.id
              LEFT JOIN ficha.setor s ON s.id = sp.id_setor
                     AND s.id_situacaocadastro = 1
                     AND s.id_loja = %s
             WHERE p.id = ANY(%s)
             ORDER BY p.id, s.id
        """,
            (id_loja, id_loja, list(ids_produto)),
        )
        result = {}
        for row in cursor_vr.fetchall():
            if row[0] not in result:
                result[row[0]] = {
                    "descricao": row[1],
                    "peso_unitario": float(row[2]) if row[2] else 0,
                    "preco_venda": float(row[6]),
                    "embalagem": row[3] or "",
                    "id_setor": row[4] or "",
                    "setor": row[5] or "",
                }
        return result
    except Exception as e:
        logger.error(e)
        return {}
    finally:
        cursor_vr.close()
        conn_vr.close()


def repo_get_setores_por_produto(ids_produto: list[int]) -> dict:
    if not ids_produto:
        return {}
    conn_vr = conectar_vr()
    cursor_vr = conn_vr.cursor()
    try:
        cursor_vr.execute(
            """
            SELECT sp.id_produto, s.id, s.descricao
              FROM ficha.setorproduto sp
              JOIN ficha.setor s ON s.id = sp.id_setor
             WHERE sp.id_produto = ANY(%s)
               AND s.id_situacaocadastro = 1
        """,
            (ids_produto,),
        )
        return {
            row[0]: {"id_setor": row[1], "setor": row[2]}
            for row in cursor_vr.fetchall()
        }
    except Exception as e:
        logger.error(e)
        return {}
    finally:
        cursor_vr.close()
        conn_vr.close()


def repo_inserir_pendencias(id_cliente: int, pendencias: list[dict]) -> None:
    conn = conectar_app()
    cursor = conn.cursor()
    try:
        for pen in pendencias:
            ids_pedido = [int(i) for i in (pen.get("ids_pedido") or [])]

            # 1) Fecha a(s) pendência(s) que foram absorvidas por este pedido
            if ids_pedido:
                cursor.execute(
                    """
                    UPDATE acougue_pendencias
                       SET resolvido = TRUE
                     WHERE id_cliente = %s
                       AND id_produto = %s
                       AND resolvido = FALSE
                       AND id_pedido_atual = ANY(%s)
                """,
                    (id_cliente, pen.get("id_produto"), ids_pedido),
                )

            # 2) Só cria a nova se ainda falta algo
            if float(pen.get("falta") or 0) > 0:
                cursor.execute(
                    """
                    INSERT INTO acougue_pendencias
                        (id_cliente, id_produto, id_pedido_criacao, total_pedido, falta, data)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """,
                    (
                        id_cliente,
                        pen.get("id_produto"),
                        pen.get("id_pedido_criacao"),
                        pen.get("total_pedido"),
                        pen.get("falta"),
                        pen.get("data"),
                    ),
                )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(e)
        raise
    finally:
        cursor.close()
        conn.close()


def repo_atualizar_falta(id_pendencia: int, enviado: float) -> None:
    conn = conectar_app()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            WITH alvo AS (
                SELECT CASE
                         WHEN o.resolvido = FALSE THEN o.id
                         ELSE COALESCE((
                             SELECT n.id FROM acougue_pendencias n
                              WHERE n.id_cliente = o.id_cliente
                                AND n.id_produto = o.id_produto
                                AND n.resolvido = FALSE
                              ORDER BY n.id DESC LIMIT 1
                         ), o.id)
                       END AS id
                  FROM acougue_pendencias o
                 WHERE o.id = %s
            )
            UPDATE acougue_pendencias p
               SET falta = GREATEST(p.falta - %s, 0),
                   resolvido = (p.resolvido OR p.falta - %s <= 0)
              FROM alvo
             WHERE p.id = alvo.id
        """,
            (id_pendencia, enviado, enviado),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(e)
        raise
    finally:
        cursor.close()
        conn.close()


def repo_vincular_pedido_atual(
    id_pedido: int, id_cliente: int, ids_produto: list[int]
) -> None:
    conn = conectar_app()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE acougue_pendencias
               SET id_pedido_atual = %s
             WHERE id IN (
                   SELECT ap.id
                     FROM acougue_pendencias ap
                     LEFT JOIN pedidos ped ON ped.id = ap.id_pedido_atual
                    WHERE ap.id_cliente = %s
                      AND ap.id_produto = ANY(%s)
                      AND ap.resolvido = FALSE
                      AND (ap.id_pedido_atual IS NULL
                           OR ap.id_pedido_atual = %s
                           OR ped.id_status = %s)
             )
        """,
            (id_pedido, id_cliente, ids_produto, id_pedido, STATUS_CANCELADO),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(e)
        raise
    finally:
        cursor.close()
        conn.close()
