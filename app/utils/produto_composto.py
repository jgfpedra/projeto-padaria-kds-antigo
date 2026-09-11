import math


def salgados(itens, pessoas, salgados_unid):
    por_item = float(salgados_unid) * pessoas / len(itens)
    return [
        {"id_produto": i["id_produto"], "quantidade": round(por_item, 2)} for i in itens
    ]


def bebidas(itens, pessoas, bebida_ml):
    total_ml = math.ceil(float(bebida_ml) * pessoas / 1000) * 1000
    validos = sorted(
        [
            (i["id_produto"], int(i["capacidade_ml"]))
            for i in itens
            if int(i.get("capacidade_ml") or 0) > 0
        ],
        key=lambda x: x[1],
    )
    if not validos:
        return []
    if len(validos) == 1:
        id_p, cap = validos[0]
        return [{"id_produto": id_p, "quantidade": math.ceil(total_ml / cap)}]
    id_menor, cap_menor = validos[0]
    id_maior, cap_maior = validos[-1]
    qtd_maior = math.ceil(total_ml / 2 / cap_maior)
    restante = max(total_ml - qtd_maior * cap_maior, 0)
    qtd_menor = math.ceil(restante / cap_menor) if restante else 0
    result = []
    if qtd_maior:
        result.append({"id_produto": id_maior, "quantidade": qtd_maior})
    if qtd_menor:
        result.append({"id_produto": id_menor, "quantidade": qtd_menor})
    return result


def bolos(itens, pessoas, bolo_g):
    result = []
    for i in itens:
        peso_unit = float(i["peso_unitario_kg"] or 0)
        peso_total = (float(bolo_g) * pessoas) / 1000
        qtd = round(peso_total / peso_unit) if peso_unit > 0 else 0
        result.append({"id_produto": i["id_produto"], "quantidade": qtd})
    return result
