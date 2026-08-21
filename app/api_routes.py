# app/api_routes.py

from flask import (
        request,
        render_template,
        jsonify,
        redirect,
        url_for,
        )
from app.repo.produto_composto import (
        repo_get_itens_fixos,
        repo_get_produto_detalhe,
        repo_get_grupos_opcionais,
        repo_get_composto_estrutura
        )
from app.services.produto_composto import (
        montar_itens,
        calcular_componentes,
        svc_get_calculos_pessoa,
        svc_get_produtos_compostos,
        svc_salvar_produtos_compostos,
        svc_remover_produtos_compostos,
        )
from app import app
from app.conexao_vr import buscar_clientes, conectar_vr
from app.conexao_app import conectar_app
from app import bcrypt
from decimal import Decimal, InvalidOperation
import logging


logger = logging.getLogger("api.api_routes")


@app.route("/api/clientes")
def api_clientes():
    try:
        clientes = buscar_clientes()
        clientes_formatados = []
        for c in clientes:
            clientes_formatados.append({
                "id": c[0],
                "nome": c[1],
                "telefone": c[2],
                "endereco": f"{c[3]}, {c[4]} - {c[5]}",
                "observacao": c[6],
                "cidade": c[7],
                "estado": c[8]
            })
        return jsonify(clientes_formatados)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/produtos")
def api_produtos():
    try:
        somente_ativos = request.args.get('ativos') in ('1', 'true', 'True')
        id_loja = request.args.get('id_loja', type=int)

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

        produtos_formatados = [{
            "id_produto": r[0],
            "descricaocompleta": r[1],
            "pesobruto": r[2],
            "tipoembalagem": r[3],
            "setor": r[4]
        } for r in rows]

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


@app.route('/api/pedido/salvar', methods=['POST'])
def salvar_pedido():
    data = request.get_json()
    conn = conectar_app()
    if not conn:
        return jsonify({'erro': 'Erro ao conectar ao banco de dados'}), 500
    try:
        cursor = conn.cursor()
        id_pedido = data.get('id_pedido')
        novo_pedido = False
        if id_pedido:
            cursor.execute("""SELECT id FROM pedidos
                           WHERE id = %s""", (id_pedido,))
            pedido_existente = cursor.fetchone()
            if pedido_existente:
                # Atualiza pedido existente
                cursor.execute("""
                    UPDATE pedidos SET
                        id_cliente = %s,
                        id_loja = %s,
                        data_entrega = %s,
                        hora_entrega = %s,
                        telefone = %s,
                        observacoes = %s,
                        tipo_entrega = %s
                    WHERE id = %s
                """, (
                    data['id_cliente'],
                    data['id_loja'],
                    data['data_entrega'],
                    data['hora_entrega'],
                    data['telefone'],
                    data['observacoes'],
                    data['tipo_entrega'],
                    id_pedido
                ))
                cursor.execute("""DELETE FROM pedido_itens
                               WHERE id_pedido = %s", (id_pedido,)""")
            else:
                novo_pedido = True
        else:
            novo_pedido = True
        if novo_pedido:
            cursor.execute("""
                INSERT INTO pedidos (id_cliente, id_loja, data_entrega,
                hora_entrega, telefone, observacoes, tipo_entrega, id_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                data['id_cliente'],
                data['id_loja'],
                data['data_entrega'],
                data['hora_entrega'],
                data['telefone'],
                data['observacoes'],
                data['tipo_entrega'],
                data.get('id_status', None)
            ))
            id_pedido = cursor.fetchone()[0]
        for item in data['itens']:
            preco_venda_raw = item.get('valor_unitario', 0)
            if isinstance(preco_venda_raw, str):
                if preco_venda_raw:
                    preco_venda_raw = float(preco_venda_raw.replace(',', '.'))
                else:
                    preco_venda_raw = 0
            else:
                preco_venda = float(preco_venda_raw)
            peso_bruto = float(item.get('peso_bruto', '0').replace(',', '.')) if item.get('peso_bruto') else 0
            quantidade_raw = item.get('quantidade')
            quantidade = float(quantidade_raw.replace(',', '.')) if quantidade_raw else 0
            quantidade_un = float(item.get('quantidade_un', '0').replace(',', '.')) if item.get('quantidade_un') else 0
            id_setor = int(item.get('id_setor', 0)) if item.get('id_setor') else 0

            print('🧪 DEBUG INSERT VALORES:', (
                id_pedido,
                item.get('cod_produto'),
                id_setor,
                quantidade,
                quantidade_un,
                peso_bruto,
                preco_venda,
                item.get('observacao'),
                item.get('cod_produto_associado') or None,
                0
            ))

            cursor.execute("""
                INSERT INTO pedido_itens (
                    id_pedido, id_produto, id_setor, quantidade,
                    quantidade_un, peso, valor_unitario, observacao,
                    id_produto_associado, id_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                id_pedido,
                item.get('cod_produto'),
                id_setor,
                quantidade,
                quantidade_un,
                peso_bruto,
                preco_venda,
                item.get('observacao'),
                item.get('cod_produto_associado') or None,
                0
            ))

        conn.commit()
        return jsonify({"success": True})

    except Exception as e:
        print('❌ Erro ao salvar pedido:', e)
        conn.rollback()
        return jsonify({"erro": str(e)}), 500

    finally:
        conn.close()


@app.route('/api/preco/<int:id_produto>/<int:id_loja>')
def api_preco_produto(id_produto, id_loja):
    try:
        conn = conectar_vr()
        cursor = conn.cursor()

        # Buscar preco_venda
        cursor.execute("""
            SELECT precovenda
            FROM produtocomplemento
            WHERE id_produto = %s AND id_loja = %s
            LIMIT 1
        """, (id_produto, id_loja))
        preco_row = cursor.fetchone()

        if preco_row:
            preco_venda = float(preco_row[0]) if preco_row[0] is not None else 0
        else:
            preco_venda = 0

        # Buscar id_setor + descricao do setor
        cursor.execute("""
            SELECT s.id, s.descricao
            FROM ficha.setorproduto sp
            INNER JOIN ficha.setor s ON s.id = sp.id_setor
            WHERE sp.id_produto = %s
            AND s.id_loja = %s
            LIMIT 1
        """, (id_produto, id_loja))
        setor_row = cursor.fetchone()

        if setor_row:
            id_setor = setor_row[0]
            descricao_setor = setor_row[1]
        else:
            id_setor = None
            descricao_setor = ''

        return jsonify({
            "precovenda": preco_venda,
            "id_setor": id_setor,
            "descricao_setor": descricao_setor
        })

    except Exception as e:
        print('Erro ao buscar preço e setor:', str(e))
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/pedido/<int:id>", methods=["GET"])
def buscar_pedido_edicao(id):
    conn_app = conectar_app()  # Banco de encomendas
    conn_vr = conectar_vr()    # Banco da VR

    if not conn_app or not conn_vr:
        return jsonify({"erro": "Erro de conexão"}), 500

    try:
        cursor_app = conn_app.cursor()
        cursor_vr = conn_vr.cursor()

        # Buscar dados do pedido (agora incluindo id_status)
        cursor_app.execute("""
            SELECT id_cliente, id_loja, data_entrega, hora_entrega, telefone, observacoes, tipo_entrega, id_status
            FROM pedidos
            WHERE id = %s
        """, (id,))
        pedido_row = cursor_app.fetchone()

        if not pedido_row:
            return jsonify({"erro": "Pedido não encontrado"}), 404

        id_cliente = pedido_row[0]
        id_loja = pedido_row[1]

        # Buscar dados do cliente
        cursor_vr.execute("""
            SELECT 
                fc.nome,
                fct.telefone,
                CONCAT(fc.endereco, ', ', fc.numero, ', ', fc.bairro, ', ', m.descricao, ' - ', e.descricao) AS endereco_completo,
                fc.observacao
            FROM food.cliente AS fc
            INNER JOIN public.municipio AS m ON m.id = fc.id_municipio
            INNER JOIN public.estado AS e ON e.id = m.id_estado
            INNER JOIN food.clientetelefone AS fct ON fct.id_cliente = fc.id
            WHERE fc.id = %s
            LIMIT 1
        """, (id_cliente,))
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
            "data_entrega": pedido_row[2].isoformat() if pedido_row[2] else None,
            "hora_entrega": pedido_row[3].strftime('%H:%M') if pedido_row[3] else None,
            "observacoes": pedido_row[5],
            "itens": []
        }

        # Buscar os itens do pedido
        cursor_app.execute("""
            SELECT id_produto, quantidade, quantidade_un, peso, valor_unitario, observacao, id_produto_associado
            FROM pedido_itens
            WHERE id_pedido = %s
        """, (id,))
        itens = cursor_app.fetchall()

        for item in itens:
            id_produto = item[0]
            id_produto_associado = item[6] if len(item) > 6 else None
        
            # Buscar dados do produto
            cursor_vr.execute("""
                SELECT 
                    p.descricaocompleta,
                    te.descricao AS tipo_embalagem
                FROM public.produto p
                LEFT JOIN public.tipoembalagem te ON te.id = p.id_tipoembalagem
                WHERE p.id = %s
                LIMIT 1
            """, (id_produto,))
            produto_row = cursor_vr.fetchone()
        
            descricao = produto_row[0] if produto_row else ""
            tipo_embalagem = produto_row[1] if produto_row and produto_row[1] else ""
        
            # Buscar descrição do associado
            desc_produto_associado = ""
            if id_produto_associado:
                cursor_vr.execute("""
                    SELECT descricaocompleta
                    FROM produto
                    WHERE id = %s
                    LIMIT 1
                """, (id_produto_associado,))
                associado_row = cursor_vr.fetchone()
                desc_produto_associado = associado_row[0] if associado_row else ""
        
            # SEMPRE buscar setor do produto (considerando a loja)
            produto_setor = id_produto_associado if id_produto_associado else id_produto
            cursor_vr.execute("""
                SELECT s.descricao,s.id
                FROM ficha.setorproduto si
                INNER JOIN ficha.setor s ON s.id = si.id_setor
                WHERE si.id_produto = %s AND s.id_loja = %s
                LIMIT 1
            """, (produto_setor, id_loja))
            setor_row = cursor_vr.fetchone()
            setor = setor_row[0] if setor_row else ""
            id_setor = setor_row[1] if setor_row else None
            # Montar o item
            pedido["itens"].append({
                "cod_produto": id_produto,
                "descricao": descricao,
                "tipo_embalagem": tipo_embalagem,
                "peso_bruto": item[3],
                "setor": setor,
                "id_setor": id_setor,
                "quantidade": item[1],
                "quantidade_un": item[2],
                "preco_venda": item[4],
                "total": round(float(item[1]) * float(item[4]), 2) if item[1] and item[4] else 0,
                "observacao": item[5],
                "cod_produto_associado": id_produto_associado or "",
                "desc_produto_associado": desc_produto_associado
            })

        return jsonify(pedido)

    except Exception as e:
        print(f'ERRO AO CARREGAR PEDIDO: {e}')
        import traceback; traceback.print_exc()
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()
        conn_vr.close()

