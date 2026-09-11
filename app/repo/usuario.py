from app.conexao_app import conectar_app


def consultar(filtro=""):
    conn = conectar_app()

    try:
        cur = conn.cursor()

        filtro = (filtro or "").strip()

        cur.execute(
            """
            SELECT
                id,
                nome,
                email,
                id_loja,
                cargo
            FROM usuarios
            WHERE
                %s = ''
                OR nome ILIKE %s
                OR email ILIKE %s
            ORDER BY nome
            """,
            (
                filtro,
                f"%{filtro}%",
                f"%{filtro}%",
            ),
        )

        rows = cur.fetchall()

        return [
            {
                "id": row[0],
                "nome": row[1],
                "email": row[2],
                "id_loja": row[3],
                "cargo": row[4],
            }
            for row in rows
        ]

    finally:
        conn.close()


def buscar_por_id(id_usuario):
    conn = conectar_app()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                id,
                nome,
                email,
                id_loja,
                cargo
            FROM usuarios
            WHERE id = %s
            """,
            (id_usuario,),
        )

        row = cur.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "nome": row[1],
            "email": row[2],
            "id_loja": row[3],
            "cargo": row[4],
        }

    finally:
        conn.close()


def inserir(nome, email, senha, id_loja, cargo=None):
    conn = conectar_app()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO usuarios (
                nome,
                email,
                senha,
                id_loja,
                cargo
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                nome,
                email,
                senha,
                id_loja,
                cargo,
            ),
        )

        id_usuario = cur.fetchone()[0]

        conn.commit()

        return id_usuario

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def atualizar(
    id_usuario,
    nome,
    email,
    id_loja,
    senha=None,
    cargo=None,
):
    conn = conectar_app()

    try:
        cur = conn.cursor()

        if senha:
            cur.execute(
                """
                UPDATE usuarios
                SET
                    nome = %s,
                    email = %s,
                    senha = %s,
                    id_loja = %s,
                    cargo = %s
                WHERE id = %s
                """,
                (
                    nome,
                    email,
                    senha,
                    id_loja,
                    cargo,
                    id_usuario,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE usuarios
                SET
                    nome = %s,
                    email = %s,
                    id_loja = %s,
                    cargo = %s
                WHERE id = %s
                """,
                (
                    nome,
                    email,
                    id_loja,
                    cargo,
                    id_usuario,
                ),
            )

        atualizado = cur.rowcount > 0

        conn.commit()

        return atualizado

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
