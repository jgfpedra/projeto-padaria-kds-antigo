# app/api_routes.py

import logging

from flask import (
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
)

from app import app, bcrypt
from app.conexao_app import conectar_app
from app.conexao_vr import buscar_clientes, conectar_vr, fechar_conexao
from app.repo.produto_composto import (
    repo_get_composto_estrutura,
    repo_get_grupos_opcionais,
    repo_get_itens_fixos,
    repo_get_produto_detalhe,
)
from app.services.produto import adicionar_nomes_produtos, buscar_produtos
from app.services.usuario import (
    consultar_usuarios,
    buscar_usuario,
    criar_usuario,
    editar_usuario,
)
from app.services.produto_composto import (
    calcular_componentes,
    montar_itens,
    svc_get_calculos_pessoa,
    svc_get_produtos_compostos,
    svc_remover_produtos_compostos,
    svc_salvar_produtos_compostos,
)
from app.services.impressora import (
    salvar_impressora_setor
)
from app.repo.pedido import (
    buscar_nome_loja,
    buscar_pedido,
    buscar_itens,
    buscar_status,
    buscar_cliente,
    buscar_impressora,
    buscar_valor_total,
)
from app.services.pedido import montar_texto_pedido, consultar_encomendas
from app.repo.pedido import (
    marcar_pedido_impresso,
)
from app.repo.produto import repo_vr_get_nomes_produtos, repo_vr_get_nome_produto
from app.utils.conversions import to_float, to_decimal
from app.utils.printer import (
    gerar_dados_impressao,
    enviar_para_impressora,
)

logger = logging.getLogger("api.api_routes")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory("assets", "favicon.svg", mimetype="image/svg+xml")


@app.route("/api/clientes")
def api_clientes():
    try:
        clientes = buscar_clientes()
        clientes_formatados = []
        for c in clientes:
            clientes_formatados.append(
                {
                    "id": c[0],
                    "nome": c[1],
                    "telefone": c[2],
                    "endereco": f"{c[3]}, {c[4]} - {c[5]}",
                    "observacao": c[6],
                    "cidade": c[7],
                    "estado": c[8],
                }
            )
        return jsonify(clientes_formatados)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/produtos")
def api_produtos():
    try:
        somente_ativos = request.args.get("ativos") in ("1", "true", "True")
        id_loja = request.args.get("id_loja", type=int)

        conn = conectar_vr()
        cur = conn.cursor()

        sql = """
            SELECT DISTINCT
                p.id                           AS id_produto,
                p.descricaocompleta,
                p.pesoliquido,
                te.descricao                   AS tipoembalagem,
                s.descricao                    AS setor
            FROM produto p
            LEFT JOIN tipoembalagem te      ON te.id = p.id_tipoembalagem
            LEFT JOIN ficha.setorproduto sp ON sp.id_produto = p.id
            LEFT JOIN ficha.setor s         ON s.id = sp.id_setor
        """

        params = []
        where = []

        if somente_ativos or id_loja:
            sql += """
                INNER JOIN produtocomplemento pc
                    ON pc.id_produto = p.id
            """

        if somente_ativos:
            where.append("pc.id_situacaocadastro = 1")

        if id_loja:
            where.append("pc.id_loja = %s")
            where.append("s.id_loja = %s")
            params.append(id_loja)
            params.append(id_loja)

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += " ORDER BY p.descricaocompleta"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        produtos_formatados = [
            {
                "id_produto": r[0],
                "descricaocompleta": r[1],
                "pesobruto": r[2],
                "tipoembalagem": r[3],
                "setor": r[4],
            }
            for r in rows
        ]

        return jsonify(produtos_formatados)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.route("/api/lojas")
def api_lojas():
    conn = conectar_vr()
    if not conn:
        return jsonify([])

    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT id, descricao FROM loja
                       WHERE id_situacaocadastro = 1 ORDER BY descricao""")
        rows = cursor.fetchall()
        return jsonify([{"id": r[0], "descricao": r[1]} for r in rows])
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/pedido/salvar", methods=["POST"])
def salvar_pedido():
    data = request.get_json()
    conn = conectar_app()
    if not conn:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500
    try:
        cursor = conn.cursor()
        id_pedido = data.get("id_pedido")
        novo_pedido = False
        if id_pedido:
            cursor.execute(
                """SELECT id FROM pedidos
                           WHERE id = %s""",
                (id_pedido,),
            )
            pedido_existente = cursor.fetchone()
            if pedido_existente:
                # Atualiza pedido existente
                cursor.execute(
                    """
                    UPDATE pedidos SET
                        id_cliente = %s,
                        id_loja = %s,
                        data_entrega = %s,
                        hora_entrega = %s,
                        telefone = %s,
                        observacoes = %s,
                        tipo_entrega = %s
                    WHERE id = %s
                """,
                    (
                        data["id_cliente"],
                        data["id_loja"],
                        data["data_entrega"],
                        data["hora_entrega"],
                        data["telefone"],
                        data["observacoes"],
                        data["tipo_entrega"],
                        id_pedido,
                    ),
                )
                cursor.execute("""DELETE FROM pedido_itens
                               WHERE id_pedido = %s""", (id_pedido,))
            else:
                novo_pedido = True
        else:
            novo_pedido = True
        if novo_pedido:
            cursor.execute(
                """
                INSERT INTO pedidos (id_cliente, id_loja, data_entrega,
                hora_entrega, telefone, observacoes, tipo_entrega, id_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """,
                (
                    data["id_cliente"],
                    data["id_loja"],
                    data["data_entrega"],
                    data["hora_entrega"],
                    data["telefone"],
                    data["observacoes"],
                    data["tipo_entrega"],
                    data.get("id_status", None),
                ),
            )
            id_pedido = cursor.fetchone()[0]
        for item in data["itens"]:
            preco_venda_raw = item.get("valor_unitario", 0)
            if isinstance(preco_venda_raw, str):
                if preco_venda_raw:
                    preco_venda_raw = to_float(preco_venda_raw)
                else:
                    preco_venda_raw = 0
            else:
                preco_venda = float(preco_venda_raw)
            if item.get("peso_bruto"):
                peso_bruto = to_float(item.get("peso_bruto"))
            else:
                peso_bruto = 0
            quantidade_raw = item.get("quantidade")
            if quantidade_raw:
                quantidade = to_float(quantidade_raw)
            else:
                quantidade = 0
            if item.get("quantidade"):
                quantidade_un = to_float(item.get("quantidade_un"))
            else:
                quantidade_un = 0
            if item.get("id_setor"):
                id_setor = int(item.get("id_setor", 0))
            else:
                id_setor = 0

            cursor.execute(
                """
                INSERT INTO pedido_itens (
                    id_pedido, id_produto, id_setor, quantidade,
                    quantidade_un, peso, valor_unitario, observacao,
                    id_produto_associado, id_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    id_pedido,
                    item.get("cod_produto"),
                    id_setor,
                    quantidade,
                    quantidade_un,
                    peso_bruto,
                    preco_venda,
                    item.get("observacao"),
                    item.get("cod_produto_associado") or None,
                    0,
                ),
            )

        conn.commit()
        return jsonify({"success": True})

    except Exception as e:
        conn.rollback()
        return jsonify({"erro": str(e)}), 500

    finally:
        conn.close()