# --- ROTAS HTML ---
@app.route('/api/pedidos/consulta', methods=['POST'])
def api_pedidos_consulta():
    conn_app = conectar_app()  # Banco do APP
    conn_vr = conectar_vr()    # Banco da VR (para buscar nome do cliente e loja)

    if not conn_app or not conn_vr:
        return jsonify({'erro': 'Erro ao conectar ao banco de dados'}), 500

    try:
        dados = request.get_json()

        data_tipo = dados.get('data_tipo', 'data_pedido')  # 'data_pedido' ou 'data_entrega'
        if data_tipo == "data_pedido":
            data_tipo = "criado_em"
        elif data_tipo == "data_entrega":
            data_tipo = "data_entrega"
        data_inicio = dados.get('data_inicio')
        data_fim = dados.get('data_fim')
        tipo_entrega = dados.get('tipo_entrega')
        id_loja = dados.get('id_loja')
        id_cliente = dados.get('id_cliente')
        status = dados.get('status')

        cursor_app = conn_app.cursor()
        cursor_vr = conn_vr.cursor()

        filtros = []
        params = []
        # Converter campo de data para o nome correto da coluna
        data_tipo = dados.get('data_tipo', 'data_pedido')
        if data_tipo == 'data_pedido':
            data_tipo = 'criado_em'
        elif data_tipo == 'data_entrega':
            data_tipo = 'data_entrega'
        num_pedido = dados.get('num_pedido')
        if num_pedido:
            filtros.append("p.id = %s")
            params.append(num_pedido)    
        
        # FILTRO POR DATA
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

        cursor_app.execute(f"""
            SELECT 
                p.id,
                p.id_cliente,
                p.criado_em::date AS data_pedido,
                p.data_entrega,
                p.tipo_entrega,
                p.id_loja,
                p.id_status,
                COALESCE(SUM(pi.quantidade * pi.valor_unitario), 0) AS valor_total
            FROM pedidos p
            LEFT JOIN pedido_itens pi ON pi.id_pedido = p.id
            {where_clause}
            GROUP BY p.id, p.id_cliente, p.criado_em, p.data_entrega, p.tipo_entrega, p.id_loja, p.id_status
            ORDER BY p.criado_em DESC
        """, params)

        pedidos = []
        for row in cursor_app.fetchall():
            id_cliente = row[1]
            id_loja = row[5]
            id_status = row[6]

            # Buscar nome do cliente
            cursor_vr.execute("""
                SELECT nome
                FROM food.cliente
                WHERE id = %s
                LIMIT 1
            """, (id_cliente,))
            cliente_row = cursor_vr.fetchone()
            nome_cliente = cliente_row[0] if cliente_row else "Cliente não encontrado"

            # Buscar nome da loja
            cursor_vr.execute("""
                SELECT descricao
                FROM loja
                WHERE id = %s
                LIMIT 1
            """, (id_loja,))
            loja_row = cursor_vr.fetchone()
            nome_loja = loja_row[0] if loja_row else "Loja não encontrada"

            # Buscar descrição do status
            descricao_status = "-"
            if id_status is not None:
                cursor_app.execute("""
                    SELECT descricao
                    FROM status
                    WHERE id = %s
                    LIMIT 1
                """, (id_status,))
                status_row = cursor_app.fetchone()
                if status_row:
                    descricao_status = status_row[0]

            pedidos.append({
                "id": row[0],
                "cod_cliente": id_cliente,
                "nome_cliente": nome_cliente,
                "data_pedido": row[2].isoformat() if row[2] else None,
                "data_entrega": row[3].isoformat() if row[3] else None,
                "tipo_entrega": row[4],
                "nome_loja": nome_loja,
                "status": descricao_status,
                "status_id": id_status,
                "valor_total": float(row[7])
            })

        return jsonify(pedidos)

    except Exception as e:
        print('Erro ao buscar pedidos:', e)
        return jsonify({'erro': str(e)}), 500

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
        GROUP BY pi.id_produto, pi.observacao, pe.id_status, pe.id_loja, pi.id_setor
        ORDER BY pi.id_produto
    """

    cur_app.execute(query_app, (id_setor, id_loja))
    produtos_app = cur_app.fetchall()
    print(f"DEBUG -> id_setor: {id_setor}, id_loja: {id_loja}")
    cur_app.close()
    conn_app.close()

    if not produtos_app:
        return jsonify([])

    # Buscar descrições dos produtos no VR
    ids_produtos = [str(produto[0]) for produto in produtos_app if produto[0] is not None]

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

        descricao = map_descricoes.get(id_produto, 'Produto sem descrição')

        resultado.append({
            "id_produto": id_produto,
            "descricao": descricao,
            "quantidade_un": int(quantidade_un),
            "observacao": observacao,
            "id_status": id_status
        })

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


@app.route('/api/dashboard/indicadores')
def dashboard_indicadores():
    id_loja = request.args.get('id_loja', default=None, type=int)
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
        cursor.execute(f"SELECT COUNT(*) FROM pedidos WHERE id_status = 1 {'AND id_loja = %s' if id_loja else ''}", params)
        pedidos_producao = cursor.fetchone()[0]

        # Pedidos por setor
        cursor.execute(f"""
            SELECT COUNT(DISTINCT id_setor)
            FROM pedido_itens
            {"WHERE id_pedido IN (SELECT id FROM pedidos WHERE id_loja = %s)" if id_loja else ""}
        """, params)
        pedidos_setor = cursor.fetchone()[0]

        # Pedidos de entrega hoje
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM pedidos
            WHERE tipo_entrega = 'entrega' 
            AND data_entrega = CURRENT_DATE
            {'AND id_loja = %s' if id_loja else ''}
        """, params)
        pedidos_entrega = cursor.fetchone()[0]

        # Pedidos de retirada hoje
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM pedidos
            WHERE tipo_entrega = 'retirada' 
            AND data_entrega = CURRENT_DATE
            {'AND id_loja = %s' if id_loja else ''}
        """, params)
        pedidos_retirada = cursor.fetchone()[0]

        return jsonify({
            "total_pedidos": total_pedidos,
            "pedidos_producao": pedidos_producao,
            "pedidos_setor": pedidos_setor,
            "pedidos_entrega": pedidos_entrega,
            "pedidos_retirada": pedidos_retirada
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


@app.route('/pedidos/consulta')
def consulta_pedidos():
    return render_template('consulta_pedidos.html',
                           titulo_tela="Consulta de Pedidos")


@app.route('/produto_horario')
def produto_horario():
    return render_template('produto_horario.html',
                           titulo_tela="Exibir Horário KDS")


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
    
    try:
        filtros = request.get_json() or {}

        # mapeia o seletor do front para o nome da coluna
        data_tipo = filtros.get('data_tipo', 'data_pedido')
        if data_tipo == "data_pedido":
            data_tipo = "criado_em"
        elif data_tipo == "data_entrega":
            data_tipo = "data_entrega"

        data_inicio   = filtros.get('data_inicio')
        data_fim      = filtros.get('data_fim')
        tipo_entrega  = filtros.get('tipo_entrega')
        id_loja       = filtros.get('id_loja')
        id_cliente    = filtros.get('id_cliente')
        id_status     = filtros.get('status')
        impresso      = filtros.get('impresso')       # "", "1" ou "0"
        num_pedido    = filtros.get('num_pedido')     # << NOVO

        # saneia num_pedido (aceita string ou int)
        if isinstance(num_pedido, str):
            num_pedido = num_pedido.strip() or None
        if num_pedido is not None:
            try:
                num_pedido = int(num_pedido)
            except ValueError:
                num_pedido = None  # se vier lixo, ignora

        cursor_app = conn_app.cursor()
        cursor_vr  = conn_vr.cursor()

        where  = ["1=1"]
        params = []

        # filtro impresso
        if impresso == "1":
            where.append("p.impresso = TRUE")
        elif impresso == "0":
            where.append("p.impresso = FALSE")

        # Nº do pedido — quando enviado, não aplica filtro de datas
        if num_pedido:
            where.append("p.id = %s")
            params.append(num_pedido)
        else:
            # filtros de data (somente quando num_pedido NÃO foi enviado)
            if data_inicio and data_fim:
                where.append(f"CAST(p.{data_tipo} AS DATE) BETWEEN %s AND %s")
                params.extend([data_inicio, data_fim])
            elif data_inicio and not data_fim:
                where.append(f"CAST(p.{data_tipo} AS DATE) = %s")
                params.append(data_inicio)
            elif data_fim and not data_inicio:
                where.append(f"CAST(p.{data_tipo} AS DATE) = %s")
                params.append(data_fim)

        if tipo_entrega:
            where.append("p.tipo_entrega = %s")
            params.append(tipo_entrega)

        if id_loja:
            where.append("p.id_loja = %s")
            params.append(id_loja)

        if id_status:
            where.append("p.id_status = %s")
            params.append(id_status)
        else:
            where.append("p.id_status NOT IN (5, 7)")

        if id_cliente:
            where.append("p.id_cliente = %s")
            params.append(id_cliente)

        sql = f"""
            SELECT p.id, p.id_cliente, p.id_loja, p.criado_em, p.data_entrega, p.hora_entrega,
                   p.tipo_entrega, p.observacoes, p.id_status, p.impresso, p.data_finalizacao
            FROM pedidos p
            WHERE {" AND ".join(where)}
            ORDER BY p.data_entrega ASC
        """

        cursor_app.execute(sql, tuple(params))
        pedidos_rows = cursor_app.fetchall()

        pedidos = []
        for row in pedidos_rows:
            id_pedido  = row[0]
            id_cliente = row[1]
            id_loja    = row[2]
            impresso_b = row[9]

            # Cliente
            cursor_vr.execute("""
                SELECT fc.nome, fct.telefone,
                       CONCAT(fc.endereco, ', ', fc.numero, ', ', fc.bairro, ', ', m.descricao, ' - ', e.descricao) AS endereco_completo
                FROM food.cliente fc
                INNER JOIN public.municipio m ON m.id = fc.id_municipio
                INNER JOIN public.estado e ON e.id = m.id_estado
                LEFT JOIN food.clientetelefone fct ON fct.id_cliente = fc.id
                WHERE fc.id = %s
                LIMIT 1
            """, (id_cliente,))
            cliente_row       = cursor_vr.fetchone()
            nome_cliente      = cliente_row[0] if cliente_row else "Cliente não encontrado"
            telefone_cliente  = cliente_row[1] if cliente_row else ""
            endereco_cliente  = cliente_row[2] if cliente_row else ""

            # Loja
            cursor_vr.execute("SELECT descricao FROM loja WHERE id = %s", (id_loja,))
            loja_row  = cursor_vr.fetchone()
            nome_loja = loja_row[0] if loja_row else ""

            # Status
            cursor_app.execute("SELECT descricao FROM status WHERE id = %s", (row[8],))
            status_row       = cursor_app.fetchone()
            status_descricao = status_row[0] if status_row else ""

            # Total
            cursor_app.execute("""
                SELECT COALESCE(SUM(quantidade * valor_unitario), 0)
                FROM pedido_itens
                WHERE id_pedido = %s
            """, (id_pedido,))
            valor_total_row = cursor_app.fetchone()
            valor_total     = float(valor_total_row[0]) if valor_total_row else 0.0

            # Itens (com produto associado)
            cursor_app.execute("""
                SELECT id_produto, quantidade, quantidade_un, observacao, id_produto_associado
                FROM pedido_itens
                WHERE id_pedido = %s
            """, (id_pedido,))
            itens_rows = cursor_app.fetchall()

            itens = []
            for id_produto, _, qtd_un, observacao, id_associado in itens_rows:
                # principal
                cursor_vr.execute("SELECT descricaocompleta FROM produto WHERE id = %s", (id_produto,))
                prod_row      = cursor_vr.fetchone()
                desc_princ    = prod_row[0] if prod_row else ""
                # associado (se houver)
                desc_assoc = ""
                if id_associado:
                    cursor_vr.execute("SELECT descricaocompleta FROM produto WHERE id = %s", (id_associado,))
                    assoc_row  = cursor_vr.fetchone()
                    desc_assoc = assoc_row[0] if assoc_row else ""

                itens.append({
                    "descricao": desc_princ,
                    "desc_produto_associado": desc_assoc,
                    "cod_produto_associado": id_associado or "",
                    "quantidade_un": qtd_un,
                    "observacao": observacao or ""
                })

            pedidos.append({
                "id": id_pedido,
                "nome_cliente": nome_cliente,
                "telefone": telefone_cliente,
                "endereco": endereco_cliente,
                "tipo_entrega": row[6],
                "observacoes": row[7],
                "data_pedido": row[3].isoformat() if row[3] else "",
                "data_entrega": row[4].isoformat() if row[4] else "",
                "hora_entrega": row[5].strftime('%H:%M') if row[5] else "",
                "id_status": row[8],
                "status_descricao": status_descricao,
                "valor_total": valor_total,
                "nome_loja": nome_loja,
                "itens": itens,
                "impresso": impresso_b,
                "data_finalizacao": row[10].isoformat() if row[10] else None
            })

        return jsonify(pedidos)

    except Exception as e:
        print("Erro na consulta de encomendas:", str(e))
        return jsonify({"erro": str(e)}), 500
    finally:
        conn_app.close()
        conn_vr.close()



@app.route("/api/encomenda/status", methods=["POST"])
def api_encomenda_status():
    conn_app = conectar_app()  # Banco de encomendas

    if not conn_app:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    try:
        dados = request.get_json()
        id_pedido = dados.get('id_pedido')
        id_status = dados.get('id_status')

        if not id_pedido or not id_status:
            return jsonify({"erro": "Dados incompletos"}), 400

        cursor = conn_app.cursor()

        cursor.execute("""
            UPDATE pedidos
            SET id_status = %s
            WHERE id = %s
        """, (id_status, id_pedido))

        conn_app.commit()

        return jsonify({"mensagem": "Status atualizado com sucesso"})

    except Exception as e:
        print("Erro ao atualizar status:", str(e))
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
        id_pedido = dados.get('id_pedido')
        itens = dados.get('itens', [])

        if not id_pedido or not itens:
            return jsonify({"erro": "Dados incompletos"}), 400

        cursor = conn_app.cursor()

        # Exclui todos os itens antigos do pedido
        cursor.execute("DELETE FROM pedido_itens WHERE id_pedido = %s", (id_pedido,))

        # Insere todos os itens recebidos
        for item in itens:
            cod_produto = item.get('cod_produto')
            quantidade = item.get('quantidade')
            quantidade_un = item.get('quantidade_un')
            observacao = item.get('observacao', '')
            # Adicione outros campos conforme necessário
            
            id_setor = int(item.get('id_setor') or 0) 
            cursor.execute("""
                INSERT INTO pedido_itens (
                id_pedido, id_produto, id_setor, quantidade, quantidade_un,
                peso, valor_unitario, observacao, id_produto_associado, id_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
             """, (
                id_pedido,
                item.get('cod_produto'),
                item.get('id_setor'),
                item.get('quantidade'),
                item.get('quantidade_un'),
                item.get('peso_bruto') or 0,
                item.get('preco_venda') or 0,
                item.get('observacao'),
                item.get('cod_produto_associado') or None
            ))

        conn_app.commit()
        return jsonify({"mensagem": "Itens atualizados com sucesso"})

    except Exception as e:
        print("Erro ao editar itens:", str(e))
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()


@app.route("/api/encomenda/finalizar", methods=["POST"])
def api_finalizar_encomenda():
    data = request.get_json()
    id_pedido = data.get('id_pedido')
    numero_ficha = data.get('numero_ficha')
    itens_editados = data.get('itens', [])

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
            cursor_app.execute("""
                UPDATE pedido_itens
                SET quantidade = %s, quantidade_un = %s
                WHERE id_pedido = %s AND id_produto = %s
            """, (quantidade, quantidade_un, id_pedido, cod_produto))
        conn_app.commit()

        # Buscar id_loja do pedido
        cursor_app.execute("SELECT id_loja FROM pedidos WHERE id = %s", (id_pedido,))
        loja_row = cursor_app.fetchone()
        id_loja = loja_row[0] if loja_row else None

        if not id_loja:
            return jsonify({"erro": "ID da loja não encontrado para o pedido."}), 400

        # Verifica se já existe uma ficha com o mesmo número e loja
        cursor_vr.execute("SELECT id FROM pdv.ficha WHERE numeroficha = %s AND id_loja = %s", (numero_ficha, id_loja))
        row = cursor_vr.fetchone()

        if row:
            id_ficha = row[0]

            # Atualiza a ficha existente
            cursor_vr.execute("""
                UPDATE pdv.ficha
                SET data = CURRENT_DATE, datahora = NOW(), numeroficha = %s
                WHERE id = %s
            """, (numero_ficha, id_ficha))

            # Remove os itens anteriores
            cursor_vr.execute("DELETE FROM pdv.fichaitem WHERE id_ficha = %s", (id_ficha,))
        else:
            # Gera novo ID para ficha
            cursor_vr.execute("SELECT nextval('ficha.ficha_id_seq')")
            id_ficha = cursor_vr.fetchone()[0]

            # Insere nova ficha
            cursor_vr.execute("""
                INSERT INTO pdv.ficha (
                    id, id_loja, numeroficha, data, datahora, id_mesa, cliente
                )
                VALUES (%s, %s, %s, CURRENT_DATE, NOW(), %s, %s)
            """, (id_ficha, id_loja, numero_ficha, 1, None))

        # Buscar os itens atualizados do pedido
        cursor_app.execute("""
            SELECT id_produto, quantidade, valor_unitario
            FROM pedido_itens
            WHERE id_pedido = %s
        """, (id_pedido,))
        itens_pedido = cursor_app.fetchall()

        # Inserir itens na pdv.fichaitem
        sequencia = 1
        for item in itens_pedido:
            id_produto, quantidade, valor_unitario = item
            if quantidade == 0:
                continue

            # Buscar codigobarras
            cursor_vr.execute("""
                SELECT codigobarras
                FROM produtoautomacao
                WHERE id_produto = %s
                LIMIT 1
            """, (id_produto,))
            codigo_barras_row = cursor_vr.fetchone()
            codigobarras = codigo_barras_row[0] if codigo_barras_row else None

            # Gerar novo ID para fichaitem
            cursor_vr.execute("SELECT nextval('ficha.fichaitem_id_seq')")
            id_fichaitem = cursor_vr.fetchone()[0]
            if valor_unitario > 0:
                cursor_vr.execute("""
                    INSERT INTO pdv.fichaitem (
                        id, id_ficha, sequencia, codigobarras, quantidade,
                        precovenda, id_atendente, iscancelado, isimpresso
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_fichaitem, id_ficha, sequencia, codigobarras,
                    quantidade, valor_unitario, -1, False, False
                ))

                sequencia += 1

        conn_vr.commit()

        # Atualiza o status do pedido
        cursor_app.execute("""
            UPDATE pedidos
               SET id_status = 7,
                   data_finalizacao = NOW(),
                   tipo_finalizacao = 'vrficha'
             WHERE id = %s;
        """, (id_pedido,))
        conn_app.commit()

        return jsonify({"mensagem": "Pedido finalizado com sucesso."})

    except Exception as e:
        print("Erro ao finalizar pedido:", str(e))
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()
        conn_vr.close()


