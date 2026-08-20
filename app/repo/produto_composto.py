import logging
from app.conexao_app import conectar_app
from app.conexao_vr import conectar_vr

logger = logging.getLogger("repo.produto_composto")


def repo_get_composto_estrutura(id_produto):
    try:
        conn = conectar_app()
        cur = conn.cursor()
        cur.execute("""
            SELECT pc.tipo, pc.id_calculo_pessoa, pc.pedido_min_pessoas,
                   cp.bebida_ml, cp.bolo_g, cp.salgados_unid
            FROM produto_composto pc
            LEFT JOIN produto_composto_calculo_pessoa cp ON
            cp.id = pc.id_calculo_pessoa
            WHERE pc.id_produto = %s
        """, (id_produto,))
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "tipo": row[0],
            "pedido_min_pessoas": row[2],
            "calculo_pessoa": {"bebida_ml": row[3],
                               "bolo_g": row[4],
                               "salgados_unid": row[5]} if row[1] else None,
        }
    except Exception as e:
        logger.error(e)
        return False
    finally:
        conn.close()


def repo_get_itens_fixos(id_produto):
    try:
        conn = conectar_app()
        cur = conn.cursor()
        cur.execute("""
            SELECT id_produto, quantidade,
            peso_unitario_kg, tipo_item, capacidade_ml
            FROM produto_composto_item
            WHERE id_produto_comp = %s
        """, (id_produto,))
        rows = cur.fetchall()
        return [{"id_produto": r[0],
                 "quantidade": r[1],
                 "peso_unitario_kg": r[2],
                 "tipo_item": r[3],
                 "capacidade_ml": r[4]} for r in rows]
    except Exception as e:
        logger.error(e)
        return False
    finally:
        conn.close()


def repo_get_grupos_opcionais(id_produto):
    try:
        conn = conectar_app()
        cur = conn.cursor()
        cur.execute("""
            SELECT g.chave, oi.id_produto, oi.quantidade
            FROM produto_composto_opcional_grupo g
            JOIN produto_composto_opcional_item oi ON oi.id_grupo = g.id
            WHERE g.id_produto_comp = %s
            ORDER BY g.chave
        """, (id_produto,))
        rows = cur.fetchall()
        grupos = {}
        for r in rows:
            grupos.setdefault(r[0], []).append(
                {"id_produto": r[1], "quantidade": r[2]})
        return grupos
    except Exception as e:
        logger.error(e)
        return False
    finally:
        conn.close()


def repo_get_opcionais_escolhidos(id_produto, chave, ids):
    try:
        conn = conectar_app()
        cur = conn.cursor()
        cur.execute("""
            SELECT oi.id_produto, oi.quantidade
            FROM produto_composto_opcional_item oi
            JOIN produto_composto_opcional_grupo g ON g.id = oi.id_grupo
            WHERE g.id_produto_comp = %s AND
            g.chave = %s AND oi.id_produto = ANY(%s)
        """, (id_produto, chave, ids))
        rows = cur.fetchall()
        return [{"id_produto": r[0], "quantidade": r[1]} for r in rows]
    except Exception as e:
        logger.error(e)
        return False
    finally:
        conn.close()


def repo_get_produto_detalhe(id_produto, id_loja):
    try:
        conn_vr = conectar_vr()
        cur = conn_vr.cursor()
        cur.execute("""
            SELECT p.id, p.descricaocompleta, p.tipoembalagem, p.pesoliquido,
                   pc.precovenda,
                   s.id, s.descricao
            FROM produto p
            LEFT JOIN produtocomplemento pc ON pc.id_produto = p.id
            AND pc.id_loja = %s
            LEFT JOIN ficha.setorproduto sp ON sp.id_produto = p.id
            LEFT JOIN ficha.setor s ON s.id = sp.id_setor AND s.id_loja = %s
            WHERE p.id = %s
            LIMIT 1
        """, (id_loja, id_loja, id_produto))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0], "descricao": row[1], "tipo_embalagem": row[2],
            "peso_liquido": row[3], "preco_venda": float(row[4] or 0),
            "id_setor": row[5], "setor": row[6],
        }
    except Exception as e:
        logger.error(e)
        return None
    finally:
        conn_vr.close()