@app.route("/api/preco/<int:id_produto>/<int:id_loja>")
def api_preco_produto(id_produto, id_loja):
    try:
        conn = conectar_vr()
        cursor = conn.cursor()

        # Buscar preco_venda
        cursor.execute(
            """
            SELECT precovenda
            FROM produtocomplemento
            WHERE id_produto = %s AND id_loja = %s
            LIMIT 1
        """,
            (id_produto, id_loja),
        )
        preco_row = cursor.fetchone()

        if preco_row:
            if preco_row[0] is not None:
                preco_venda = float(preco_row[0])
            else:
                preco_venda = 0
        else:
            preco_venda = 0

        cursor.execute(
            """
            SELECT s.id, s.descricao
            FROM ficha.setorproduto sp
            INNER JOIN ficha.setor s ON s.id = sp.id_setor
            WHERE sp.id_produto = %s
            AND s.id_loja = %s
            LIMIT 1
        """,
            (id_produto, id_loja),
        )
        setor_row = cursor.fetchone()

        if setor_row:
            id_setor = setor_row[0]
            descricao_setor = setor_row[1]
        else:
            id_setor = None
            descricao_setor = ""

        return jsonify(
            {
                "precovenda": preco_venda,
                "id_setor": id_setor,
                "descricao_setor": descricao_setor,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/pedido/<int:id>", methods=["GET"])
def buscar_pedido_edicao(id):
    conn_app = conectar_app()  # Banco de encomendas
    conn_vr = conectar_vr()  # Banco da VR

    if not conn_app or not conn_vr:
        return jsonify({"erro": "Erro de conexão"}), 500

    try:
        cursor_app = conn_app.cursor()
        cursor_vr = conn_vr.cursor()

        # Buscar dados do pedido (agora incluindo id_status)
        cursor_app.execute(
            """
            SELECT id_cliente, id_loja,
            data_entrega, hora_entrega,
            telefone, observacoes, tipo_entrega, id_status
            FROM pedidos
            WHERE id = %s
        """,
            (id,),
        )
        pedido_row = cursor_app.fetchone()

        if not pedido_row:
            return jsonify({"erro": "Pedido não encontrado"}), 404

        id_cliente = pedido_row[0]
        id_loja = pedido_row[1]

        # Buscar dados do cliente
        cursor_vr.execute(
            """
            SELECT
                fc.nome,
                fct.telefone,
                CONCAT(fc.endereco,
                ', ', fc.numero,
                ', ', fc.bairro,
                ', ', m.descricao,
                ' - ', e.descricao)
                AS endereco_completo,
                fc.observacao
            FROM food.cliente AS fc
            INNER JOIN public.municipio AS m ON m.id = fc.id_municipio
            INNER JOIN public.estado AS e ON e.id = m.id_estado
            INNER JOIN food.clientetelefone AS fct ON fct.id_cliente = fc.id
            WHERE fc.id = %s
            LIMIT 1
        """,
            (id_cliente,),
        )
        cliente_row = cursor_vr.fetchone()

        if not cliente_row:
            return jsonify({"erro": "Cliente não encontrado"}), 404

        # Montar pedido
        pedido = {
            "id": id,
            "id_cliente": id_cliente,
            "nome_cliente": cliente_row[0],
            "telefone": cliente_row[1],
            "endereco": cliente_row[2],
            "observacao_endereco": cliente_row[3] or "",
            "tipo_entrega": pedido_row[6],
            "id_status": pedido_row[7],  # 🔥 agora traz o id_status também
            "id_loja": id_loja,
            "data_entrega": pedido_row[2].isoformat(),
            "hora_entrega": pedido_row[3].strftime("%H:%M"),
            "observacoes": pedido_row[5],
            "itens": [],
        }

        # Buscar os itens do pedido
        cursor_app.execute(
            """
            SELECT id_produto, quantidade,
            quantidade_un, peso, valor_unitario,
            observacao, id_produto_associado
            FROM pedido_itens
            WHERE id_pedido = %s
        """,
            (id,),
        )
        itens = cursor_app.fetchall()

        for item in itens:
            id_produto = item[0]
            id_produto_associado = item[6] if len(item) > 6 else None
            # Buscar dados do produto
            cursor_vr.execute(
                """
                SELECT
                    p.descricaocompleta,
                    te.descricao AS tipo_embalagem
                FROM public.produto p
                LEFT JOIN public.tipoembalagem te ON te.id = p.id_tipoembalagem
                WHERE p.id = %s
                LIMIT 1
            """,
                (id_produto,),
            )
            produto_row = cursor_vr.fetchone()
            descricao = produto_row[0] if produto_row else ""
            if produto_row and produto_row[1]:
                tipo_embalagem = produto_row[1]
            else:
                tipo_embalagem = ""
            desc_produto_associado = ""
            if id_produto_associado:
                associado_row = repo_vr_get_nome_produto(id_produto_associado)
                if associado_row:
                    desc_produto_associado = associado_row[0]
                else:
                    desc_produto_associado = ""
            if id_produto_associado:
                produto_setor = id_produto_associado
            else:
                produto_setor = id_produto
            cursor_vr.execute(
                """
                SELECT s.descricao,s.id
                FROM ficha.setorproduto si
                INNER JOIN ficha.setor s ON s.id = si.id_setor
                WHERE si.id_produto = %s AND s.id_loja = %s
                LIMIT 1
            """,
                (produto_setor, id_loja),
            )
            setor_row = cursor_vr.fetchone()
            setor = setor_row[0] if setor_row else ""
            id_setor = setor_row[1] if setor_row else None
            # Montar o item
            pedido["itens"].append(
                {
                    "cod_produto": id_produto,
                    "descricao": descricao,
                    "tipo_embalagem": tipo_embalagem,
                    "peso_bruto": item[3],
                    "setor": setor,
                    "id_setor": id_setor,
                    "quantidade": item[1],
                    "quantidade_un": item[2],
                    "preco_venda": item[4],
                    "total": round(float(item[1]) * float(item[4]), 2),
                    "observacao": item[5],
                    "cod_produto_associado": id_produto_associado or "",
                    "desc_produto_associado": desc_produto_associado,
                }
            )

        return jsonify(pedido)

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()
        conn_vr.close()


# --- ROTAS HTML ---
@app.route("/api/pedidos/consulta", methods=["POST"])
def api_pedidos_consulta():
    conn_app = conectar_app()
    conn_vr = conectar_vr()
    if not conn_app or not conn_vr:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500
    try:
        dados = request.get_json()
        data_tipo = dados.get("data_tipo", "data_pedido")
        if data_tipo == "data_pedido":
            data_tipo = "criado_em"
        elif data_tipo == "data_entrega":
            data_tipo = "data_entrega"
        data_inicio = dados.get("data_inicio")
        data_fim = dados.get("data_fim")
        tipo_entrega = dados.get("tipo_entrega")
        id_loja = dados.get("id_loja")
        id_cliente = dados.get("id_cliente")
        status = dados.get("status")
        cursor_app = conn_app.cursor()
        cursor_vr = conn_vr.cursor()
        filtros = []
        params = []
        # Converter campo de data para o nome correto da coluna
        data_tipo = dados.get("data_tipo", "data_pedido")
        if data_tipo == "data_pedido":
            data_tipo = "criado_em"
        elif data_tipo == "data_entrega":
            data_tipo = "data_entrega"
        num_pedido = dados.get("num_pedido")
        if num_pedido:
            filtros.append("p.id = %s")
            params.append(num_pedido)
        if data_inicio and data_fim:
            if data_inicio == data_fim:
                filtros.append(f"DATE({data_tipo}) = %s")
                params.append(data_inicio)
            else:
                filtros.append(f"DATE({data_tipo}) BETWEEN %s AND %s")
                params.extend([data_inicio, data_fim])
        elif data_inicio:
            filtros.append(f"DATE({data_tipo}) >= %s")
            params.append(data_inicio)
        elif data_fim:
            filtros.append(f"DATE({data_tipo}) <= %s")
            params.append(data_fim)

        if tipo_entrega:
            filtros.append("p.tipo_entrega = %s")
            params.append(tipo_entrega)

        if id_loja:
            filtros.append("p.id_loja = %s")
            params.append(id_loja)

        if id_cliente:
            filtros.append("p.id_cliente = %s")
            params.append(id_cliente)

        if status:
            filtros.append("p.id_status = %s")
            params.append(status)

        where_clause = "WHERE " + " AND ".join(filtros) if filtros else ""

        cursor_app.execute(
            f"""
            SELECT
                p.id,
                p.id_cliente,
                p.criado_em::date AS data_pedido,
                p.data_entrega,
                p.tipo_entrega,
                p.id_loja,
                p.id_status,
                COALESCE(SUM(pi.quantidade * pi.valor_unitario), 0)
                AS valor_total
            FROM pedidos p
            LEFT JOIN pedido_itens pi ON pi.id_pedido = p.id
            {where_clause}
            GROUP BY p.id, p.id_cliente, p.criado_em, p.data_entrega,
            p.tipo_entrega, p.id_loja, p.id_status
            ORDER BY p.criado_em DESC
        """,
            params,
        )

        pedidos = []
        for row in cursor_app.fetchall():
            id_cliente = row[1]
            id_loja = row[5]
            id_status = row[6]

            # Buscar nome do cliente
            cursor_vr.execute(
                """
                SELECT nome
                FROM food.cliente
                WHERE id = %s
                LIMIT 1
            """,
                (id_cliente,),
            )
            cliente_row = cursor_vr.fetchone()
            if cliente_row:
                nome_cliente = cliente_row[0]
            else:
                nome_cliente = "Cliente não encontrado"

            # Buscar nome da loja
            cursor_vr.execute(
                """
                SELECT descricao
                FROM loja
                WHERE id = %s
                LIMIT 1
            """,
                (id_loja,),
            )
            loja_row = cursor_vr.fetchone()
            nome_loja = loja_row[0] if loja_row else "Loja não encontrada"

            # Buscar descrição do status
            descricao_status = "-"
            if id_status is not None:
                cursor_app.execute(
                    """
                    SELECT descricao
                    FROM status
                    WHERE id = %s
                    LIMIT 1
                """,
                    (id_status,),
                )
                status_row = cursor_app.fetchone()
                if status_row:
                    descricao_status = status_row[0]

            pedidos.append(
                {
                    "id": row[0],
                    "cod_cliente": id_cliente,
                    "nome_cliente": nome_cliente,
                    "data_pedido": row[2].isoformat() if row[2] else None,
                    "data_entrega": row[3].isoformat() if row[3] else None,
                    "tipo_entrega": row[4],
                    "nome_loja": nome_loja,
                    "status": descricao_status,
                    "status_id": id_status,
                    "valor_total": float(row[7]),
                }
            )

        return jsonify(pedidos)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()
        conn_vr.close()


@app.route("/api/setor/pedidos")
def api_pedidos_setor():
    id_setor = request.args.get("setor")
    id_loja = request.args.get("loja")

    # Conectar no banco do App
    conn_app = conectar_app()
    cur_app = conn_app.cursor()

    # Buscar id_produto, quantidade, observacao e id_status do APP
    query_app = """
        SELECT
            pi.id_produto,
            SUM(pi.quantidade_un) AS quantidade_un,
            pi.observacao,
            pe.id_status
        FROM pedido_itens pi
        INNER JOIN pedidos pe ON pe.id = pi.id_pedido
        WHERE pe.id_status = 1
        AND pi.id_setor = %s
        AND pe.id_loja = %s
        GROUP BY pi.id_produto, pi.observacao,
        pe.id_status, pe.id_loja, pi.id_setor
        ORDER BY pi.id_produto
    """

    cur_app.execute(query_app, (id_setor, id_loja))
    produtos_app = cur_app.fetchall()
    cur_app.close()
    conn_app.close()

    if not produtos_app:
        return jsonify([])

    # Buscar descrições dos produtos no VR
    ids_produtos = [
        str(produto[0]) for produto in produtos_app if produto[0] is not None
    ]

    if not ids_produtos:
        return jsonify([])

    conn_vr = conectar_vr()
    cur_vr = conn_vr.cursor()

    query_vr = f"""
        SELECT id, descricaocompleta
        FROM produto
        WHERE id IN ({','.join(['%s' for _ in ids_produtos])})
    """

    cur_vr.execute(query_vr, ids_produtos)
    descricoes_vr = cur_vr.fetchall()

    cur_vr.close()
    conn_vr.close()

    # Mapear id_produto -> descricao
    map_descricoes = {str(row[0]): row[1] for row in descricoes_vr}

    # Montar o resultado
    resultado = []
    for produto in produtos_app:
        id_produto = str(produto[0])
        quantidade_un = produto[1]
        observacao = produto[2]
        id_status = produto[3]

        descricao = map_descricoes.get(id_produto, "Produto sem descrição")

        resultado.append(
            {
                "id_produto": id_produto,
                "descricao": descricao,
                "quantidade_un": int(quantidade_un),
                "observacao": observacao,
                "id_status": id_status,
            }
        )

    return jsonify(resultado)


@app.route("/api/loja/<int:id_loja>/setores")
def api_setores_por_loja(id_loja):
    conn = conectar_vr()
    cur = conn.cursor()

    query = """
        SELECT id, descricao
        FROM ficha.setor
        WHERE id_situacaocadastro = 1
        AND id_loja = %s
        ORDER BY descricao
    """

    cur.execute(query, (id_loja,))
    setores = [{"id": row[0], "descricao": row[1]} for row in cur.fetchall()]

    cur.close()
    conn.close()

    return jsonify(setores)


@app.route("/setor/visualizacao")
def tela_visualizacao_setor():
    conn = conectar_vr()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, descricao
        FROM loja
        WHERE id_situacaocadastro = 1
        ORDER BY descricao
    """)
    lojas = [{"id": row[0], "descricao": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return render_template("setor_visualizacao.html", lojas=lojas)


@app.route("/api/dashboard/indicadores")
def dashboard_indicadores():
    id_loja = request.args.get("id_loja", default=None, type=int)
    conn = conectar_app()
    if not conn:
        return jsonify({"erro": "Erro de conexão"}), 500

    try:
        cursor = conn.cursor()

        where = ""
        params = []

        if id_loja:
            where = "WHERE id_loja = %s"
            params.append(id_loja)

        # Total de pedidos
        cursor.execute(f"SELECT COUNT(*) FROM pedidos {where}", params)
        total_pedidos = cursor.fetchone()[0]

        # Pedidos em produção (status = 1)
        cursor.execute(
            f"""SELECT COUNT(*)
            FROM pedidos
            WHERE id_status = 1
            {'AND id_loja = %s' if id_loja else ''}""",
            params,
        )
        pedidos_producao = cursor.fetchone()[0]
        query = """
            SELECT COUNT(DISTINCT id_setor)
            FROM pedido_itens
        """
        params = ()

        if id_loja:
            query += """
                WHERE id_pedido IN (
                    SELECT id FROM pedidos WHERE id_loja = %s
                )
            """
            params = (id_loja,)
        cursor.execute(query, params)
        pedidos_setor = cursor.fetchone()[0]
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM pedidos
            WHERE tipo_entrega = 'entrega'
            AND data_entrega = CURRENT_DATE
            {'AND id_loja = %s' if id_loja else ''}
        """,
            params,
        )
        pedidos_entrega = cursor.fetchone()[0]
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM pedidos
            WHERE tipo_entrega = 'retirada'
            AND data_entrega = CURRENT_DATE
            {'AND id_loja = %s' if id_loja else ''}
        """,
            params,
        )
        pedidos_retirada = cursor.fetchone()[0]
        return jsonify(
            {
                "total_pedidos": total_pedidos,
                "pedidos_producao": pedidos_producao,
                "pedidos_setor": pedidos_setor,
                "pedidos_entrega": pedidos_entrega,
                "pedidos_retirada": pedidos_retirada,
            }
        )
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


@app.route("/pedidos/consulta")
def consulta_pedidos():
    return render_template("consulta_pedidos.html", titulo_tela="Consulta de Pedidos")


@app.route("/produto_horario")
def produto_horario():
    return render_template("produto_horario.html", titulo_tela="Exibir Horário KDS")


@app.route("/api/status")
def api_status():
    conn = conectar_app()
    if not conn:
        return jsonify([])

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, descricao FROM status ORDER BY descricao")
        rows = cursor.fetchall()
        return jsonify([{"id": r[0], "descricao": r[1]} for r in rows])
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


@app.route("/gestao_encomendas")
def gestao_encomendas():
    return render_template("gestao_encomendas.html", titulo_tela="Gestão de Encomendas")


@app.route("/api/encomendas/consulta", methods=["POST"])
def api_encomendas_consulta():
    conn_app = conectar_app()
    conn_vr = conectar_vr()

    if not conn_app or not conn_vr:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    cursor_app = conn_app.cursor()
    cursor_vr = conn_vr.cursor()

    try:
        filtros = request.get_json() or {}

        pedidos = consultar_encomendas(
            filtros,
            cursor_app,
            cursor_vr,
        )

        return jsonify(pedidos)

    except Exception:
        logger.exception("Erro ao consultar encomendas")

        return jsonify({"erro": "Erro ao consultar encomendas"}), 500

    finally:
        cursor_app.close()
        cursor_vr.close()
        conn_app.close()
        conn_vr.close()


@app.route("/api/encomenda/status", methods=["POST"])
def api_encomenda_status():
    conn_app = conectar_app()  # Banco de encomendas

    if not conn_app:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    try:
        dados = request.get_json()
        id_pedido = dados.get("id_pedido")
        id_status = dados.get("id_status")

        if not id_pedido or not id_status:
            return jsonify({"erro": "Dados incompletos"}), 400

        cursor = conn_app.cursor()

        cursor.execute(
            """
            UPDATE pedidos
            SET id_status = %s
            WHERE id = %s
        """,
            (id_status, id_pedido),
        )

        conn_app.commit()

        return jsonify({"mensagem": "Status atualizado com sucesso"})

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()


@app.route("/api/encomenda/editar", methods=["POST"])
def api_encomenda_editar():
    conn_app = conectar_app()
    if not conn_app:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    try:
        dados = request.get_json()
        id_pedido = dados.get("id_pedido")
        itens = dados.get("itens", [])

        if not id_pedido or not itens:
            return jsonify({"erro": "Dados incompletos"}), 400

        cursor = conn_app.cursor()

        # Exclui todos os itens antigos do pedido
        cursor.execute(
            """DELETE FROM pedido_itens
                       WHERE id_pedido = %s""",
            (id_pedido,),
        )
        for item in itens:
            cursor.execute(
                """
                INSERT INTO pedido_itens (
                id_pedido, id_produto, id_setor, quantidade, quantidade_un,
                peso, valor_unitario, observacao,
                id_produto_associado, id_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
             """,
                (
                    id_pedido,
                    item.get("cod_produto"),
                    item.get("id_setor"),
                    item.get("quantidade"),
                    item.get("quantidade_un"),
                    item.get("peso_bruto") or 0,
                    item.get("preco_venda") or 0,
                    item.get("observacao"),
                    item.get("cod_produto_associado") or None,
                ),
            )

        conn_app.commit()
        return jsonify({"mensagem": "Itens atualizados com sucesso"})

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()


@app.route("/api/encomenda/finalizar", methods=["POST"])
def api_finalizar_encomenda():
    data = request.get_json()
    id_pedido = data.get("id_pedido")
    numero_ficha = data.get("numero_ficha")
    itens_editados = data.get("itens", [])

    conn_app = conectar_app()
    conn_vr = conectar_vr()

    if not conn_app or not conn_vr:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    try:
        cursor_app = conn_app.cursor()
        cursor_vr = conn_vr.cursor()

        # Atualizar os itens editados no conecta_app
        for item in itens_editados:
            cod_produto = item.get("cod_produto")
            quantidade = item.get("quantidade")
            quantidade_un = item.get("quantidade_un")
            cursor_app.execute(
                """
                UPDATE pedido_itens
                SET quantidade = %s, quantidade_un = %s
                WHERE id_pedido = %s AND id_produto = %s
            """,
                (quantidade, quantidade_un, id_pedido, cod_produto),
            )
        conn_app.commit()

        # Buscar id_loja do pedido
        cursor_app.execute(
            """SELECT id_loja
                           FROM pedidos WHERE id = %s""",
            (id_pedido,),
        )
        loja_row = cursor_app.fetchone()
        id_loja = loja_row[0] if loja_row else None

        if not id_loja:
            return (
                jsonify({"erro": """ID da loja não
                            encontrado para o pedido."""}),
                400,
            )
        cursor_vr.execute(
            "SELECT id FROM pdv.ficha WHERE numeroficha = %s AND id_loja = %s",
            (numero_ficha, id_loja),
        )
        row = cursor_vr.fetchone()
        if row:
            id_ficha = row[0]

            # Atualiza a ficha existente
            cursor_vr.execute(
                """
                UPDATE pdv.ficha
                SET data = CURRENT_DATE, datahora = NOW(), numeroficha = %s
                WHERE id = %s
            """,
                (numero_ficha, id_ficha),
            )

            # Remove os itens anteriores
            cursor_vr.execute(
                "DELETE FROM pdv.fichaitem WHERE id_ficha = %s", (id_ficha,)
            )
        else:
            # Gera novo ID para ficha
            cursor_vr.execute("SELECT nextval('ficha.ficha_id_seq')")
            id_ficha = cursor_vr.fetchone()[0]

            # Insere nova ficha
            cursor_vr.execute(
                """
                INSERT INTO pdv.ficha (
                    id, id_loja, numeroficha, data, datahora, id_mesa, cliente
                )
                VALUES (%s, %s, %s, CURRENT_DATE, NOW(), %s, %s)
            """,
                (id_ficha, id_loja, numero_ficha, 1, None),
            )

        # Buscar os itens atualizados do pedido
        cursor_app.execute(
            """
            SELECT id_produto, quantidade, valor_unitario
            FROM pedido_itens
            WHERE id_pedido = %s
        """,
            (id_pedido,),
        )
        itens_pedido = cursor_app.fetchall()

        # Inserir itens na pdv.fichaitem
        sequencia = 1
        for item in itens_pedido:
            id_produto, quantidade, valor_unitario = item
            if quantidade == 0:
                continue

            # Buscar codigobarras
            cursor_vr.execute(
                """
                SELECT codigobarras
                FROM produtoautomacao
                WHERE id_produto = %s
                LIMIT 1
            """,
                (id_produto,),
            )
            codigo_barras_row = cursor_vr.fetchone()
            codigobarras = codigo_barras_row[0] if codigo_barras_row else None

            # Gerar novo ID para fichaitem
            cursor_vr.execute("SELECT nextval('ficha.fichaitem_id_seq')")
            id_fichaitem = cursor_vr.fetchone()[0]
            if valor_unitario > 0:
                cursor_vr.execute(
                    """
                    INSERT INTO pdv.fichaitem (
                        id, id_ficha, sequencia, codigobarras, quantidade,
                        precovenda, id_atendente, iscancelado, isimpresso
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        id_fichaitem,
                        id_ficha,
                        sequencia,
                        codigobarras,
                        quantidade,
                        valor_unitario,
                        -1,
                        False,
                        False,
                    ),
                )

                sequencia += 1

        conn_vr.commit()

        # Atualiza o status do pedido
        cursor_app.execute(
            """
            UPDATE pedidos
               SET id_status = 7,
                   data_finalizacao = NOW(),
                   tipo_finalizacao = 'vrficha'
             WHERE id = %s;
        """,
            (id_pedido,),
        )
        conn_app.commit()

        return jsonify({"mensagem": "Pedido finalizado com sucesso."})

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()
        conn_vr.close()


@app.route("/api/encomenda/finalizar_vrfood", methods=["POST"])
def api_finalizar_encomenda_vrfood():
    data = request.get_json()
    id_pedido = data.get("id_pedido")
    itens_editados = data.get("itens", [])

    conn_app = conectar_app()
    conn_vr = conectar_vr()
    if not conn_app or not conn_vr:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    try:
        cur_app = conn_app.cursor()
        cur_vr = conn_vr.cursor()
        for item in itens_editados:
            cod_produto = item.get("cod_produto")
            qtd_modal = to_decimal(item.get("quantidade"))
            qtd_un = to_decimal(item.get("quantidade_un"))
            cur_app.execute(
                """
                UPDATE pedido_itens
                   SET quantidade   = %s,
                       quantidade_un = %s
                 WHERE id_pedido    = %s
                   AND id_produto   = %s
            """,
                (qtd_modal, qtd_un, id_pedido, cod_produto),
            )
        conn_app.commit()
        cur_app.execute(
            """SELECT id_loja, id_cliente
            FROM pedidos WHERE id = %s""",
            (id_pedido,),
        )
        row = cur_app.fetchone()
        if not row:
            return jsonify({"erro": "Pedido não encontrado."}), 400
        id_loja, id_cliente = row
        codigo_pedido = int(id_pedido)
        # Itens já atualizados
        cur_app.execute(
            """
            SELECT id_produto, quantidade,
            valor_unitario, COALESCE(observacao,''), id_setor
              FROM pedido_itens
             WHERE id_pedido = %s
        """,
            (id_pedido,),
        )
        itens = cur_app.fetchall()
        cur_vr.execute("LOCK TABLE food.venda IN EXCLUSIVE MODE")
        cur_vr.execute("SELECT COALESCE(MAX(id),0) FROM food.venda")
        id_venda = (cur_vr.fetchone()[0] or 0) + 1
        cur_vr.execute(
            """
            INSERT INTO food.venda (
                id, id_loja, id_cliente,
                id_tipopagamento, datahora, tempoentrega,
                troco, desconto, entrega,
                id_usuario, importado, id_situacaovenda,
                codigo, id_ifood, json, isretirada, dataretirada, horaretirada,
                id_entregador, id_vendedor
            ) VALUES (
                %s, %s, %s, 3, NOW(), '00:00:00',
                0, 0, 0, 0, FALSE, 0,
                %s, NULL, NULL, FALSE, NULL, NULL,
                NULL, NULL
            )
        """,
            (id_venda, id_loja, id_cliente, codigo_pedido),
        )

        # 4) Itens
        itens_inseridos = 0
        for id_produto, quantidade, precovenda, observacao, id_setor in itens:
            qtd = to_decimal(quantidade)
            if qtd <= 0:
                continue
            pv = to_decimal(precovenda)
            valortotal = pv * qtd
            if valortotal > 0:
                cur_vr.execute(
                    """
                    INSERT INTO food.vendaitem
                        (id, id_venda, id_produto, quantidade, precovenda,
                        valortotal, observacao, id_setor)
                    VALUES
                        (nextval('food.vendaitem_id_seq'), %s, %s, %s, %s, %s,
                        %s, %s)
                """,
                    (
                        id_venda,
                        int(id_produto),
                        float(qtd),
                        float(pv),
                        float(valortotal),
                        observacao,
                        int(id_setor),
                    ),
                )
                itens_inseridos += 1

        conn_vr.commit()

        # 5) Marca pedido como finalizado no Gestão
        cur_app.execute(
            """
            UPDATE pedidos
               SET id_status = 7,
                   data_finalizacao = NOW(),
                   tipo_finalizacao = 'vrfood'
             WHERE id = %s;
        """,
            (id_pedido,),
        )
        conn_app.commit()

        return jsonify(
            {
                "mensagem": "Pedido finalizado no VRFood com sucesso.",
                "id_venda": id_venda,
                "codigo": codigo_pedido,
                "itens_inseridos": itens_inseridos,
            }
        )

    except Exception as e:
        conn_app.rollback()
        conn_vr.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        conn_app.close()
        conn_vr.close()


@app.route("/api/usuarios/<int:id_usuario>", methods=["GET"])
def api_buscar_usuario(id_usuario):
    conn_app = conectar_app()

    if not conn_app:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    try:
        cursor_app = conn_app.cursor()
        cursor_app.execute(
            """
            SELECT id, nome, email, id_loja
            FROM usuarios
            WHERE id = %s
        """,
            (id_usuario,),
        )

        row = cursor_app.fetchone()
        if not row:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        id_usuario, nome, email, id_loja = row

        usuario = {"id": id_usuario, "nome": nome, "email": email, "id_loja": id_loja}

        return jsonify(usuario)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()


@app.route("/api/usuarios/novo", methods=["POST"])
def api_novo_usuario():
    conn_app = conectar_app()

    if not conn_app:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    try:
        data = request.get_json()
        nome = data.get("nome")
        email = data.get("email")
        senha = data.get("senha")
        id_loja = data.get("id_loja")

        if not nome or not email or not senha or not id_loja:
            return jsonify({"erro": "Campos obrigatórios faltando"}), 400
        senha_hash = bcrypt.generate_password_hash(senha).decode("utf-8")

        cursor_app = conn_app.cursor()
        cursor_app.execute(
            """
            INSERT INTO usuarios (nome, email, senha, id_loja, criado_em)
            VALUES (%s, %s, %s, %s, NOW())
        """,
            (nome, email, senha_hash, id_loja),
        )

        conn_app.commit()

        return jsonify({"mensagem": "Usuário criado com sucesso!"})

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()


@app.route("/api/usuarios/editar/<int:id_usuario>", methods=["PUT"])
def api_editar_usuario(id_usuario):
    conn_app = conectar_app()

    if not conn_app:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    try:
        data = request.get_json()
        nome = data.get("nome")
        email = data.get("email")
        senha = data.get("senha")  # Se enviar vazio, não altera
        id_loja = data.get("id_loja")

        if not nome or not email or not id_loja:
            return jsonify({"erro": "Campos obrigatórios faltando"}), 400

        cursor_app = conn_app.cursor()

        if senha:
            senha_hash = bcrypt.generate_password_hash(senha).decode("utf-8")
            cursor_app.execute(
                """
                UPDATE usuarios
                SET nome = %s, email = %s, senha = %s, id_loja = %s
                WHERE id = %s
            """,
                (nome, email, senha_hash, id_loja, id_usuario),
            )
        else:
            cursor_app.execute(
                """
                UPDATE usuarios
                SET nome = %s, email = %s, id_loja = %s
                WHERE id = %s
            """,
                (nome, email, id_loja, id_usuario),
            )

        conn_app.commit()

        return jsonify({"mensagem": "Usuário atualizado com sucesso!"})

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()


@app.route("/usuarios/cadastro")
def usuarios_cadastro():
    return render_template("usuarios.html", titulo_tela="Cadastro de Usuários")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


@app.route("/api/produto_associado/salvar", methods=["POST"])
def salvar_produto_associado():
    conn = conectar_app()
    try:
        dados = request.get_json()
        cur = conn.cursor()

        if not dados or "descricao_grupo" not in dados or "id_loja" not in dados:
            return jsonify({"erro": "Dados incompletos"}), 400

        descricao_grupo = dados["descricao_grupo"]
        id_loja = dados["id_loja"]
        principais = dados["principais"]  # lista de códigos
        opcoes = dados["opcoes"]  # lista de códigos

        # Insere grupo
        cur.execute(
            """
            INSERT INTO controle_id_produtoopcoes (descricao, id_loja)
            VALUES (%s, %s) RETURNING id
        """,
            (descricao_grupo, id_loja),
        )
        id_grupo = cur.fetchone()[0]

        # Insere principais
        for p in principais:
            cur.execute(
                """
                INSERT INTO produto_opcoes_principal (id_produtoopcoes,
                id_produto_principal)
                VALUES (%s, %s)
            """,
                (id_grupo, p),
            )

        # Insere associados
        for o in opcoes:
            cur.execute(
                """
                INSERT INTO produto_opcoes_associado (id_produtoopcoes,
                id_produto_associado)
                VALUES (%s, %s)
            """,
                (id_grupo, o),
            )

        conn.commit()
        return (
            jsonify(
                {
                    "status": "ok",
                    "id_produtoopcoes": id_grupo,
                    "descricao": descricao_grupo,
                    "id_loja": id_loja,
                }
            ),
            201,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"erro": str(e)}), 500

    finally:
        conn.close()