def _to_decimal(val):
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    s = str(val).strip()
    # aceita "1.234,56" e "1234,56"
    s = s.replace('.', '').replace(',', '.')
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

@app.route("/api/encomenda/finalizar_vrfood", methods=["POST"])
def api_finalizar_encomenda_vrfood():
    data = request.get_json()
    id_pedido = data.get('id_pedido')
    itens_editados = data.get('itens', [])

    conn_app = conectar_app()
    conn_vr  = conectar_vr()
    if not conn_app or not conn_vr:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    try:
        cur_app = conn_app.cursor()
        cur_vr  = conn_vr.cursor()

        # 1) Atualiza itens no sistema de encomendas (usa quantidade do modal/etiqueta)
        for item in itens_editados:
            cod_produto = item.get("cod_produto")
            qtd_modal   = _to_decimal(item.get("quantidade")) or Decimal('0')
            qtd_un      = _to_decimal(item.get("quantidade_un")) or Decimal('0')

            cur_app.execute("""
                UPDATE pedido_itens
                   SET quantidade   = %s,
                       quantidade_un = %s
                 WHERE id_pedido    = %s
                   AND id_produto   = %s
            """, (qtd_modal, qtd_un, id_pedido, cod_produto))
        conn_app.commit()

        # 2) Dados do pedido (loja/cliente)
        cur_app.execute("SELECT id_loja, id_cliente FROM pedidos WHERE id = %s", (id_pedido,))
        row = cur_app.fetchone()
        if not row:
            return jsonify({"erro": "Pedido não encontrado."}), 400
        id_loja, id_cliente = row

        codigo_pedido = int(id_pedido)

        # Itens já atualizados
        cur_app.execute("""
            SELECT id_produto, quantidade, valor_unitario, COALESCE(observacao,''), id_setor
              FROM pedido_itens
             WHERE id_pedido = %s
        """, (id_pedido,))
        itens = cur_app.fetchall()

        # 3) VRFOOD: gerar id_venda manual
        cur_vr.execute("LOCK TABLE food.venda IN EXCLUSIVE MODE")
        cur_vr.execute("SELECT COALESCE(MAX(id),0) FROM food.venda")
        id_venda = (cur_vr.fetchone()[0] or 0) + 1

        cur_vr.execute("""
            INSERT INTO food.venda (
                id, id_loja, id_cliente, id_tipopagamento, datahora, tempoentrega,
                troco, desconto, entrega, id_usuario, importado, id_situacaovenda,
                codigo, id_ifood, json, isretirada, dataretirada, horaretirada,
                id_entregador, id_vendedor
            ) VALUES (
                %s, %s, %s, 3, NOW(), '00:00:00',
                0, 0, 0, 0, FALSE, 0,
                %s, NULL, NULL, FALSE, NULL, NULL,
                NULL, NULL
            )
        """, (id_venda, id_loja, id_cliente, codigo_pedido))

        # 4) Itens
        itens_inseridos = 0
        print(itens)
        for id_produto, quantidade, precovenda, observacao, id_setor in itens:
            qtd = _to_decimal(quantidade) or Decimal('0')
            if qtd <= 0:
                continue
            pv = _to_decimal(precovenda) or Decimal('0')
            valortotal = pv * qtd
            if valortotal > 0:
                cur_vr.execute("""
                    INSERT INTO food.vendaitem
                        (id, id_venda, id_produto, quantidade, precovenda,
                        valortotal, observacao, id_setor)
                    VALUES
                        (nextval('food.vendaitem_id_seq'), %s, %s, %s, %s, %s,
                        %s, %s)
                """, (id_venda, int(id_produto), float(qtd),
                      float(pv), float(valortotal), observacao, int(id_setor)))
                itens_inseridos += 1

        conn_vr.commit()

        # 5) Marca pedido como finalizado no Gestão
        cur_app.execute("""
            UPDATE pedidos
               SET id_status = 7,
                   data_finalizacao = NOW(),
                   tipo_finalizacao = 'vrfood'
             WHERE id = %s;
        """, (id_pedido,))
        conn_app.commit()

        return jsonify({
            "mensagem": "Pedido finalizado no VRFood com sucesso.",
            "id_venda": id_venda,
            "codigo": codigo_pedido,
            "itens_inseridos": itens_inseridos
        })

    except Exception as e:
        conn_app.rollback()
        conn_vr.rollback()
        print("Erro ao finalizar VRFood:", str(e))
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
        cursor_app.execute("""
            SELECT id, nome, email, id_loja
            FROM usuarios
            WHERE id = %s
        """, (id_usuario,))

        row = cursor_app.fetchone()
        if not row:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        id_usuario, nome, email, id_loja = row

        usuario = {
            "id": id_usuario,
            "nome": nome,
            "email": email,
            "id_loja": id_loja
        }

        return jsonify(usuario)

    except Exception as e:
        print("Erro ao buscar usuário:", str(e))
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
        nome = data.get('nome')
        email = data.get('email')
        senha = data.get('senha')
        id_loja = data.get('id_loja')

        if not nome or not email or not senha or not id_loja:
            return jsonify({"erro": "Campos obrigatórios faltando"}), 400
        senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')

        cursor_app = conn_app.cursor()
        cursor_app.execute("""
            INSERT INTO usuarios (nome, email, senha, id_loja, criado_em)
            VALUES (%s, %s, %s, %s, NOW())
        """, (nome, email, senha_hash, id_loja))

        conn_app.commit()

        return jsonify({"mensagem": "Usuário criado com sucesso!"})

    except Exception as e:
        print("Erro ao criar usuário:", str(e))
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
        nome = data.get('nome')
        email = data.get('email')
        senha = data.get('senha')  # Se enviar vazio, não altera
        id_loja = data.get('id_loja')

        if not nome or not email or not id_loja:
            return jsonify({"erro": "Campos obrigatórios faltando"}), 400

        cursor_app = conn_app.cursor()

        if senha:
            senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')
            cursor_app.execute("""
                UPDATE usuarios
                SET nome = %s, email = %s, senha = %s, id_loja = %s
                WHERE id = %s
            """, (nome, email, senha, id_loja, id_usuario))
        else:
            cursor_app.execute("""
                UPDATE usuarios
                SET nome = %s, email = %s, id_loja = %s
                WHERE id = %s
            """, (nome, email, id_loja, id_usuario))

        conn_app.commit()

        return jsonify({"mensagem": "Usuário atualizado com sucesso!"})

    except Exception as e:
        print("Erro ao editar usuário:", str(e))
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()
@app.route("/usuarios/cadastro")
def usuarios_cadastro():
    return render_template("usuarios.html", titulo_tela="Cadastro de Usuários")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
