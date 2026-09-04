def adicionar_filtro_simples(where, params, coluna, valor):
    if not valor:
        return

    where.append(f"{coluna} = %s")
    params.append(valor)


def adicionar_filtro_impresso(where, impresso):
    filtros = {
        "1": "p.impresso = TRUE",
        "0": "p.impresso = FALSE",
    }

    clausula = filtros.get(impresso)

    if clausula:
        where.append(clausula)


def normalizar_numero_pedido(valor):
    if valor is None:
        return None

    if isinstance(valor, str):
        valor = valor.strip()

        if not valor:
            return None

    try:
        return int(valor)
    except (ValueError, TypeError):
        return None


def adicionar_filtro_numero(where, params, num_pedido):
    num_pedido = normalizar_numero_pedido(num_pedido)

    if num_pedido:
        where.append("p.id = %s")
        params.append(num_pedido)


def adicionar_filtro_data(where, params, filtros):
    coluna = obter_coluna_data(filtros.get("data_tipo"))

    data_inicio = filtros.get("data_inicio")
    data_fim = filtros.get("data_fim")

    if data_inicio and data_fim:
        where.append(f"CAST(p.{coluna} AS DATE) BETWEEN %s AND %s")
        params.extend([data_inicio, data_fim])
        return

    if data_inicio:
        where.append(f"CAST(p.{coluna} AS DATE) = %s")
        params.append(data_inicio)
        return

    if data_fim:
        where.append(f"CAST(p.{coluna} AS DATE) = %s")
        params.append(data_fim)


def obter_coluna_data(data_tipo):
    colunas = {
        "data_pedido": "criado_em",
        "data_entrega": "data_entrega",
    }

    return colunas.get(data_tipo, "criado_em")


def adicionar_filtro_status(where, params, id_status):
    if id_status in (None, "", "todos"):
        where.append("p.id_status NOT IN (5, 7)")
        return

    try:
        id_status = int(id_status)
    except (ValueError, TypeError):
        where.append("p.id_status NOT IN (5, 7)")
        return

    where.append("p.id_status = %s")
    params.append(id_status)


def montar_filtros_pedidos(filtros):
    if not isinstance(filtros, dict):
        filtros = {}
    where = []
    params = []
    num_pedido = normalizar_numero_pedido(filtros.get("num_pedido"))
    if num_pedido:
        # busca direta por número: ignora os demais filtros,
        # exceto "impresso"
        where.append("p.id = %s")
        params.append(num_pedido)
        adicionar_filtro_impresso(where, filtros.get("impresso"))
        return where, params
    adicionar_filtro_impresso(where, filtros.get("impresso"))
    adicionar_filtro_data(where, params, filtros)
    adicionar_filtro_simples(where, params, "p.tipo_entrega",
                             filtros.get("tipo_entrega"))
    adicionar_filtro_simples(where, params, "p.id_loja", filtros.get("id_loja"))
    adicionar_filtro_status(where, params, filtros.get("status"))
    adicionar_filtro_simples(where, params, "p.id_cliente", filtros.get("id_cliente"))
    return where, params
