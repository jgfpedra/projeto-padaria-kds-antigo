import logging
from app.repo.acougue import (
    repo_get_pendencias,
    repo_get_produtos_vr,
    repo_inserir_pendencias,
    repo_atualizar_falta,
    repo_vincular_pedido_atual,
)

logger = logging.getLogger("services.acougue")

CLIENTES_ACOUGUE = {5306, 131}


def svc_get_pendencias(id_cliente: int) -> list[dict]:
    rows = repo_get_pendencias(id_cliente)
    if not rows:
        return []

    ids_produto = list({r[1] for r in rows})
    produtos_vr = repo_get_produtos_vr(ids_produto)
    print(produtos_vr)
    return [
        {
            "id": r[0],
            "id_produto": r[1],
            "produto": produtos_vr.get(r[1], {}).get("descricao", str(r[1])),
            "peso_unitario": produtos_vr.get(r[1], {}).get("peso_unitario", 0),
            "embalagem": produtos_vr.get(r[1], {}).get("embalagem", ""),
            "id_setor": produtos_vr.get(r[1], {}).get("id_setor", ""),
            "setor": produtos_vr.get(r[1], {}).get("setor", ""),
            "id_pedido_criacao": r[2],
            "id_pedido_atual": r[3],
            "total_pedido": float(r[4]),
            "falta": float(r[5]),
            "data": str(r[6]) if r[6] else None,
            "preco_venda": float(produtos_vr.get(r[1], {}).get("preco_venda", "") or 0),
            "preco_total": (float(produtos_vr.get(r[1],
                                                  {}).get("preco_venda", "") or 0) * float(r[5] or 0)),
        }
        for r in rows
    ]


def svc_salvar_pendencias(id_cliente: int,
                          pendencias: list[dict],
                          id_pedido: int | None = None) -> dict:
    if id_cliente not in CLIENTES_ACOUGUE:
        return {"ok": True, "ignorado": True}
    repo_inserir_pendencias(id_cliente, pendencias)
    return {"ok": True}


def svc_atualizar_falta(id_pendencia: int, enviado: float) -> dict:
    repo_atualizar_falta(id_pendencia, enviado)
    return {"ok": True}


def svc_vincular_pedido_atual(id_pedido: int,
                              id_cliente: int,
                              ids_produto: list[int]) -> dict:
    if id_cliente not in CLIENTES_ACOUGUE:
        return {"ok": True, "ignorado": True}
    repo_vincular_pedido_atual(id_pedido, id_cliente, ids_produto)
    return {"ok": True}