@app.route('/pesquisar_opcoes', methods=['GET'])
def pesquisar_opcoes():
    # Conectar à base de dados conectar_app para buscar os produtos e opções
    conn_app = conectar_app()
    cursor_app = conn_app.cursor()

    # Conectar à base de dados conectar_vr para puxar as descrições
    conn_vr = conectar_vr()
    cursor_vr = conn_vr.cursor()

    # Captura os parâmetros de filtro
    codigo_produto = request.args.get('codigo_produto')
    descricao_produto = request.args.get('descricao_produto')

    # Construção da query dinâmica para buscar produtos e suas opções
    query = """
        SELECT 
            p.id AS id,
            p.codigo AS codigo_produto_principal,
            p.descricao AS descricao_produto_principal,
            s.descricao AS descricao_setor,
            COUNT(po.id) AS qtd_opcoes
        FROM produto p
        LEFT JOIN produtos_opcoes po ON po.id_produtoprinciapal = p.id
        LEFT JOIN ficha.setor s ON s.id = po.id_setor
        WHERE 1=1
    """

    # Adiciona filtros se fornecidos
    params = []
    if codigo_produto:
        query += " AND p.codigo LIKE %s"
        params.append(f"%{codigo_produto}%")
    if descricao_produto:
        query += " AND p.descricao LIKE %s"
        params.append(f"%{descricao_produto}%")
    
    query += " GROUP BY p.id, s.id ORDER BY p.codigo"
    
    cursor_app.execute(query, tuple(params))
    produtos = cursor_app.fetchall()

    # Agora que temos os IDs, vamos puxar as descrições completas do banco conectar_vr
    produtos_formatados = []
    for produto in produtos:
        produto_id = produto[0]
        descricao_produto_principal = produto[2]
        descricao_setor = produto[3]

        # Buscar a descrição completa do produto no banco conectar_vr
        cursor_vr.execute("""
            SELECT descricaocompleta 
            FROM produto 
            WHERE id = %s
        """, (produto_id,))
        produto_row = cursor_vr.fetchone()

        descricao_produto_completa = produto_row[0] if produto_row else descricao_produto_principal

        # Adicionar ao resultado final
        produtos_formatados.append({
            "id": produto[0],
            "codigo_produto_principal": produto[1],
            "descricao_produto_principal": descricao_produto_completa,
            "descricao_setor": descricao_setor,
            "qtd_opcoes": produto[4]
        })

    conn_app.close()
    conn_vr.close()
    
    return render_template('pesquisa_opcoes.html', produtos=produtos_formatados)
    
