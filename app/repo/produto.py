from app.conexao_vr import conectar_vr
import logging

logger = logging.getLogger("repo.produto")


def _coletar_ids_produtos(compostos: list[dict]) -> set[int]:
    """Junta os ids de produto que precisam de descrição:
    o próprio composto + itens + itens dos grupos opcionais."""
    ids_set = set()
    for c in compostos:
        ids_set.add(c["id"])
        for item in (c["itens"] or []):
            ids_set.add(item["id_produto"])
        for grupo in (c["grupos_opcionais"] or []):
            for item in (grupo["itens"] or []):
                ids_set.add(item["id_produto"])
    return ids_set


def _preencher_descricoes(compostos: list[dict],
                          nomes: dict[int, str]) -> None:
    for c in compostos:
        c["nome_produto"] = nomes.get(c["id"], "—")

        for item in (c["itens"] or []):
            item["descricao"] = nomes.get(item["id_produto"], "—")

        for grupo in (c["grupos_opcionais"] or []):
            for item in (grupo["itens"] or []):
                item["descricao"] = nomes.get(item["id_produto"], "—")


def repo_vr_get_nomes_produtos(ids: list[int]):
    if not ids:
        return {}
    try:
        with conectar_vr.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.descricaocompleta
                FROM produto p
                JOIN produtocomplemento pc ON pc.id_produto = p.id
                WHERE p.id = ANY(%s)
                AND pc.id_situacaocadastro = 1
            """, (ids,))
            rows = cur.fetchall()
            return {r[0]: r[1] for r in rows}
    except Exception as e:
        logger.error(e)
        return {}
