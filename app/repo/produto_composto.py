import logging
from app.conexao_app import conectar_app
from app.conexao_vr import conectar_vr
from app.repo.produto import (
    repo_vr_get_nomes_produtos,
    _coletar_ids_produtos,
    _preencher_descricoes
)

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
            SELECT g.chave, g.quantidade_total, oi.id_produto, oi.quantidade
            FROM produto_composto_opcional_grupo g
            JOIN produto_composto_opcional_item oi ON oi.id_grupo = g.id
            WHERE g.id_produto_comp = %s
            ORDER BY g.chave
        """, (id_produto,))
        rows = cur.fetchall()
        grupos = {}
        for r in rows:
            grupos.setdefault(r[0], {"quantidade_total": r[1], "itens": []})
            grupos[r[0]]["itens"].append({"id_produto": r[2], "quantidade": r[3]})
        return grupos
    except Exception as e:
        logger.error(e)
        return False
    finally:
        conn.close()


def repo_get_quantidade_total_grupo(id_produto, chave):
    try:
        conn = conectar_app()
        cur = conn.cursor()
        cur.execute("""
            SELECT quantidade_total FROM produto_composto_opcional_grupo
            WHERE id_produto_comp = %s AND chave = %s
        """, (id_produto, chave))
        row = cur.fetchone()
        return float(row[0]) if row else 0
    except Exception as e:
        logger.error(e)
        return 0
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
            SELECT p.id, p.descricaocompleta, te.descricao,
                   p.pesoliquido, pc.precovenda,
                   s.id, s.descricao
            FROM produto p
            LEFT JOIN tipoembalagem te ON te.id = p.id_tipoembalagem
            LEFT JOIN produtocomplemento pc ON pc.id_produto = p.id
            AND pc.id_loja = %s
            LEFT JOIN ficha.setorproduto sp ON sp.id_produto = p.id
            LEFT JOIN ficha.setor s ON s.id = sp.id_setor AND s.id_loja = %s
            WHERE p.id = %s
            ORDER BY s.id_loja DESC NULLS LAST
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


def repo_buscar_produtos(termo: str, id_loja, limit: int = 10):
    try:
        conn_vr = conectar_vr()
        cur = conn_vr.cursor()
        cur.execute("""
                SELECT DISTINCT p.id, p.descricaocompleta
                FROM produto p
                JOIN produtocomplemento pc ON p.id = pc.id_produto
                WHERE
                    p.id::text ILIKE %s
                    OR p.descricaocompleta ILIKE %s
                AND pc.id_loja = %s
                AND pc.id_situacaocadastro = 1
                ORDER BY p.id
                LIMIT %s
            """, (f"%{termo}%", f"%{termo}%", id_loja, limit))
        rows = cur.fetchall()
        return [{"id": r[0], "nome": r[1]} for r in rows]
    except Exception as e:
        logger.error(e)
        return False


def repo_get_calculos_pessoa():
    try:
        conn_app = conectar_app()
        cur = conn_app.cursor()
        cur.execute("""
                SELECT *
                FROM produto_composto_calculo_pessoa
                ORDER BY id
            """)
        rows = cur.fetchall()
        return [{"id": r[0],
                 "bebida_ml": r[1],
                 "bolo_g": r[2],
                 "salgados_unid": r[3]} for r in rows]
    except Exception as e:
        logger.error(e)
        return False


def salvar_calculo(cur, calc):
    if not calc:
        return None
    try:
        if calc.get("id"):
            return calc["id"]
        cur.execute("""
            INSERT INTO produto_composto_calculo_pessoa
            (bebida_ml, bolo_g, salgados_unid)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (
            calc.get("bebida_ml"),
            calc.get("bolo_g"),
            calc.get("salgados_unid")
        ))
        return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"[CALCULO_PESSOA] {e}")
        raise


def salvar_produto(cur, id_produto, dados, id_calculo):
    try:
        cur.execute("""
            INSERT INTO produto_composto
                (id_produto, tipo, id_calculo_pessoa, pedido_min_pessoas)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id_produto) DO UPDATE SET
                tipo               = EXCLUDED.tipo,
                id_calculo_pessoa  = EXCLUDED.id_calculo_pessoa,
                pedido_min_pessoas = EXCLUDED.pedido_min_pessoas
        """, (
            id_produto,
            dados.get("tipo"),
            id_calculo,
            dados.get("pedido_min_pessoas")
        ))

    except Exception as e:
        logger.error(f"[PRODUTO_COMPOSTO] {e}")
        raise