@app.route('/incluir_opcao', methods=['GET', 'POST'])
def incluir_opcao():
    if request.method == 'POST':
        # Aqui você captura os dados do formulário e insere no banco de dados
        codigo_produto_principal = request.form['codigo_produto_principal']
        descricao_produto_principal = request.form['descricao_produto_principal']
        # Lógica para inserir as opções também
        # ...

        return redirect(url_for('pesquisar_opcoes'))

    return render_template('incluir_opcao.html')  # Formulário para incluir novo produto
@app.route('/editar_opcao/<int:id>', methods=['GET', 'POST'])
def editar_opcao(id):
    if request.method == 'POST':
        # Lógica para editar o produto e as opções no banco de dados
        codigo_produto_principal = request.form['codigo_produto_principal']
        descricao_produto_principal = request.form['descricao_produto_principal']
        # Atualizar no banco de dados
        return redirect(url_for('pesquisar_opcoes'))

    # Buscar produto para editar
    conn = conectar_vr()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM produto WHERE id = %s", (id,))
    produto = cursor.fetchone()
    conn.close()
    
    return render_template('editar_opcao.html', produto=produto)
@app.route('/excluir_opcao/<int:id>', methods=['POST'])
def excluir_opcao(id):
    conn = conectar_vr()
    cursor = conn.cursor()

    # Excluir o produto principal e as opções relacionadas
    cursor.execute("DELETE FROM produtos_opcoes WHERE id_produtoprinciapal = %s", (id,))
    cursor.execute("DELETE FROM produto WHERE id = %s", (id,))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('pesquisar_opcoes'))
    
@app.route("/api/produto_opcoes/<int:id_produto>")
def api_produto_opcoes(id_produto):
    conn_app = conectar_app()
    conn_vr = conectar_vr()
    try:
        cur_app = conn_app.cursor()
        cur_vr = conn_vr.cursor()

        # 1. Buscar o grupo (id_produtoopcoes) onde esse produto é principal
        cur_app.execute("""
            SELECT id_produtoopcoes FROM produto_opcoes_principal WHERE id_produto_principal = %s
        """, (id_produto,))
        row = cur_app.fetchone()
        if not row or not row[0]:
            return jsonify([])

        id_produtoopcoes = row[0]

        # 2. Buscar todos os associados desse grupo
        cur_app.execute("""
            SELECT id_produto_associado FROM produto_opcoes_associado WHERE id_produtoopcoes = %s
        """, (id_produtoopcoes,))
        associados = [a[0] for a in cur_app.fetchall()]

        if not associados:
            return jsonify([])

        # 3. Buscar descrições dos produtos associados no VR
        cur_vr.execute(
            f"SELECT id, descricaocompleta FROM produto WHERE id IN ({','.join(['%s']*len(associados))})",
            associados
        )
        resultado = cur_vr.fetchall()
        opcoes = [{"id": r[0], "nome": r[1]} for r in resultado]
        return jsonify(opcoes)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"erro": str(e)}), 500

    finally:
        conn_app.close()
        conn_vr.close()


@app.route("/api/produto_associado/salvar", methods=["POST"])
def salvar_produto_associado():
    conn = conectar_app()
    try:
        dados = request.get_json()
        cur = conn.cursor()

        if not dados or 'descricao_grupo' not in dados or 'id_loja' not in dados:
            return jsonify({"erro": "Dados incompletos"}), 400

        descricao_grupo = dados['descricao_grupo']
        id_loja = dados['id_loja']
        principais = dados['principais']   # lista de códigos
        opcoes = dados['opcoes']           # lista de códigos

        # Insere grupo
        cur.execute("""
            INSERT INTO controle_id_produtoopcoes (descricao, id_loja)
            VALUES (%s, %s) RETURNING id
        """, (descricao_grupo, id_loja))
        id_grupo = cur.fetchone()[0]

        # Insere principais
        for p in principais:
            cur.execute("""
                INSERT INTO produto_opcoes_principal (id_produtoopcoes,
                id_produto_principal)
                VALUES (%s, %s)
            """, (id_grupo, p))

        # Insere associados
        for o in opcoes:
            cur.execute("""
                INSERT INTO produto_opcoes_associado (id_produtoopcoes,
                id_produto_associado)
                VALUES (%s, %s)
            """, (id_grupo, o))

        conn.commit()
        return jsonify({
            "status": "ok",
            "id_produtoopcoes": id_grupo,
            "descricao": descricao_grupo,
            "id_loja": id_loja
        }), 201

    except Exception as e:
        import traceback
        print("ERRO AO SALVAR PRODUTO ASSOCIADO:")
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
        cur.execute("""
            UPDATE controle_id_produtoopcoes
            SET descricao = %s, id_loja = %s
            WHERE id = %s
        """, (dados['descricao_grupo'], dados['id_loja'], id))

        # Apaga principais e associados antigos do grupo
        cur.execute("DELETE FROM produto_opcoes_principal WHERE id_produtoopcoes = %s", (id,))
        cur.execute("DELETE FROM produto_opcoes_associado WHERE id_produtoopcoes = %s", (id,))

        # Insere os novos principais
        for p in dados['principais']:
            cur.execute("""
                INSERT INTO produto_opcoes_principal (id_produtoopcoes, id_produto_principal)
                VALUES (%s, %s)
            """, (id, p))

        # Insere os novos associados
        for o in dados['opcoes']:
            cur.execute("""
                INSERT INTO produto_opcoes_associado (id_produtoopcoes, id_produto_associado)
                VALUES (%s, %s)
            """, (id, o))

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
        cur.execute("DELETE FROM produto_opcoes_principal WHERE id_produtoopcoes = %s", (id,))
        # Exclui todos os associados desse grupo
        cur.execute("DELETE FROM produto_opcoes_associado WHERE id_produtoopcoes = %s", (id,))
        # Exclui o grupo (isso pode ser suficiente se usou ON DELETE CASCADE)
        cur.execute("DELETE FROM controle_id_produtoopcoes WHERE id = %s", (id,))
        conn.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()

@app.route("/produto_associado")
def tela_produto_associado():
    return render_template("produto_associado.html", titulo_tela="Cadastro de Associados")
    