@app.route("/api/produto_associado/editar/<int:id>", methods=["PUT"])
def editar_produto_associado(id):
    conn = conectar_app()
    try:
        dados = request.get_json()
        cur = conn.cursor()

        # Atualiza o grupo (pode atualizar descrição e loja se quiser)
        cur.execute(
            """
            UPDATE controle_id_produtoopcoes
            SET descricao = %s, id_loja = %s
            WHERE id = %s
        """,
            (dados["descricao_grupo"], dados["id_loja"], id),
        )

        # Apaga principais e associados antigos do grupo
        cur.execute(
            """DELETE FROM produto_opcoes_principal
            WHERE id_produtoopcoes = %s""",
            (id,),
        )
        cur.execute(
            """DELETE FROM produto_opcoes_associado
            WHERE id_produtoopcoes = %s""",
            (id,),
        )
        for p in dados["principais"]:
            cur.execute(
                """
                INSERT INTO produto_opcoes_principal (id_produtoopcoes,
                id_produto_principal)
                VALUES (%s, %s)
            """,
                (id, p),
            )

        # Insere os novos associados
        for o in dados["opcoes"]:
            cur.execute(
                """
                INSERT INTO produto_opcoes_associado (id_produtoopcoes,
                id_produto_associado)
                VALUES (%s, %s)
            """,
                (id, o),
            )

        conn.commit()
        return jsonify({"status": "ok", "id_produtoopcoes": id})

    except Exception as e:
        conn.rollback()
        return jsonify({"erro": str(e)}), 500

    finally:
        conn.close()


