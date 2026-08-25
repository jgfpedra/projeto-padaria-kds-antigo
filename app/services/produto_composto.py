import logging

from app.repo.produto_composto import (
    repo_get_calculos_pessoa,
    repo_get_itens_fixos,
    repo_get_opcionais_escolhidos,
    repo_get_produto_detalhe,
    repo_get_produtos_compostos,
    repo_get_quantidade_total_grupo,
    repo_remover_produto_composto,
    repo_salvar_produto_composto,
)
from app.utils.produto_composto import bebidas, bolos, salgados
from app.utils.conversions import to_float

logger = logging.getLogger("api.services.produto_composto")


def svc_get_produtos_compostos():
    return repo_get_produtos_compostos()


def svc_salvar_produtos_compostos(dados):
    return repo_salvar_produto_composto(dados)


def svc_remover_produtos_compostos(id_produto):
    return repo_remover_produto_composto(id_produto)


def svc_get_calculos_pessoa():
    return repo_get_calculos_pessoa()


def calcular_componentes(id_produto, fator, estrutura, escolhas_opcionais):
    itens_fixos = repo_get_itens_fixos(id_produto)
    if itens_fixos is False:
        return False
    cp = estrutura.get("calculo_pessoa")
    if not cp:
        resultado = [
            {
                "id_produto": i["id_produto"],
                "quantidade": float(i["quantidade"]) * fator,
            }
            for i in itens_fixos
        ]
    else:
        calc = {"salgado": salgados, "bebida": bebidas, "bolo": bolos}
        resultado = []
        por_tipo = {}
        for i in itens_fixos:
            if not i["tipo_item"]:
                resultado.append(
                    {
                        "id_produto": i["id_produto"],
                        "quantidade": float(i["quantidade"]) * fator,
                    }
                )
            else:
                por_tipo.setdefault(i["tipo_item"], []).append(i)
        args = {
            "salgado": cp["salgados_unid"],
            "bebida": cp["bebida_ml"],
            "bolo": cp["bolo_g"],
        }
        for tipo, grupo in por_tipo.items():
            if tipo in calc:
                resultado.extend(calc[tipo](grupo, fator, args[tipo]))

    for chave, ids in escolhas_opcionais.items():
        if not ids:
            continue
        opcionais = repo_get_opcionais_escolhidos(id_produto, chave, ids)
        if opcionais is False:
            return False
        qtd_total = repo_get_quantidade_total_grupo(id_produto, chave)
        qtd_por_item = qtd_total / len(ids) if ids else 0
        resultado.extend(
            {
                "id_produto": op["id_produto"],
                "quantidade": qtd_por_item * fator,
            }
            for op in opcionais
        )
    return resultado


def montar_itens(produto_pai, fator, componentes, id_loja):
    itens = []
    for comp in componentes:
        detalhe = repo_get_produto_detalhe(comp["id_produto"], id_loja)
        if not detalhe:
            logger.warning(f"""Produto {comp['id_produto']} não
                encontrado na loja {id_loja}""")
            continue
        itens.append(
            {
                "cod_produto": detalhe["id"],
                "descricao": detalhe["descricao"],
                "tipo_embalagem": detalhe["tipo_embalagem"],
                "peso_liquido": detalhe["peso_liquido"],
                "setor": detalhe["setor"],
                "id_setor": detalhe["id_setor"],
                "quantidade": (to_float(comp["quantidade"]) *
                               to_float(detalhe["peso_liquido"])),
                "quantidade_un": comp["quantidade"],
                "preco_venda": 0,
                "total": 0,
                "observacao": f"Composto: {produto_pai["descricao"]}",
            }
        )
    return itens