@app.route("/api/produto_vr/<int:id_produto>")
def api_detalhe_produto_vr(id_produto):
    conn = conectar_vr()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.descricaocompleta
            FROM produto p
            WHERE p.id = %s
        """, (id_produto,))
        row = cur.fetchone()
        return jsonify({
            "descricao": row[0] if row else ""
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


@app.route("/consulta_associado")
def pagina_consulta_associado():
    return render_template("consulta_associado.html",
                           titulo_tela="Consulta de Associados")


@app.route("/consulta_composto")
def pagina_consulta_composto():
    return render_template("consulta_composto.html",
                           titulo_tela="Consulta de Produtos Compostos")


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
            cur_app.execute("SELECT id_produto_principal FROM produto_opcoes_principal WHERE id_produtoopcoes = %s", (g[0],))
            principais_dict[g[0]] = [r[0] for r in cur_app.fetchall()]
            cur_app.execute("SELECT id_produto_associado FROM produto_opcoes_associado WHERE id_produtoopcoes = %s", (g[0],))
            associados_dict[g[0]] = [r[0] for r in cur_app.fetchall()]

        # Descobre todos os ids de loja usados
        id_lojas = list({g[2] for g in grupos if g[2] is not None})
        nomes_loja = {}
        if id_lojas:
            cur_vr = conn_vr.cursor()
            cur_vr.execute(
                "SELECT id, descricao FROM loja WHERE id = ANY(%s)",
                (id_lojas,)
            )
            nomes_loja = {row[0]: row[1] for row in cur_vr.fetchall()}

        # Monta o resultado com nome da loja E lista dos produtos
        return jsonify([
            {
                "id": g[0],
                "descricao": g[1],
                "id_loja": g[2],
                "nome_loja": nomes_loja.get(g[2], '') if g[2] else '',
                "produtos_principais": principais_dict.get(g[0], []),
                "produtos_associados": associados_dict.get(g[0], [])
            }
            for g in grupos
        ])
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
            cur.execute("SELECT id, descricao, id_loja FROM controle_id_produtoopcoes WHERE id = %s", (id_grupo,))
            grupo = cur.fetchone()
            principais, opcoes = [], []
            if grupo:
                cur.execute("SELECT id_produto_principal FROM produto_opcoes_principal WHERE id_produtoopcoes = %s", (id_grupo,))
                principais = [r[0] for r in cur.fetchall()]
                cur.execute("SELECT id_produto_associado FROM produto_opcoes_associado WHERE id_produtoopcoes = %s", (id_grupo,))
                opcoes = [r[0] for r in cur.fetchall()]
                contexto = {
                    "id": grupo[0],
                    "descricao": grupo[1],
                    "id_loja": grupo[2],
                    "principais": [{"cod": cod, "desc": "", "setor": ""} for cod in principais],
                    "opcoes": [{"cod": cod, "desc": "", "setor": ""} for cod in opcoes]
                }
            cur.close()
            conn.close()
        # Renderiza o modal já com o contexto (ou vazio se for novo)
        return render_template("produto_associado.html", **contexto)
    else:
        return redirect("/consulta_associado")


@app.route("/api/produto_associado/grupo/<int:id>")
def carregar_produto_associado(id):
    conn = conectar_app()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, descricao, id_loja FROM controle_id_produtoopcoes WHERE id = %s", (id,))
        grupo = cur.fetchone()
        if not grupo:
            return jsonify({"erro": "Grupo não encontrado"}), 404

        # Busca produtos principais
        cur.execute("SELECT id_produto_principal FROM produto_opcoes_principal WHERE id_produtoopcoes = %s", (id,))
        principais = [r[0] for r in cur.fetchall()]
        # Busca produtos de opção
        cur.execute("SELECT id_produto_associado FROM produto_opcoes_associado WHERE id_produtoopcoes = %s", (id,))
        opcoes = [r[0] for r in cur.fetchall()]

        return jsonify({
            "id": grupo[0],
            "descricao": grupo[1],
            "id_loja": grupo[2],
            "principais": [{"cod": cod, "desc": "", "setor": ""} for cod in principais],
            "opcoes": [{"cod": cod, "desc": "", "setor": ""} for cod in opcoes]
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


@app.route("/produto_composto")
def produto_composto():
    id_produto = request.args.get("id_produto", type=int)
    modal = request.args.get("modal")
    print(id_produto, modal)
    return render_template(
        "produto_composto.html",
        id_produto=id_produto,
        modal=modal
    )


@app.route("/api/produtos_compostos")
def get_produtos_compostos():
    try:
        a = svc_get_produtos_compostos()
        return jsonify(a)
    except Exception as e:
        logger.exception(e)
        return jsonify({
            "error": "Erro interno"
        }), 500


@app.route("/api/produtos_compostos/salvar", methods=["POST"])
def api_salvar_composto():
    dados = request.get_json()
    if not dados or not dados.get("id_produto"):
        return jsonify({"erro": "id_produto obrigatório."}), 400
    ok = svc_salvar_produtos_compostos(dados)
    if not ok:
        return jsonify({"erro": "Erro ao salvar."}), 500
    return jsonify({"ok": True})


@app.route("/api/produtos_compostos/remover/<int:id_produto>",
           methods=["DELETE"])
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
    return jsonify({
        "id_produto": id_produto,
        "tipo": estrutura.get("tipo"),
        "min_pessoas": estrutura.get("pedido_min_pessoas"),
        "calculo_pessoa": estrutura.get("calculo_pessoa"),
        "itens_fixos": itens_fixos,
        "grupos_opcionais": [{"chave": k, "itens": v} for k,
                             v in grupos.items()],
    })


@app.route("/api/produtos_compostos/explodir/<int:id_produto>",
          methods=["POST"])
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
            return jsonify({"erro": "quantidade deve ser maior que zero."}),
        400
    else:
        return jsonify({"erro": "Informe pessoas ou quantidade."}), 400
    estrutura = repo_get_composto_estrutura(id_produto)
    if estrutura is False:
        return jsonify({"erro": "Erro ao buscar composto."}), 500
    if estrutura is None:
        return jsonify({"erro": "Produto não é composto."}), 404
    produto_pai = repo_get_produto_detalhe(id_produto, int(id_loja))
    if not produto_pai:
        return jsonify({"erro": "Produto não encontrado na loja informada."}),
    404
    tem_calculo_pessoa = bool(estrutura.get("calculo_pessoa"))
    if tem_calculo_pessoa and not dados.get("pessoas"):
        return jsonify({"erro": "Este composto requer o campo pessoas."}),
    400
    if not tem_calculo_pessoa and not dados.get("quantidade"):
        return jsonify({"erro": "Este composto requer o campo quantidade."}),
    400

    componentes = calcular_componentes(id_produto,
                                       fator,
                                       estrutura,
                                       dados.get("escolhas_opcionais") or {})
    if componentes is False:
        return jsonify({"erro": "Erro ao calcular componentes."}), 500
    return jsonify({"itens": montar_itens(produto_pai,
                                          fator,
                                          componentes,
                                          int(id_loja))})


@app.route('/api/produtos/opcoes_associadas/<int:id_produto_principal>',
           methods=['GET'])
def opcoes_associadas(id_produto_principal):
    conn_app = conectar_app()
    cursor_app = conn_app.cursor()

    # 1. Buscar id_produtoopcoes na tabela produto_opcoes_principal
    cursor_app.execute("""
        SELECT id_produtoopcoes FROM produto_opcoes_principal
        WHERE id_produto_principal = %s
    """, (id_produto_principal,))
    row = cursor_app.fetchone()

    if not row or not row[0]:
        return jsonify([])  # Não tem associados

    id_produtoopcoes = row[0]

    # 2. Buscar id_produto_associado na tabela produto_opcoes_associado
    cursor_app.execute("""
        SELECT id_produto_associado FROM produto_opcoes_associado
        WHERE id_produtoopcoes = %s
    """, (id_produtoopcoes,))
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
        (tuple(ids_associados),)
    )
    resultado = cursor_vr.fetchall()

    # 4. Montar o JSON de retorno
    lista_retorno = [{'id': r[0], 'nome': r[1]} for r in resultado]

    return jsonify(lista_retorno)


@app.route("/setor/kds")
def setor_kds():
    return render_template("kds.html", titulo_tela="KDS")


@app.route('/api/kds/pedidos')
def api_kds_pedidos():
    loja = request.args.get('loja')
    setor = request.args.get('setor')

    conn = conectar_app()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id                                         AS id_pedido,
               pi.id                                        AS id_item,
               COALESCE(pi.id_produto_associado, pi.id_produto) AS id_produto_preferencial,
               pi.quantidade_un,
               p.data_entrega,
               p.hora_entrega,
               pi.observacao,
               pi.id_produto_associado,
               pi.id_setor,
               pi.id_status                                 AS id_status_item,
               p.tipo_entrega,
               p.id_status                                  AS id_status_pedido,
               pi.quantidade
          FROM pedidos p
          JOIN pedido_itens pi ON pi.id_pedido = p.id
         WHERE p.id_loja = %s
           AND pi.id_setor = %s
           AND (p.data_entrega = CURRENT_DATE
            OR  p.data_entrega = CURRENT_DATE + INTERVAL '1 day')
           AND (p.id_status NOT IN (5, 7))  
    """, (loja, setor))

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
            (tuple(produtos_ids),)
        )
        for prod_row in cursor_vr.fetchall():
            descricoes[prod_row[0]] = prod_row[1]
        cursor_vr.close()
        conn_vr.close()

    
    for row in rows:
        produto_id = row[7] if row[7] else row[2]
        pedidos.append({
            "id": row[0],                    
            "id_item": row[1],
            "id_produto": produto_id,
            "descricao": descricoes.get(produto_id, str(produto_id)),
            "quantidade": row[3],
            "data": str(row[4]),
            "hora": row[5].strftime('%H:%M') if hasattr(row[5], "strftime") else (str(row[5]) if row[5] is not None else ""),
            "observacao": row[6] or "",
            "id_produto_associado": row[7],
            "id_setor": row[8],
            "id_status": row[9],              
            "tipo_entrega": row[10],
            "id_status_pedido": row[11],
            "peso": row[12]
        })

    return jsonify(pedidos)