@app.route("/api/produto_associado/excluir/<int:id>", methods=["DELETE"])
def excluir_grupo_produto_associado(id):
    conn = conectar_app()
    try:
        cur = conn.cursor()
        # Exclui todos os principais desse grupo
        cur.execute(
            """DELETE FROM produto_opcoes_principal
            WHERE id_produtoopcoes = %s""",
            (id,),
        )
        # Exclui todos os associados desse grupo
        cur.execute(
            """DELETE FROM produto_opcoes_associado
            WHERE id_produtoopcoes = %s""",
            (id,),
        )
        # Exclui o grupo (isso pode ser suficiente se usou ON DELETE CASCADE)
        cur.execute(
            """DELETE FROM controle_id_produtoopcoes
                    WHERE id = %s""",
            (id,),
        )
        conn.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


@app.route("/produto_associado")
def tela_produto_associado():
    return render_template(
        "produto_associado.html", titulo_tela="Cadastro de Associados"
    )


@app.route("/consulta_associado")
def pagina_consulta_associado():
    return render_template(
        "consulta_associado.html", titulo_tela="Consulta de Associados"
    )


@app.route("/consulta_composto")
def pagina_consulta_composto():
    return render_template(
        "consulta_composto.html", titulo_tela="Consulta de Produtos Compostos"
    )