def salvar_itens(cur, id_produto, itens):
    try:
        cur.execute("""
            DELETE FROM produto_composto_item
            WHERE id_produto_comp = %s
        """, (id_produto,))

        if not itens:
            return
        cur.executemany("""
            INSERT INTO produto_composto_item
                (id_produto_comp, id_produto,
                 quantidade, peso_unitario_kg,
                 tipo_item, capacidade_ml)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, [
            (
                id_produto,
                it["id_produto"],
                it.get("quantidade"),
                it.get("peso_unitario_kg"),
                it.get("tipo_item") or None,
                it.get("capacidade_ml") if it.get(
                    "tipo_item") == "bebida" else None,
            )
            for it in itens
        ])
    except Exception as e:
        logger.error(f"[ITENS] {e}")
        raise


def salvar_grupos(cur, id_produto, grupos):
    try:
        cur.execute("""
            DELETE FROM produto_composto_opcional_grupo
            WHERE id_produto_comp = %s
        """, (id_produto,))
        for grupo in grupos:
            cur.execute("""
                INSERT INTO produto_composto_opcional_grupo
                    (id_produto_comp, chave)
                VALUES (%s, %s)
                RETURNING id
            """, (id_produto, grupo["chave"]))

            id_grupo = cur.fetchone()[0]
            itens = grupo.get("itens")
            if itens:
                cur.executemany("""
                    INSERT INTO produto_composto_opcional_item
                        (id_grupo, id_produto, quantidade)
                    VALUES (%s, %s, %s)
                """, [
                    (id_grupo, it["id_produto"], it.get("quantidade"))
                    for it in itens
                ])
    except Exception as e:
        logger.error(f"[GRUPOS_OPCIONAIS] {e}")
        raise


def repo_salvar_produto_composto(dados: dict):
    try:
        with conectar_app.cursor() as cur:
            id_produto = dados["id_produto"]
            id_calculo = salvar_calculo(cur, dados.get("calculo_pessoa"))
            salvar_produto(cur, id_produto, dados, id_calculo)
            salvar_itens(cur, id_produto, dados.get("itens", []))
            salvar_grupos(cur, id_produto, dados.get("grupos_opcionais", []))
        return True
    except Exception as e:
        logger.error(f"[repo_salvar_produto_composto] {e}")
        return False


def repo_remover_produto_composto(id_produto: int):
    try:
        with conectar_app.cursor() as cur:
            cur.execute("""
                SELECT id_calculo_pessoa FROM produto_composto
                WHERE id_produto = %s
            """, (id_produto,))
            row = cur.fetchone()
            cur.execute("""
                DELETE FROM produto_composto WHERE id_produto = %s
            """, (id_produto,))
            if row and row[0]:
                cur.execute("""
                    SELECT COUNT(*) FROM produto_composto
                    WHERE id_calculo_pessoa = %s
                """, (row[0],))
                still_used = cur.fetchone()[0]
                if not still_used:
                    cur.execute("""
                        DELETE FROM produto_composto_calculo_pessoa
                        WHERE id = %s
                    """, (row[0],))
        return True
    except Exception as e:
        logger.error(e)
        return False


def repo_get_produtos_compostos():
    try:
        conn_app = conectar_app()
        cur = conn_app.cursor()
        cur.execute("""
                SELECT
                    pc.id_produto AS id,
                    pc.tipo,
                    pc.pedido_min_pessoas,
                    CASE
                        WHEN pcc.id IS NOT NULL THEN
                            json_build_object(
                                'bebida_ml', pcc.bebida_ml,
                                'bolo_g', pcc.bolo_g,
                                'salgados_unid', pcc.salgados_unid
                            )
                        ELSE NULL
                    END AS calculo_pessoa,
                    COALESCE(
                        (
                            SELECT json_agg(json_build_object(
                                'id_produto', pci.id_produto,
                                'quantidade', pci.quantidade,
                                'peso_unitario_kg', pci.peso_unitario_kg,
                                'tipo_item', pci.tipo_item,
                                'capacidade_ml', pci.capacidade_ml
                            ))
                            FROM produto_composto_item pci
                            WHERE pci.id_produto_comp = pc.id_produto
                        ),
                        '[]'::json
                    ) AS itens,
                    COALESCE(
                        (
                            SELECT json_agg(json_build_object(
                                'id', pog.id,
                                'chave', pog.chave,
                                'itens', COALESCE(
                                    (
                                        SELECT json_agg(json_build_object(
                                            'id_produto', poi.id_produto,
                                            'quantidade', poi.quantidade
                                        ))
                                        FROM produto_composto_opcional_item poi
                                        WHERE poi.id_grupo = pog.id
                                    ),
                                    '[]'::json
                                )
                            ))
                            FROM produto_composto_opcional_grupo pog
                            WHERE pog.id_produto_comp = pc.id_produto
                        ),
                        '[]'::json
                    ) AS grupos_opcionais
                FROM produto_composto pc
                LEFT JOIN produto_composto_calculo_pessoa pcc
                    ON pcc.id = pc.id_calculo_pessoa
                ORDER BY pc.id_produto;
            """)
        rows = cur.fetchall()

        compostos = [
            {
                "id": r[0],
                "tipo": r[1],
                "pedido_min_pessoas": r[2],
                "calculo_pessoa": r[3],
                "itens": r[4],
                "grupos_opcionais": r[5],
            }
            for r in rows
        ]

        if not compostos:
            return []
        ids = _coletar_ids_produtos(compostos)
        nomes = repo_vr_get_nomes_produtos(list(ids))
        _preencher_descricoes(compostos, nomes)
        return compostos
    except Exception as e:
        logger.error(e)
        return False
