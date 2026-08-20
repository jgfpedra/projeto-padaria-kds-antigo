import logging
from app.repo.produto_composto import (
    repo_get_itens_fixos,
    repo_get_opcionais_escolhidos,
    repo_get_produto_detalhe,
)
from app.utils.produto_composto import (
    salgados,
    bolos,
    bebidas
)

logger = logging.getLogger("api.services.produto_composto")


def calcular_componentes(id_produto, fator, estrutura, escolhas_opcionais):
    itens_fixos = repo_get_itens_fixos(id_produto)
    if itens_fixos is False:
        return False
    resultado = []
    cp = estrutura.get("calculo_pessoa")
    if cp:
        for i in itens_fixos:
            if not i["tipo_item"]:
                resultado.append(
                    {"id_produto": i["id_produto"],
                     "quantidade": float(i["quantidade"])})
        por_tipo = {}
        for i in itens_fixos:
            if i["tipo_item"]:
                por_tipo.setdefault(i["tipo_item"], []).append(i)
        for tipo, grupo in por_tipo.items():
            if tipo == "salgado":
                resultado.extend(salgados(grupo, fator, cp["salgados_unid"]))
            elif tipo == "bebida":
                resultado.extend(bebidas(grupo, fator, cp["bebida_ml"]))
            elif tipo == "bolo":
                resultado.extend(bolos(grupo, fator, cp["bolo_g"]))
    else:
        for i in itens_fixos:
            resultado.append(
                {"id_produto": i["id_produto"],
                 "quantidade": float(i["quantidade"]) * fator})
    for chave, ids in escolhas_opcionais.items():
        if not ids:
            continue
        opcionais = repo_get_opcionais_escolhidos(id_produto, chave, ids)
        if opcionais is False:
            return False
        resultado.extend({"id_produto": op["id_produto"], "quantidade": float(
            op["quantidade"])} for op in opcionais)
    return resultado


def montar_itens(produto_pai, fator, componentes, id_loja):
    itens = [{
        "cod_produto": produto_pai["id"],
        "descricao": produto_pai["descricao"],
        "tipo_embalagem": produto_pai["tipo_embalagem"],
        "peso_liquido": produto_pai["peso_liquido"],
        "setor": produto_pai["setor"],
        "id_setor": produto_pai["id_setor"],
        "quantidade": fator,
        "quantidade_un": 1,
        "preco_venda": produto_pai["preco_venda"],
        "total": (round(produto_pai["preco_venda"] *
                        fator *
                        float(produto_pai["peso_liquido"] or 0), 2)),
        "observacao": "",
        "cod_produto_associado": "",
        "desc_produto_associado": "",
    }]
    for comp in componentes:
        detalhe = repo_get_produto_detalhe(comp["id_produto"], id_loja)
        if not detalhe:
            logger.warning(
                f"""Produto {comp['id_produto']} não
                encontrado na loja {id_loja}""")
            continue
        itens.append({
            "cod_produto": detalhe["id"],
            "descricao": detalhe["descricao"],
            "tipo_embalagem": detalhe["tipo_embalagem"],
            "peso_liquido": detalhe["peso_liquido"],
            "setor": detalhe["setor"],
            "id_setor": detalhe["id_setor"],
            "quantidade": comp["quantidade"],
            "quantidade_un": comp["quantidade"],
            "preco_venda": 0,
            "total": 0,
            "observacao": "",
            "cod_produto_associado": produto_pai["id"],
            "desc_produto_associado": produto_pai["descricao"],
        })
    return itens