@app.route("/api/produto_associado/grupos")
def listar_grupos_produto_associado():
    conn_app = conectar_app()
    conn_vr = conectar_vr()
    try:
        # Busca os grupos com id_loja
        cur_app = conn_app.cursor()
        cur_app.execute("""
            SELECT id, descricao, id_loja
            FROM controle_id_produtoopcoes
            ORDER BY id DESC
        """)
        grupos = cur_app.fetchall()

        # Busca produtos principais e associados de todos os grupos
        principais_dict = {}
        associados_dict = {}
        for g in grupos:
            cur_app.execute(
                """SELECT id_produto_principal
                FROM produto_opcoes_principal
                WHERE id_produtoopcoes = %s""",
                (g[0],),
            )
            principais_dict[g[0]] = [r[0] for r in cur_app.fetchall()]
            cur_app.execute(
                """SELECT id_produto_associado
                FROM produto_opcoes_associado
                WHERE id_produtoopcoes = %s""",
                (g[0],),
            )
            associados_dict[g[0]] = [r[0] for r in cur_app.fetchall()]

        # Descobre todos os ids de loja usados
        id_lojas = list({g[2] for g in grupos if g[2] is not None})
        nomes_loja = {}
        if id_lojas:
            cur_vr = conn_vr.cursor()
            cur_vr.execute(
                """SELECT id, descricao
                FROM loja WHERE id = ANY(%s)""",
                (id_lojas,),
            )
            nomes_loja = {row[0]: row[1] for row in cur_vr.fetchall()}

        # Monta o resultado com nome da loja E lista dos produtos
        return jsonify(
            [
                {
                    "id": g[0],
                    "descricao": g[1],
                    "id_loja": g[2],
                    "nome_loja": nomes_loja.get(g[2], "") if g[2] else "",
                    "produtos_principais": principais_dict.get(g[0], []),
                    "produtos_associados": associados_dict.get(g[0], []),
                }
                for g in grupos
            ]
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"erro": str(e)}), 500
    finally:
        conn_app.close()
        conn_vr.close()


