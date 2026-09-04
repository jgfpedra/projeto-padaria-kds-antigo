from app.conexao_app import conectar_app


def salvar(id_loja, id_setor, caminho):
    conn = conectar_app()

    try:
        cur = conn.cursor()

        if id_setor is None:
            # Impressora padrão da loja
            cur.execute(
                """
                INSERT INTO impressora (
                    id_loja,
                    id_setor,
                    caminho_impressora
                )
                VALUES (%s, NULL, %s)
                ON CONFLICT (id_loja)
                WHERE id_setor IS NULL
                DO UPDATE SET
                    caminho_impressora = EXCLUDED.caminho_impressora
                """,
                (id_loja, caminho),
            )

        else:
            # Impressora específica do setor
            cur.execute(
                """
                INSERT INTO impressora (
                    id_loja,
                    id_setor,
                    caminho_impressora
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (id_loja, id_setor)
                WHERE id_setor IS NOT NULL
                DO UPDATE SET
                    caminho_impressora = EXCLUDED.caminho_impressora
                """,
                (id_loja, id_setor, caminho),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
