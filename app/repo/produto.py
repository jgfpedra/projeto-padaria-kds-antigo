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


def _preencher_descricoes(compostos: list[dict], nomes: dict[int, str]) -> None:
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


def _filtro_ativo_e_setor_por_loja():
    return """
        AND EXISTS (
            SELECT 1
            FROM produtocomplemento pc
            WHERE pc.id_produto = p.id
              AND pc.id_situacaocadastro = 1
              AND pc.id_loja = %s
        )
        AND EXISTS (
            SELECT 1
            FROM ficha.setorproduto sp
            INNER JOIN ficha.setor s
                ON s.id = sp.id_setor
            WHERE sp.id_produto = p.id
              AND s.id_loja = %s
        )
    """


def _sql_buscar_produto_por_id():
    return f"""
        SELECT
            p.id,
            p.descricaocompleta,
            p.pesoliquido
        FROM produto p
        WHERE p.id = %s
          {_filtro_ativo_e_setor_por_loja()}
        LIMIT %s
    """


def _sql_buscar_produtos_por_termo(n_palavras):
    condicoes = " AND ".join(["LOWER(p.descricaocompleta) LIKE %s"] * n_palavras)

    return f"""
        SELECT
            p.id,
            p.descricaocompleta,
            p.pesoliquido,
            CASE
                WHEN LOWER(p.descricaocompleta) = %s THEN 1
                WHEN LOWER(p.descricaocompleta) LIKE %s THEN 2
                ELSE 3
            END AS prioridade
        FROM produto p
        WHERE {condicoes}
          {_filtro_ativo_e_setor_por_loja()}
        ORDER BY
            prioridade,
            p.descricaocompleta
        LIMIT %s
    """


def _mapear_produto(row):
    return {
        "id": row[0],
        "descricaocompleta": row[1],
        "peso_unitario_kg": row[2],
    }


def repo_get_precos_produtos(ids, id_loja):
    """Retorna {id_produto: preco_venda} para a loja."""
    if not ids:
        return {}
    conn = None
    try:
        conn = conectar_vr()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id_produto, precovenda
            FROM produtocomplemento
            WHERE id_loja = %s AND id_produto = ANY(%s)
            """,
            (id_loja, list(ids)),
        )
        return {r[0]: float(r[1] or 0) for r in cur.fetchall()}
    except Exception as e:
        logger.error(f"[PRECOS_PRODUTOS] {e}")
        return {}
    finally:
        if conn:
            conn.close()


def repo_vr_buscar_produtos(termo, id_loja, por_id=False, limite=20):
    termo = str(termo).strip()

    # só busca por id se realmente for numérico
    buscar_por_id = por_id and termo.isascii() and termo.isdigit()

    conn = conectar_vr()
    cursor = conn.cursor()

    try:
        if buscar_por_id:
            cursor.execute(
                _sql_buscar_produto_por_id(),
                (int(termo), id_loja, id_loja, limite),
            )
        else:
            termo = termo.lower()
            palavras = termo.split()

            if not palavras:
                return []

            sql = _sql_buscar_produtos_por_termo(len(palavras))

            params = [
                termo,
                f"{termo}%",
                *[f"%{p}%" for p in palavras],
                id_loja,
                id_loja,
                limite,
            ]

            cursor.execute(sql, tuple(params))

        return [_mapear_produto(row) for row in cursor.fetchall()]

    finally:
        cursor.close()
        conn.close()