@app.route("/produto_associado")
def produto_associado():
    id_grupo = request.args.get("id")
    is_modal = request.args.get("modal") == "1"
    if is_modal:
        contexto = {}
        if id_grupo:
            # Busca os dados do grupo
            conn = conectar_app()
            cur = conn.cursor()
            cur.execute(
                """SELECT id, descricao, id_loja
                    FROM controle_id_produtoopcoes
                    WHERE id = %s""",
                (id_grupo,),
            )
            grupo = cur.fetchone()
            principais, opcoes = [], []
            if grupo:
                cur.execute(
                    """SELECT id_produto_principal
                        FROM produto_opcoes_principal
                        WHERE id_produtoopcoes = %s""",
                    (id_grupo,),
                )
                principais = [r[0] for r in cur.fetchall()]
                cur.execute(
                    """SELECT id_produto_associado
                    FROM produto_opcoes_associado
                    WHERE id_produtoopcoes = %s""",
                    (id_grupo,),
                )
                opcoes = [r[0] for r in cur.fetchall()]
                contexto = {
                    "id": grupo[0],
                    "descricao": grupo[1],
                    "id_loja": grupo[2],
                    "principais": [
                        {"cod": cod, "desc": "", "setor": ""} for cod in principais
                    ],
                    "opcoes": [{"cod": cod, "desc": "", "setor": ""} for cod in opcoes],
                }
            cur.close()
            conn.close()
        return render_template("produto_associado.html", **contexto)
    else:
        return redirect("/consulta_associado")


@app.route("/api/produto_associado/grupo/<int:id>")
def carregar_produto_associado(id):
    conn = conectar_app()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, descricao, id_loja
            FROM controle_id_produtoopcoes
            WHERE id = %s""",
            (id,),
        )
        grupo = cur.fetchone()
        if not grupo:
            return jsonify({"erro": "Grupo não encontrado"}), 404

        # Busca produtos principais
        cur.execute(
            """SELECT id_produto_principal
            FROM produto_opcoes_principal
            WHERE id_produtoopcoes = %s""",
            (id,),
        )
        principais = [r[0] for r in cur.fetchall()]
        # Busca produtos de opção
        cur.execute(
            """SELECT id_produto_associado
            FROM produto_opcoes_associado
            WHERE id_produtoopcoes = %s""",
            (id,),
        )
        opcoes = [r[0] for r in cur.fetchall()]

        return jsonify(
            {
                "id": grupo[0],
                "descricao": grupo[1],
                "id_loja": grupo[2],
                "principais": [
                    {"cod": cod, "desc": "", "setor": ""} for cod in principais
                ],
                "opcoes": [{"cod": cod, "desc": "", "setor": ""} for cod in opcoes],
            }
        )
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


@app.route("/produto_composto")
def produto_composto():
    id_produto = request.args.get("id_produto", type=int)
    modal = request.args.get("modal")
    return render_template("produto_composto.html", id_produto=id_produto, modal=modal)


@app.route("/api/produtos_compostos")
def get_produtos_compostos():
    try:
        return jsonify(svc_get_produtos_compostos())
    except Exception as e:
        logger.exception(e)
        return jsonify({"error": "Erro interno"}), 500


@app.route("/api/produtos_compostos/salvar", methods=["POST"])
def api_salvar_composto():
    dados = request.get_json()
    if not dados or not dados.get("id_produto"):
        return jsonify({"erro": "id_produto obrigatório."}), 400
    ok = svc_salvar_produtos_compostos(dados)
    if not ok:
        return jsonify({"erro": "Erro ao salvar."}), 500
    return jsonify({"ok": True})


@app.route("/api/produtos_compostos/remover/<int:id_produto>", methods=["DELETE"])
def api_remover_composto(id_produto):
    ok = svc_remover_produtos_compostos(id_produto)
    if not ok:
        return jsonify({"erro": "Erro ao remover."}), 500
    return jsonify({"ok": True})


@app.route("/api/produtos_compostos/calculos")
def api_get_calculos():
    data = svc_get_calculos_pessoa()
    if data is False:
        return jsonify({"erro": "Erro ao buscar."}), 500
    return jsonify(data)


@app.route("/api/produtos_compostos/<int:id_produto>", methods=["POST"])
def api_get_composto(id_produto):
    estrutura = repo_get_composto_estrutura(id_produto)
    if estrutura is False:
        return jsonify({"erro": "Erro ao buscar composto."}), 500
    if estrutura is None:
        return jsonify({"erro": "Produto não é composto."}), 404
    itens_fixos = repo_get_itens_fixos(id_produto)
    if itens_fixos is False:
        return jsonify({"erro": "Erro ao buscar itens fixos."}), 500
    grupos = repo_get_grupos_opcionais(id_produto)
    if grupos is False:
        return jsonify({"erro": "Erro ao buscar grupos opcionais."}), 500
    ids_fixos = [item["id_produto"] for item in itens_fixos]
    ids_opcionais = [
        item["id_produto"] for dados in grupos.values() for item in dados["itens"]
    ]
    todos_ids = list(set(ids_fixos + ids_opcionais))
    nomes = repo_vr_get_nomes_produtos(todos_ids) if todos_ids else {}
    nome_pai = repo_vr_get_nome_produto(id_produto)
    itens_fixos_com_nomes = adicionar_nomes_produtos(itens_fixos, nomes)
    grupos_com_nomes = [
        {
            "chave": chave,
            "quantidade_total": dados["quantidade_total"],
            "itens": adicionar_nomes_produtos(dados["itens"], nomes),
        }
        for chave, dados in grupos.items()
    ]

    return jsonify(
        {
            "id": id_produto,
            "descricao": nome_pai,
            "tipo": estrutura.get("tipo"),
            "min_pessoas": estrutura.get("pedido_min_pessoas"),
            "calculo_pessoa": estrutura.get("calculo_pessoa"),
            "itens_fixos": itens_fixos_com_nomes,
            "grupos_opcionais": grupos_com_nomes,
        }
    )


@app.route("/api/produtos_compostos/explodir/<int:id_produto>", methods=["POST"])
def api_explodir_composto(id_produto):
    dados = request.get_json(silent=True) or {}
    id_loja = dados.get("id_loja")
    if not id_loja:
        return jsonify({"erro": "id_loja é obrigatório."}), 400
    pessoas = dados.get("pessoas")
    quantidade = dados.get("quantidade")
    if pessoas is not None:
        fator = int(pessoas)
        if fator <= 0:
            return jsonify({"erro": "pessoas deve ser maior que zero."}), 400
    elif quantidade is not None:
        fator = int(quantidade)
        if fator <= 0:
            return (
                jsonify({"erro": """quantidade deve ser
                            maior que zero."""}),
                400,
            )
    else:
        return jsonify({"erro": "Informe pessoas ou quantidade."}), 400
    estrutura = repo_get_composto_estrutura(id_produto)
    if estrutura is False:
        return jsonify({"erro": "Erro ao buscar composto."}), 500
    if estrutura is None:
        return jsonify({"erro": "Produto não é composto."}), 404
    produto_pai = repo_get_produto_detalhe(id_produto, int(id_loja))
    if not produto_pai:
        return (
            jsonify({"erro": """Produto não encontrado
                        na loja informada."""}),
            404,
        )
    tem_calculo_pessoa = bool(estrutura.get("calculo_pessoa"))
    if tem_calculo_pessoa and not dados.get("pessoas"):
        return jsonify({"erro": "Este composto requer o campo pessoas."}), 400
    if not tem_calculo_pessoa and not dados.get("quantidade"):
        return (
            jsonify({"erro": """Este composto requer
                        o campo quantidade."""}),
            400,
        )
    componentes = calcular_componentes(
        id_produto, fator, estrutura, dados.get("escolhas_opcionais") or {}
    )
    if componentes is False:
        return jsonify({"erro": "Erro ao calcular componentes."}), 500
    return jsonify(
        {"itens": montar_itens(produto_pai, fator,
                               componentes, estrutura['tipo'],
                               int(id_loja))}
    )


@app.route(
    "/api/produtos/opcoes_associadas/<int:id_produto_principal>", methods=["GET"]
)
def opcoes_associadas(id_produto_principal):
    conn_app = conectar_app()
    cursor_app = conn_app.cursor()

    # 1. Buscar id_produtoopcoes na tabela produto_opcoes_principal
    cursor_app.execute(
        """
        SELECT id_produtoopcoes FROM produto_opcoes_principal
        WHERE id_produto_principal = %s
    """,
        (id_produto_principal,),
    )
    row = cursor_app.fetchone()

    if not row or not row[0]:
        return jsonify([])  # Não tem associados

    id_produtoopcoes = row[0]

    # 2. Buscar id_produto_associado na tabela produto_opcoes_associado
    cursor_app.execute(
        """
        SELECT id_produto_associado FROM produto_opcoes_associado
        WHERE id_produtoopcoes = %s
    """,
        (id_produtoopcoes,),
    )
    associados = cursor_app.fetchall()

    if not associados:
        return jsonify([])  # Não tem associados

    ids_associados = [a[0] for a in associados]

    # 3. Buscar as descrições completas no banco VR
    if not ids_associados:
        return jsonify([])

    conn_vr = conectar_vr()
    cursor_vr = conn_vr.cursor()
    cursor_vr.execute(
        "SELECT id, descricaocompleta FROM produto WHERE id IN %s",
        (tuple(ids_associados),),
    )
    resultado = cursor_vr.fetchall()

    # 4. Montar o JSON de retorno
    lista_retorno = [{"id": r[0], "nome": r[1]} for r in resultado]

    return jsonify(lista_retorno)


@app.route("/setor/kds")
def setor_kds():
    return render_template("kds.html", titulo_tela="KDS")


@app.route("/api/kds/pedidos")
def api_kds_pedidos():
    loja = request.args.get("loja")
    setor = request.args.get("setor")

    conn = conectar_app()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.id                                         AS id_pedido,
               pi.id                                        AS id_item,
               COALESCE(pi.id_produto_associado, pi.id_produto)
               AS id_produto_preferencial,
               pi.quantidade_un,
               p.data_entrega,
               p.hora_entrega,
               pi.observacao,
               pi.id_produto_associado,
               pi.id_setor,
               pi.id_status AS id_status_item,
               p.tipo_entrega,
               p.id_status AS id_status_pedido,
               pi.quantidade
          FROM pedidos p
          JOIN pedido_itens pi ON pi.id_pedido = p.id
         WHERE p.id_loja = %s
           AND pi.id_setor = %s
           AND (p.data_entrega = CURRENT_DATE
            OR  p.data_entrega = CURRENT_DATE + INTERVAL '1 day')
           AND (p.id_status NOT IN (5, 7))
    """,
        (loja, setor),
    )

    pedidos = []
    produtos_ids = set()
    rows = cursor.fetchall()

    # junta IDs para buscar descrição (usa associado se existir)
    for row in rows:
        produto_id = row[7] if row[7] else row[2]
        produtos_ids.add(produto_id)

    # busca descrições em lote
    descricoes = {}
    if produtos_ids:
        conn_vr = conectar_vr()
        cursor_vr = conn_vr.cursor()
        cursor_vr.execute(
            "SELECT id, descricaocompleta FROM produto WHERE id IN %s",
            (tuple(produtos_ids),),
        )
        for prod_row in cursor_vr.fetchall():
            descricoes[prod_row[0]] = prod_row[1]
        cursor_vr.close()
        conn_vr.close()

    for row in rows:
        produto_id = row[7] if row[7] else row[2]
        pedidos.append(
            {
                "id": row[0],
                "id_item": row[1],
                "id_produto": produto_id,
                "descricao": descricoes.get(produto_id, str(produto_id)),
                "quantidade": row[3],
                "data": str(row[4]),
                "hora": (
                    row[5].strftime("%H:%M")
                    if hasattr(row[5], "strftime")
                    else (str(row[5]) if row[5] is not None else "")
                ),
                "observacao": row[6] or "",
                "id_produto_associado": row[7],
                "id_setor": row[8],
                "id_status": row[9],
                "tipo_entrega": row[10],
                "id_status_pedido": row[11],
                "peso": row[12],
            }
        )

    return jsonify(pedidos)


