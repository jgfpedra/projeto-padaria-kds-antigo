import logging

from app.conexao_vr import conectar_vr

logger = logging.getLogger("repo.produto")


def _coletar_ids_produtos(compostos: list[dict]) -> set[int]:
    """Junta os ids de produto que precisam de descrição:
    o próprio composto + itens + itens dos grupos opcionais."""
    ids_set = set()
    for c in compostos:
        ids_set.add(c["id"])
        for item in c["itens"] or []:
            ids_set.add(item["id_produto"])
        for grupo in c["grupos_opcionais"] or []:
            for item in grupo["itens"] or []:
                ids_set.add(item["id_produto"])
    return ids_set


def _preencher_descricoes(compostos: list[dict],
                          nomes: dict[int, str]) -> None:
    for c in compostos:
        c["nome_produto"] = nomes.get(c["id"], "—")

        for item in c["itens"] or []:
            item["descricao"] = nomes.get(item["id_produto"], "—")

        for grupo in c["grupos_opcionais"] or []:
            for item in grupo["itens"] or []:
                item["descricao"] = nomes.get(item["id_produto"], "—")


def repo_vr_get_nomes_produtos(ids: list[int]):
    if not ids:
        return {}
    try:
        conn = conectar_vr()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.id, p.descricaocompleta
            FROM produto p
            JOIN produtocomplemento pc ON pc.id_produto = p.id
            WHERE p.id = ANY(%s)
            AND pc.id_situacaocadastro = 1
        """,
            (ids,),
        )
        rows = cur.fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception as e:
        logger.error(e)
        return {}
    finally:
        conn.close()


def repo_vr_get_nome_produto(id_produto):
    if not id_produto:
        return None
    try:
        conn = conectar_vr()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.descricaocompleta
            FROM produto p
            JOIN produtocomplemento pc ON pc.id_produto = p.id
            WHERE p.id = %s
              AND pc.id_situacaocadastro = 1
            """,
            (id_produto,),
        )
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error(e)
        return False
    finally:
        conn.close()


def repo_vr_buscar_produtos(termo, por_id=False, limite=20):
    conn = conectar_vr()
    cursor = conn.cursor()

    try:
        if por_id:
            sql = """
                SELECT DISTINCT
                    p.id,
                    p.descricaocompleta,
                    p.pesoliquido
                FROM produto p
                INNER JOIN produtocomplemento pc
                    ON pc.id_produto = p.id
                WHERE pc.id_situacaocadastro = 1
                  AND p.id = %s
                LIMIT %s
            """

            cursor.execute(sql, (int(termo), limite))

        else:
            termo = termo.lower()
            termo_inicio = f"{termo}%"
            termo_contem = f"%{termo}%"

            sql = """
                SELECT DISTINCT
                    p.id,
                    p.descricaocompleta,
                    p.pesoliquido,
                    CASE
                        WHEN LOWER(p.descricaocompleta) = %s THEN 1
                        WHEN LOWER(p.descricaocompleta) LIKE %s THEN 2
                        ELSE 3
                    END AS prioridade
                FROM produto p
                INNER JOIN produtocomplemento pc
                    ON pc.id_produto = p.id
                WHERE pc.id_situacaocadastro = 1
                  AND LOWER(p.descricaocompleta) LIKE %s
                ORDER BY
                    prioridade,
                    p.descricaocompleta
                LIMIT %s
            """

            cursor.execute(
                sql,
                (
                    termo,
                    termo_inicio,
                    termo_contem,
                    limite,
                ),
            )

        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "descricaocompleta": row[1],
                "peso_unitario_kg": row[2],
            }
            for row in rows
        ]

    finally:
        cursor.close()
        conn.close()