@app.route('/api/kds/pedido/produzir', methods=['POST'])
def kds_produzir():
    data = request.get_json()
    id_pedidos = data.get("ids", [])
    if not id_pedidos:
        return jsonify({"success": False, "msg": "Nenhum pedido informado!"}), 400

    conn = conectar_app()
    cursor = conn.cursor()
    # Atualiza todos os pedidos para status = 1 (em produção)
    cursor.execute(
        "UPDATE pedidos SET id_status = 1 WHERE id = ANY(%s)",
        (id_pedidos,)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/kds/pedido/finalizar', methods=['POST'])
def kds_finalizar():
    data = request.get_json()
    id_pedidos = data.get("ids", [])
    if not id_pedidos:
        return jsonify({"success": False,
                        "msg": "Nenhum pedido informado!"}), 400

    conn = conectar_app()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE pedidos SET id_status = 7 WHERE id = ANY(%s)",
        (id_pedidos,)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/kds/item/produzir', methods=['POST'])
def kds_item_produzir():
    data = request.get_json()
    ids_itens = data.get("ids", [])
    if not ids_itens:
        return jsonify({"success": False, "msg": "Nenhum item informado!"}), 400

    conn = conectar_app()
    cursor = conn.cursor()
    # Atualiza apenas os itens para status = 1 (em produção)
    cursor.execute(
        "UPDATE pedido_itens SET id_status = 1 WHERE id = ANY(%s)",
        (ids_itens,)
    )
    conn.commit()
    cursor.close()

    # Agora, para cada item, analise se todos os itens do pedido estão com mesmo status
    cursor = conn.cursor()
    for id_item in ids_itens:
        cursor.execute("SELECT id_pedido FROM pedido_itens WHERE id = %s", (id_item,))
        id_pedido_row = cursor.fetchone()
        if not id_pedido_row:
            continue
        id_pedido = id_pedido_row[0]
        cursor.execute("SELECT DISTINCT id_status FROM pedido_itens WHERE id_pedido = %s", (id_pedido,))
        status_list = [r[0] for r in cursor.fetchall()]
        # Se só existe um status (todos iguais), atualiza o pedido principal
        if len(status_list) == 1:
            cursor.execute("UPDATE pedidos SET id_status = %s WHERE id = %s", (status_list[0], id_pedido))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/kds/item/finalizar', methods=['POST'])
def kds_item_finalizar():
    data = request.get_json()
    ids_itens = data.get("ids", [])
    if not ids_itens:
        return jsonify({"success": False, "msg": "Nenhum item informado!"}), 400

    conn = conectar_app()
    cursor = conn.cursor()
    # Atualiza apenas os itens para status = 2 (produzido)
    cursor.execute(
        "UPDATE pedido_itens SET id_status = 2 WHERE id = ANY(%s)",
        (ids_itens,)
    )
    conn.commit()
    cursor.close()

    # Agora, para cada item, analise se todos os itens do pedido estão com mesmo status
    cursor = conn.cursor()
    for id_item in ids_itens:
        cursor.execute("SELECT id_pedido FROM pedido_itens WHERE id = %s", (id_item,))
        id_pedido_row = cursor.fetchone()
        if not id_pedido_row:
            continue
        id_pedido = id_pedido_row[0]
        cursor.execute("SELECT DISTINCT id_status FROM pedido_itens WHERE id_pedido = %s", (id_pedido,))
        status_list = [r[0] for r in cursor.fetchall()]
        # Se só existe um status (todos iguais), atualiza o pedido principal
        if len(status_list) == 1:
            cursor.execute("UPDATE pedidos SET id_status = %s WHERE id = %s", (status_list[0], id_pedido))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/pedido/<int:id_pedido>/imprimir', methods=['POST'])
def imprimir_pedido(id_pedido):
    import os
    from datetime import datetime
    from flask import request, jsonify
    from app.conexao_app import conectar_app
    from app.conexao_vr import conectar_vr

    # ---------------------------------------
    # Helpers de formatação / codificação
    # ---------------------------------------
    def br_date(d):
        if not d:
            return ""
        if isinstance(d, datetime):
            return d.strftime('%d/%m/%Y')
        try:
            return datetime.strptime(str(d)[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
        except Exception:
            return str(d)

    def br_time(t):
        if not t:
            return ""
        if isinstance(t, datetime):
            return t.strftime('%H:%M')
        s = str(t)
        return s[:5]

    # Normaliza caracteres “tipográficos” para equivalentes simples aceitos na maioria das térmicas
    def normalize_text(s: str) -> str:
        if s is None:
            return ""
        s = str(s)
        s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        s = s.replace("—", "-").replace("–", "-")
        s = s.replace("…", "...")
        s = s.replace("•", "*")
        return s

    def join_crlf(lines):
        # Junta com CRLF — manteremos também no binário para consistência visual
        return "\r\n".join(lines) + "\r\n"

    # Body pode conter parâmetros opcionais
    data = request.get_json() or {}
    linhas_extras = int(data.get('linhas_extras', 3))  # mantém 3 linhas extras por padrão
    cortar        = bool(data.get('cortar', True))
    tipo_corte    = (data.get('tipo_corte') or 'full')  # 'full' | 'partial'

    conn_app = conectar_app()
    conn_vr = conectar_vr()

    if not conn_app or not conn_vr:
        return jsonify({"erro": "Erro ao conectar ao banco de dados"}), 500

    cursor_app = conn_app.cursor()
    cursor_vr = conn_vr.cursor()
    try:
        # ---------------------------
        # 1) Buscar pedido
        # ---------------------------
        cursor_app.execute("""
            SELECT id, id_cliente, id_loja, criado_em, data_entrega, hora_entrega, tipo_entrega, observacoes, id_status
            FROM pedidos
            WHERE id = %s
        """, (id_pedido,))
        row = cursor_app.fetchone()

        if not row:
            return jsonify({'sucesso': False, 'mensagem': 'Pedido não encontrado'}), 404

        id_cliente = row[1]
        id_loja    = row[2]

        # ---------------------------
        # 2) Pegar caminho da impressora pela LOJA do pedido (id_setor IS NULL)
        # ---------------------------
        cursor_app.execute("""
            SELECT caminho_impressora
              FROM impressora
             WHERE id_loja = %s
               AND id_setor IS NULL
             ORDER BY caminho_impressora ASC
             LIMIT 1
        """, (id_loja,))
        imp_row = cursor_app.fetchone()
        if not imp_row or not (imp_row[0] or '').strip():
            return jsonify({
                'sucesso': False,
                'mensagem': 'Nenhuma impressora configurada para esta loja (setor em branco).',
                'id_loja': id_loja
            }), 412

        caminho_impressora = imp_row[0].strip()
        # ---------------------------
        # 3) Buscar dados do cliente (VR)
        # ---------------------------
        cursor_vr.execute("""
            SELECT fc.nome, fct.telefone,
                   CONCAT(fc.endereco, ', ', fc.numero, ', ', fc.bairro, ', ', m.descricao, ' - ', e.descricao) AS endereco_completo
              FROM food.cliente fc
         LEFT JOIN food.clientetelefone fct ON fct.id_cliente = fc.id
        INNER JOIN public.municipio m ON m.id = fc.id_municipio
        INNER JOIN public.estado   e ON e.id = m.id_estado
             WHERE fc.id = %s
             LIMIT 1
        """, (id_cliente,))
        cliente_row = cursor_vr.fetchone()
        nome_cliente     = cliente_row[0] if cliente_row else "Cliente não encontrado"
        telefone_cliente = cliente_row[1] if cliente_row else ""
        endereco_cliente = cliente_row[2] if cliente_row else ""

        # ---------------------------
        # 4) Buscar nome da loja (VR)
        # ---------------------------
        cursor_vr.execute("SELECT descricao FROM loja WHERE id = %s", (id_loja,))
        loja_row = cursor_vr.fetchone()
        nome_loja = loja_row[0] if loja_row else ""

        # ---------------------------
        # 5) Descrição do status (APP)
        # ---------------------------
        cursor_app.execute("SELECT descricao FROM status WHERE id = %s", (row[8],))
        status_row = cursor_app.fetchone()
        status_descricao = status_row[0] if status_row else ""

        # ---------------------------
        # 6) Valor total (APP)
        # ---------------------------
        cursor_app.execute("""
            SELECT COALESCE(SUM(quantidade * valor_unitario), 0)
              FROM pedido_itens
             WHERE id_pedido = %s
        """, (id_pedido,))
        valor_total_row = cursor_app.fetchone()
        valor_total = float(valor_total_row[0]) if valor_total_row else 0.0
        valor_total_formatado = "R$ {:.2f}".format(valor_total).replace('.', ',')

        # ---------------------------
        # 7) Itens do pedido (APP) + descrição do produto (VR) -> ordenar alfabeticamente
        # ---------------------------
        cursor_app.execute("""
            SELECT id_produto, quantidade, quantidade_un, observacao
              FROM pedido_itens
             WHERE id_pedido = %s
        """, (id_pedido,))
        itens_rows = cursor_app.fetchall()

        itens = []
        for item in itens_rows:
            id_produto = item[0]
            cursor_vr.execute("SELECT descricaocompleta FROM produto WHERE id = %s", (id_produto,))
            produto_row = cursor_vr.fetchone()
            descricao = (produto_row[0] if produto_row else "") or ""
            itens.append({
                "descricao": descricao,
                "quantidade_un": item[2],
                "observacao": item[3] or ""
            })

        # **ORDENAÇÃO ALFABÉTICA DOS ITENS**
        itens.sort(key=lambda x: x["descricao"].casefold() if x["descricao"] else "")

        # ---------------------------
        # 8) Montar texto da impressão
        # ---------------------------
        texto = []
        texto.append(f"Pedido #{row[0]}")
        texto.append(f"Loja: {normalize_text(nome_loja)}")
        texto.append(f"Cliente: {normalize_text(nome_cliente)}")
        texto.append(f"Telefone: {normalize_text(telefone_cliente)}")
        if status_descricao:
            texto.append(f"Status: {normalize_text(status_descricao)}")

        data_entrega_str = br_date(row[4])
        hora_entrega_str = br_time(row[5])

        texto.append(f"Tipo Entrega: {normalize_text(row[6])}")
        texto.append(f"Data Entrega: {data_entrega_str} - {hora_entrega_str}")

        # Endereço apenas se tipo = entrega
        if row[6] == 'entrega' and endereco_cliente:
            texto.append(f"Endereço: {normalize_text(endereco_cliente)}")

        # >>> Observações do Pedido <<<
        if row[7]:
            texto.append("")  # separador visual
            texto.append("Observações do Pedido:")
            for linha_obs in str(row[7]).splitlines():
                linha_obs = (linha_obs or "").strip()
                if linha_obs:
                    texto.append(normalize_text(linha_obs))

        texto.append("")  # linha em branco
        texto.append("Produtos (ordem alfabética):")
        for it in itens:
            linha_prod = f"{it['quantidade_un']} un - {normalize_text(it['descricao'])}"
            if it['observacao']:
                linha_prod += f" ({normalize_text(it['observacao'])})"
            texto.append(linha_prod)

        texto.append(f"Valor Total: {valor_total_formatado}")

        # Linhas em branco para térmica
        for _ in range(max(0, linhas_extras)):
            texto.append("")

        # Texto final com CRLF
        conteudo_txt = join_crlf(texto)

        # ---------------------------
        # 9) Enviar para impressora (RAW ESC/POS com code page PT)
        # ---------------------------
        # ESC/POS
        ESC = b'\x1b'
        GS = b'\x1d'
        init_printer = ESC + b'@'           # inicializa
        # Code pages:
        #  0x03 = PC860 (Português)   -> preferida para PT-BR
        #  0x02 = PC850 (Multilingual) -> alternativa comum
        select_cp = ESC + b't' + b'\x03'    # tente primeiro PC860
        try:
            dados = init_printer + select_cp + conteudo_txt.encode('cp860',
                                                                   errors='replace')
        except LookupError:
            # fallback para cp850 se ambiente não tiver cp860 (raro)
            select_cp = ESC + b't' + b'\x02'
            dados = init_printer + select_cp + conteudo_txt.encode('cp850',
                                                                   errors='replace')

        # Corte (opcional) – respeita flags recebidas
        if cortar:
            dados += GS + b'V' + (b'\x00' if (tipo_corte == 'full') else b'\x01')

        # Grava binário e envia com 'copy /b' (mantém bytes intactos)
        nome_arquivo = f'pedido_{row[0]}.bin'
        with open(caminho_impressora, "wb") as printer:
            printer.write(dados)

        comando = f'copy /b "{nome_arquivo}" "{caminho_impressora}"'
        os.system(comando)
        cursor_app.execute("UPDATE pedidos SET impresso = true WHERE id = %s", (id_pedido,))
        conn_app.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        conn_app.rollback()
        print("Erro ao imprimir pedido:", str(e))
        return jsonify({"erro": str(e)}), 500
    finally:
        try:
            cursor_app.close()
            conn_app.close()
        except Exception:
            pass
        try:
            cursor_vr.close()
            conn_vr.close()
        except Exception:
            pass


# CONSULTAR caminho da impressora
@app.route("/api/impressora", methods=["GET"])
def api_impressora_get():
    conn = conectar_app()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT caminho_impressora FROM impressora ORDER BY id DESC LIMIT 1")
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
        cursor.execute("""INSERT INTO impressora (caminho_impressora)
                       VALUES (%s)""", (caminho,))
        conn.commit()
        return jsonify({"sucesso": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


@app.route("/base")
def base():
    return render_template("layout_base.html")


@app.route('/dashboard_partial')
def dashboard_partial():
    return render_template('dashboard_partial.html')


@app.route("/api/ia/cliente", methods=["POST"])
def ia_buscar_cliente():
    conn_vr = conectar_vr()

    if not conn_vr:
        return jsonify({"erro": "Falha ao conectar ao banco de dados"}), 500

    try:
        dados = request.get_json()
        telefone = dados.get("telefone")

        if not telefone:
            return jsonify({"erro": "Telefone não informado"}), 400

        cursor = conn_vr.cursor()

        cursor.execute("""
            SELECT c.id, c.nome, t.telefone
            FROM food.clientetelefone t
            JOIN food.cliente c ON c.id = t.id_cliente
            WHERE t.telefone ILIKE %s
            LIMIT 1
        """, (f"%{telefone}%",))

        row = cursor.fetchone()

        if row:
            id_cliente, nome_completo, telefone_encontrado = row
            primeiro_nome = nome_completo.split()[0]
            return jsonify({
                "cliente_encontrado": True,
                "id_cliente": id_cliente,
                "nome_completo": nome_completo,
                "primeiro_nome": primeiro_nome,
                "telefone": telefone_encontrado
            })
        else:
            return jsonify({"cliente_encontrado": False})

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
@app.route("/api/ia/cadastrar_cliente", methods=["POST"])
def ia_cadastrar_cliente():
    conn_vr = conectar_vr()

    if not conn_vr:
        return jsonify({"erro": "Falha ao conectar ao banco de dados"}), 500

    try:
        dados = request.get_json()

        nome = dados.get("nome")
        endereco = dados.get("endereco")
        numero = dados.get("numero")
        bairro = dados.get("bairro")
        complemento = dados.get("complemento", "")
        telefone = dados.get("telefone")
        cidade = dados.get("cidade")  # ex: Limeira
        estado_sigla = dados.get("estado")  # ex: SP

        if not all([nome, endereco, numero, bairro, telefone, cidade, estado_sigla]):
            return jsonify({"erro": "Campos obrigatórios faltando"}), 400

        cursor = conn_vr.cursor()

        # Buscar id_estado
        cursor.execute("""
            SELECT id FROM estado WHERE sigla = %s
        """, (estado_sigla,))
        row_estado = cursor.fetchone()
        if not row_estado:
            return jsonify({"erro": f"Estado '{estado_sigla}' não encontrado"}), 400
        id_estado = row_estado[0]

        # Buscar id_municipio
        cursor.execute("""
            SELECT id FROM municipio
            WHERE descricao ILIKE %s AND id_estado = %s
        """, (cidade.strip(), id_estado))
        row_municipio = cursor.fetchone()
        if not row_municipio:
            return jsonify({"erro": f"Município '{cidade}' não encontrado no estado '{estado_sigla}'"}), 400
        id_municipio = row_municipio[0]

        # Valores fixos para campos obrigatórios
        id_situacaocadastro = 1
        id_regiao = 1

        # Inserir cliente
        cursor.execute("""
            INSERT INTO food.cliente (
                nome, endereco, numero, bairro, complemento,
                id_situacaocadastro, id_municipio, id_regiao
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            nome, endereco, numero, bairro, complemento,
            id_situacaocadastro, id_municipio, id_regiao
        ))

        id_cliente = cursor.fetchone()[0]

        # Inserir telefone
        cursor.execute("""
            INSERT INTO food.clientetelefone (id_cliente, telefone)
            VALUES (%s, %s)
        """, (id_cliente, telefone))

        conn_vr.commit()

        return jsonify({
            "cliente_cadastrado": True,
            "id_cliente": id_cliente,
            "primeiro_nome": nome.split()[0]
        })

    except Exception as e:
        conn_vr.rollback()
        return jsonify({"erro": str(e)}), 500


@app.route("/api/produtos/busca_descricao", methods=["POST"])
def buscar_produtos_por_descricao():
    data = request.get_json() or {}
    termo = (data.get('termo') or '').strip().lower()

    if not termo:
        return jsonify([])

    tokens = [t for t in termo.split() if t]
    if not tokens:
        return jsonify([])

    conn = conectar_vr()
    cursor = conn.cursor()

    # Se seu MySQL suportar, pode usar a collation acento-insensível:
    # predicado = "p.descricaocompleta COLLATE utf8mb4_0900_ai_ci LIKE %s"
    # Caso contrário, mantenha o LOWER(...) mesmo:
    predicado = "LOWER(p.descricaocompleta) LIKE %s"

    where_clauses = " AND ".join([predicado] * len(tokens))

    # ✅ Filtro garantido: só traz produtos cujo produtocomplemento.id_situacaocadastro = 1
    sql = f"""
        SELECT DISTINCT p.id, p.descricaocompleta
        FROM produto p
        INNER JOIN produtocomplemento pc ON pc.id_produto = p.id
        WHERE pc.id_situacaocadastro = 1
          AND {where_clauses}
        ORDER BY p.descricaocompleta
        LIMIT 20
    """

    params = [f"%{t}%" for t in tokens]
    cursor.execute(sql, params)
    resultados = cursor.fetchall()

    produtos = [{"id": row[0], "descricaocompleta": row[1]} for row in resultados]
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
        cursor_app.execute("INSERT INTO produto_exibir_horario (id_produto) VALUES (%s)", (id_produto,))
        conn_app.commit()
        return jsonify({"success": True})

    elif request.method == "DELETE":
        data = request.get_json()
        id_produto = data.get("id_produto")
        cursor_app.execute("DELETE FROM produto_exibir_horario WHERE id_produto = %s", (id_produto,))
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
    
# GET /api/impressora/setor?loja=1&setor=2
@app.route("/api/impressora/setor", methods=["GET"])
def api_impressora_por_setor_get():
    id_loja  = request.args.get("loja", type=int)
    setor_qs = request.args.get("setor", default=None)     # pode vir "", None ou "123"
    id_setor = int(setor_qs) if (setor_qs and setor_qs.strip().isdigit()) else None

    if not id_loja:
        return jsonify({"erro":"Parâmetro 'loja' é obrigatório"}), 400

    conn = conectar_app()
    try:
        cur = conn.cursor()
        if id_setor is None:
            cur.execute("""
                SELECT id, caminho_impressora
                  FROM impressora
                 WHERE id_loja = %s AND id_setor IS NULL
                 LIMIT 1
            """, (id_loja,))
        else:
            cur.execute("""
                SELECT id, caminho_impressora
                  FROM impressora
                 WHERE id_loja = %s AND id_setor = %s
                 LIMIT 1
            """, (id_loja, id_setor))

        row = cur.fetchone()
        return jsonify({
            "id": row[0] if row else None,
            "id_loja": id_loja,
            "id_setor": id_setor,              # pode ser None
            "caminho_impressora": row[1] if row else ""
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


# POST /api/impressora/setor  body: {id_loja, id_setor, caminho_impressora}
@app.route("/api/impressora/setor", methods=["POST"])
def api_impressora_por_setor_post():
    dados    = request.get_json() or {}
    id_loja  = dados.get("id_loja")
    id_setor = dados.get("id_setor", None)  # pode ser null/"" → None
    caminho  = (dados.get("caminho_impressora") or "").strip()

    if not id_loja or not caminho:
        return jsonify({"erro":"id_loja e caminho_impressora são obrigatórios"}), 400

    try:
        id_loja  = int(id_loja)
        id_setor = (int(id_setor) if id_setor not in (None, "",) else None)
    except (TypeError, ValueError):
        return jsonify({"erro":"id_loja/id_setor inválidos"}), 400

    conn = conectar_app()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO impressora (id_loja, id_setor, caminho_impressora)
            VALUES (%s, %s, %s)
            ON CONFLICT (id_loja, id_setor)
            DO UPDATE SET caminho_impressora = EXCLUDED.caminho_impressora
        """, (id_loja, id_setor, caminho))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        conn.close()


def _montar_texto_impressao_kds(titulo, itens):
    # itens: [{produto, observacao, quantidade_formatada}]
    linhas = []
    linhas.append(f"*** {titulo} ***")
    for it in itens:
        linhas.append(f"{it['produto']}")
        if it.get('observacao'):
            linhas.append(f"OBS: {it['observacao']}")
        linhas.append(f"QTD: {it['quantidade_formatada']}")
        linhas.append("-" * 32)
    linhas.append("\n\n")
    return "\r\n".join(linhas)


def _enviar_para_impressora_kds(caminho, conteudo):
    try:
        with open(caminho, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(conteudo)
        return True, ""
    except Exception as e:
        return False, str(e)


@app.route("/api/kds/imprimir", methods=["POST"])
def api_kds_imprimir_coluna():
    data = request.get_json() or {}
    id_loja = int(data.get("id_loja") or 0)
    id_setor = int(data.get("id_setor") or 0)
    coluna  = data.get("coluna")  # aguardando | producao
    itens   = data.get("itens") or []

    if not (id_loja and id_setor and coluna in ("aguardando","producao") and isinstance(itens, list) and itens):
        return jsonify({"erro":"Dados inválidos"}), 400

    # Busca caminho por loja/setor
    conn = conectar_app()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT caminho_impressora
              FROM impressora
             WHERE id_loja = %s AND id_setor = %s
             LIMIT 1
        """, (id_loja, id_setor))
        row = cur.fetchone()
    finally:
        conn.close()

    if not row or not row[0]:
        return jsonify({"erro":"Impressora não configurada para esta Loja/Setor"}), 404

    titulo = f"KDS - Setor {id_setor} - {'AGUARDANDO' if coluna=='aguardando' else 'EM PRODUÇÃO'}"
    texto  = _montar_texto_impressao_kds(titulo, itens)
    ok, msg = _enviar_para_impressora_kds(row[0], texto)
    if not ok:
        return jsonify({"erro": f"Falha ao imprimir: {msg}"}), 500
    return jsonify({"ok": True})