@app.route("/api/kds/pedido/produzir", methods=["POST"])
def kds_produzir():
    data = request.get_json()
    id_pedidos = data.get("ids", [])
    if not id_pedidos:
        return (
            jsonify(
                {
                    "success": False,
                    "msg": """Nenhum pedido
                        informado!""",
                }
            ),
            400,
        )

    conn = conectar_app()
    cursor = conn.cursor()
    cursor.execute("UPDATE pedidos SET id_status = 1 WHERE id = ANY(%s)", (id_pedidos,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/kds/pedido/finalizar", methods=["POST"])
def kds_finalizar():
    data = request.get_json()
    id_pedidos = data.get("ids", [])
    if not id_pedidos:
        return jsonify({"success": False, "msg": "Nenhum pedido informado!"}), 400

    conn = conectar_app()
    cursor = conn.cursor()
    cursor.execute("UPDATE pedidos SET id_status = 7 WHERE id = ANY(%s)", (id_pedidos,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/kds/item/produzir", methods=["POST"])
def kds_item_produzir():
    data = request.get_json()
    ids_itens = data.get("ids", [])
    if not ids_itens:
        return jsonify({"success": False, "msg": "Nenhum item informado!"}), 400

    conn = conectar_app()
    cursor = conn.cursor()
    # Atualiza apenas os itens para status = 1 (em produção)
    cursor.execute(
        "UPDATE pedido_itens SET id_status = 1 WHERE id = ANY(%s)", (ids_itens,)
    )
    conn.commit()
    cursor.close()

    cursor = conn.cursor()
    for id_item in ids_itens:
        cursor.execute("SELECT id_pedido FROM pedido_itens WHERE id = %s", (id_item,))
        id_pedido_row = cursor.fetchone()
        if not id_pedido_row:
            continue
        id_pedido = id_pedido_row[0]
        cursor.execute(
            "SELECT DISTINCT id_status FROM pedido_itens WHERE id_pedido = %s",
            (id_pedido,),
        )
        status_list = [r[0] for r in cursor.fetchall()]
        # Se só existe um status (todos iguais), atualiza o pedido principal
        if len(status_list) == 1:
            cursor.execute(
                "UPDATE pedidos SET id_status = %s WHERE id = %s",
                (status_list[0], id_pedido),
            )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/kds/item/finalizar", methods=["POST"])
def kds_item_finalizar():
    data = request.get_json()
    ids_itens = data.get("ids", [])
    if not ids_itens:
        return jsonify({"success": False, "msg": "Nenhum item informado!"}), 400

    conn = conectar_app()
    cursor = conn.cursor()
    # Atualiza apenas os itens para status = 2 (produzido)
    cursor.execute(
        "UPDATE pedido_itens SET id_status = 2 WHERE id = ANY(%s)", (ids_itens,)
    )
    conn.commit()
    cursor.close()

    cursor = conn.cursor()
    for id_item in ids_itens:
        cursor.execute("SELECT id_pedido FROM pedido_itens WHERE id = %s", (id_item,))
        id_pedido_row = cursor.fetchone()
        if not id_pedido_row:
            continue
        id_pedido = id_pedido_row[0]
        cursor.execute(
            "SELECT DISTINCT id_status FROM pedido_itens WHERE id_pedido = %s",
            (id_pedido,),
        )
        status_list = [r[0] for r in cursor.fetchall()]
        # Se só existe um status (todos iguais), atualiza o pedido principal
        if len(status_list) == 1:
            cursor.execute(
                "UPDATE pedidos SET id_status = %s WHERE id = %s",
                (status_list[0], id_pedido),
            )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/pedido/<int:id_pedido>/imprimir", methods=["POST"])
def imprimir_pedido(id_pedido):
    from flask import jsonify, request

    data = request.get_json() or {}

    linhas_extras = int(data.get("linhas_extras", 3))
    cortar = bool(data.get("cortar", True))
    tipo_corte = data.get("tipo_corte") or "full"

    conn_app = conectar_app()
    conn_vr = conectar_vr()

    if not conn_app or not conn_vr:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    cursor_app = conn_app.cursor()
    cursor_vr = conn_vr.cursor()

    try:
        pedido = buscar_pedido(cursor_app, id_pedido)

        if not pedido:
            return jsonify({"sucesso": False, "mensagem": "Pedido não encontrado"}), 404

        impressora = buscar_impressora(cursor_app, pedido["id_loja"])

        if not impressora:
            return (
                jsonify(
                    {
                        "sucesso": False,
                        "mensagem": """Nenhuma impressora
                        configurada para esta loja (setor em branco).""",
                        "id_loja": pedido["id_loja"],
                    }
                ),
                412,
            )

        cliente = buscar_cliente(cursor_vr, pedido["id_cliente"])
        nome_loja = buscar_nome_loja(cursor_vr, pedido["id_loja"])
        status = buscar_status(cursor_app, pedido["id_status"])
        valor_total = buscar_valor_total(cursor_app, id_pedido)
        itens = buscar_itens(cursor_app, cursor_vr, id_pedido)

        texto = montar_texto_pedido(
            pedido=pedido,
            cliente=cliente,
            nome_loja=nome_loja,
            status=status,
            valor_total=valor_total,
            itens=itens,
            linhas_extras=linhas_extras,
        )

        dados = gerar_dados_impressao(texto=texto, cortar=cortar, tipo_corte=tipo_corte)

        enviar_para_impressora(
            caminho_impressora=impressora, dados=dados, id_pedido=id_pedido
        )

        marcar_pedido_impresso(cursor_app, conn_app, id_pedido)

        return jsonify({"sucesso": True})

    except Exception as e:
        conn_app.rollback()
        return jsonify({"erro": str(e)}), 500

    finally:
        fechar_conexao(cursor_app, conn_app)
        fechar_conexao(cursor_vr, conn_vr)


@app.route("/api/impressora", methods=["GET"])
def api_impressora_get():
    conn = conectar_app()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT caminho_impressora
                       FROM impressora ORDER BY id DESC LIMIT 1""")
        row = cursor.fetchone()
        caminho = row[0] if row else ""
        return jsonify({"caminho_impressora": caminho})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/impressora", methods=["POST"])
def api_impressora_post():
    conn = conectar_app()
    try:
        data = request.get_json()
        caminho = data.get("caminho_impressora", "")
        cursor = conn.cursor()
        # Deleta anterior e insere novo, para garantir sempre só 1 registro
        cursor.execute("DELETE FROM impressora")
        cursor.execute(
            """INSERT INTO impressora (caminho_impressora)
                       VALUES (%s)""",
            (caminho,),
        )
        conn.commit()
        return jsonify({"sucesso": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


@app.route("/base")
def base():
    return render_template("layout_base.html")


@app.route("/dashboard_partial")
def dashboard_partial():
    return render_template("dashboard_partial.html")


@app.route("/api/produtos/busca_descricao", methods=["POST"])
def buscar_produtos_por_descricao():
    data = request.get_json() or {}
    produtos = buscar_produtos(data.get("termo"))
    return jsonify(produtos)


@app.route("/api/produtos_kds_horario", methods=["GET", "POST", "DELETE"])
def api_produtos_kds_horario():
    conn_app = conectar_app()
    conn_vr = conectar_vr()
    cursor_app = conn_app.cursor()
    cursor_vr = conn_vr.cursor()

    if request.method == "POST":
        data = request.get_json()
        id_produto = data.get("id_produto")
        cursor_app.execute(
            "INSERT INTO produto_exibir_horario (id_produto) VALUES (%s)", (id_produto,)
        )
        conn_app.commit()
        return jsonify({"success": True})

    elif request.method == "DELETE":
        data = request.get_json()
        id_produto = data.get("id_produto")
        cursor_app.execute(
            """DELETE FROM produto_exibir_horario
            WHERE id_produto = %s""",
            (id_produto,),
        )
        conn_app.commit()
        return jsonify({"success": True})

    elif request.method == "GET":
        cursor_app.execute("SELECT id_produto FROM produto_exibir_horario")
        ids = cursor_app.fetchall()
        if not ids:
            return jsonify([])

        id_list = [str(row[0]) for row in ids]
        query = f"""
            SELECT id, descricaocompleta
            FROM produto
            WHERE id IN ({','.join(['%s']*len(id_list))})
        """
        cursor_vr.execute(query, tuple(id_list))
        produtos = cursor_vr.fetchall()

        resultado = [{"id_produto": row[0], "nome": row[1]} for row in produtos]
        return jsonify(resultado)


@app.route("/api/produtos_ocultar_horario")
def api_produtos_ocultar_horario():
    conn = conectar_app()
    cursor = conn.cursor()
    cursor.execute("SELECT id_produto FROM produto_exibir_horario")
    rows = cursor.fetchall()
    ids = [r[0] for r in rows]
    return jsonify(ids)


@app.route("/api/usuarios/consulta", methods=["POST"])
def api_usuarios_consulta():
    try:
        dados = request.get_json() or {}

        filtro = dados.get("filtro", "")

        usuarios = consultar_usuarios(filtro)

        return jsonify(usuarios)

    except Exception as e:
        return jsonify({
            "erro": str(e)
        }), 500


@app.route("/api/usuarios/<int:id_usuario>", methods=["GET"])
def api_usuario_get(id_usuario):
    try:
        usuario = buscar_usuario(id_usuario)

        return jsonify(usuario)

    except ValueError as e:
        return jsonify({
            "erro": str(e)
        }), 400

    except LookupError as e:
        return jsonify({
            "erro": str(e)
        }), 404

    except Exception as e:
        return jsonify({
            "erro": str(e)
        }), 500


@app.route("/api/usuarios/novo", methods=["POST"])
def api_usuario_novo():
    try:
        dados = request.get_json() or {}

        id_usuario = criar_usuario(dados)

        return jsonify({
            "ok": True,
            "id": id_usuario,
        }), 201

    except ValueError as e:
        return jsonify({
            "erro": str(e)
        }), 400

    except Exception as e:
        return jsonify({
            "erro": str(e)
        }), 500


@app.route(
    "/api/usuarios/editar/<int:id_usuario>",
    methods=["PUT"],
)
def api_usuario_editar(id_usuario):
    try:
        dados = request.get_json() or {}

        editar_usuario(
            id_usuario,
            dados,
        )

        return jsonify({
            "ok": True
        })

    except ValueError as e:
        return jsonify({
            "erro": str(e)
        }), 400

    except LookupError as e:
        return jsonify({
            "erro": str(e)
        }), 404

    except Exception as e:
        return jsonify({
            "erro": str(e)
        }), 500


# GET /api/impressora/setor?loja=1&setor=2
@app.route("/api/impressora/setor", methods=["GET"])
def api_impressora_por_setor_get():
    id_loja = request.args.get("loja", type=int)
    setor_qs = request.args.get("setor", default=None)  # pode vir "", None ou "123"
    if setor_qs and setor_qs.strip().isdigit():
        id_setor = int(setor_qs)
    else:
        id_setor = None

    if not id_loja:
        return jsonify({"erro": "Parâmetro 'loja' é obrigatório"}), 400

    conn = conectar_app()
    try:
        cur = conn.cursor()
        if id_setor is None:
            cur.execute(
                """
                SELECT id, caminho_impressora
                  FROM impressora
                 WHERE id_loja = %s AND id_setor IS NULL
                 LIMIT 1
            """,
                (id_loja,),
            )
        else:
            cur.execute(
                """
                SELECT id, caminho_impressora
                  FROM impressora
                 WHERE id_loja = %s AND id_setor = %s
                 LIMIT 1
            """,
                (id_loja, id_setor),
            )

        row = cur.fetchone()
        return jsonify(
            {
                "id": row[0] if row else None,
                "id_loja": id_loja,
                "id_setor": id_setor,  # pode ser None
                "caminho_impressora": row[1] if row else "",
            }
        )
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


# POST /api/impressora/setor  body: {id_loja, id_setor, caminho_impressora}
@app.route("/api/impressora/setor", methods=["POST"])
def api_impressora_por_setor_post():
    try:
        dados = request.get_json() or {}

        acao = salvar_impressora_setor(dados)

        return jsonify({
            "ok": True,
            "acao": acao,
        })

    except ValueError as e:
        return jsonify({
            "erro": str(e)
        }), 400

    except Exception as e:
        return jsonify({
            "erro": str(e)
        }), 500


def _montar_texto_impressao_kds(titulo, itens):
    # itens: [{produto, observacao, quantidade_formatada}]
    linhas = []
    linhas.append(f"*** {titulo} ***")
    for it in itens:
        linhas.append(f"{it['produto']}")
        if it.get("observacao"):
            linhas.append(f"OBS: {it['observacao']}")
        linhas.append(f"QTD: {it['quantidade_formatada']}")
        linhas.append("-" * 32)
    linhas.append("\n\n")
    return "\r\n".join(linhas)


def _enviar_para_impressora_kds(caminho, conteudo):
    return True, ""


@app.route("/api/kds/imprimir", methods=["POST"])
def api_kds_imprimir_coluna():
    data = request.get_json() or {}
    id_loja = int(data.get("id_loja") or 0)
    id_setor = int(data.get("id_setor") or 0)
    coluna = data.get("coluna")  # aguardando | producao
    itens = data.get("itens") or []

    if not (
        id_loja
        and id_setor
        and coluna in ("aguardando", "producao")
        and isinstance(itens, list)
        and itens
    ):
        return jsonify({"erro": "Dados inválidos"}), 400

    # Busca caminho por loja/setor
    conn = conectar_app()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT caminho_impressora
              FROM impressora
             WHERE id_loja = %s AND id_setor = %s
             LIMIT 1
        """,
            (id_loja, id_setor),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row or not row[0]:
        return (
            jsonify({"erro": """Impressora não configurada
                        para esta Loja/Setor"""}),
            404,
        )

    titulo = f"""KDS - Setor {id_setor}
    - {'AGUARDANDO' if coluna == 'aguardando' else 'EM PRODUÇÃO'}"""
    texto = _montar_texto_impressao_kds(titulo, itens)
    ok, msg = _enviar_para_impressora_kds(row[0], texto)
    if not ok:
        return jsonify({"erro": f"Falha ao imprimir: {msg}"}), 500
    return jsonify({"ok": True})
