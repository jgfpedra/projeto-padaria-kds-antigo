import logging
from flask import jsonify, request
from app import app
from flask_login import login_required
from app.services.acougue import (
    svc_get_pendencias,
    svc_salvar_pendencias,
    svc_atualizar_falta,
    svc_vincular_pedido_atual,
)

logger = logging.getLogger("route.acougue")


@app.route("/api/acougue/pendencias", methods=["GET"])
@login_required
def acougue_pendencias_get():
    id_cliente = request.args.get("id_cliente", type=int)
    id_loja = request.args.get("id_loja", type=int)
    if not id_cliente or not id_loja:
        return jsonify({"pendencias": []})
    return jsonify({"pendencias": svc_get_pendencias(id_cliente, id_loja)})


@app.route("/api/acougue/pendencias", methods=["POST"])
@login_required
def acougue_pendencias_post():
    body = request.get_json()
    id_cliente = int(body.get("id_cliente", 0))
    pendencias = body.get("pendencias", [])
    return jsonify(svc_salvar_pendencias(id_cliente, pendencias))


@app.route("/api/acougue/pendencias/<int:id_pendencia>", methods=["PATCH"])
@login_required
def acougue_pendencia_patch(id_pendencia):
    body = request.get_json()
    enviado = float(body.get("enviado", 0))
    return jsonify(svc_atualizar_falta(id_pendencia, enviado))


@app.route("/api/acougue/pendencias/pedido/<int:id_pedido>", methods=["PATCH"])
@login_required
def acougue_pendencia_vincular(id_pedido):
    body = request.get_json()
    id_cliente = int(body.get("id_cliente", 0))
    ids_produto = body.get("ids_produto", [])
    return jsonify(svc_vincular_pedido_atual(id_pedido, id_cliente, ids_produto))
