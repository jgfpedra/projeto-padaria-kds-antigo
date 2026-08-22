async function pesquisarEncomendas() {
  $("#cards-container").html("");

  const filtros = {
    data_tipo: document.getElementById("data_tipo").value,
    data_inicio: document.getElementById("data_inicio").value,
    data_fim: document.getElementById("data_fim").value,
    tipo_entrega: document.getElementById("tipo_entrega").value,
    id_loja: document.getElementById("loja").value,
    cliente: document.getElementById("cliente").value,
    status: document.getElementById("status").value,
  };

  try {
    const response = await fetch("/api/encomendas/consulta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(filtros),
    });

    const pedidos = await response.json();
    if (!pedidos.length) {
      $("#cards-container").html(
        '<p class="text-center">Nenhum pedido encontrado.</p>',
      );
      return;
    }

    pedidos.sort((a, b) => new Date(a.data_entrega) - new Date(b.data_entrega));

    pedidos.forEach((pedido) => {
      const hoje = new Date().toISOString().split("T")[0];
      let faixa = "";
      if (pedido.data_entrega === hoje) {
        faixa = '<span class="badge bg-success">HOJE</span>';
      } else if (
        new Date(pedido.data_entrega) < new Date() &&
        pedido.id_status === 1
      ) {
        faixa = '<span class="badge bg-danger">ATRASADO</span>';
      }

      const itensHtml = pedido.itens
        .map(
          (item) => `
                <li>${item.quantidade_un} UN - ${item.descricao} ${item.observacao ? "(<em>" + item.observacao + "</em>)" : ""}</li>
            `,
        )
        .join("");

      const card = `
            <div class="col-md-6">
                <div class="card shadow-sm">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <h5>Pedido #${pedido.id}</h5>
                            ${faixa}
                        </div>
                        <p><strong>Cliente:</strong> ${pedido.nome_cliente} - ${pedido.telefone}</p>
                        <p><strong>Tipo Entrega:</strong> ${pedido.tipo_entrega.toUpperCase()}</p>
                        ${pedido.tipo_entrega === "entrega" ? `<p><strong>Endereço:</strong> ${pedido.endereco}</p>` : ""}
                        ${pedido.observacoes ? `<p><strong>Observação:</strong> ${pedido.observacoes}</p>` : ""}
                        <ul>${itensHtml}</ul>
                        <p><strong>Data Pedido:</strong> ${pedido.data_pedido}</p>
                        <p><strong>Entrega:</strong> ${pedido.data_entrega} - ${pedido.hora_entrega}</p>
                        <p><strong>Loja:</strong> ${pedido.nome_loja}</p>
                        <div class="mt-3 d-flex gap-2">
                            <button class="btn btn-warning btn-sm" onclick="abrirModalStatus(${pedido.id})">Status</button>
                            <button class="btn btn-info btn-sm" onclick="abrirModalEditar(${pedido.id})">Editar</button>
                            <button class="btn btn-success btn-sm" onclick="abrirModalFinalizar(${pedido.id})">Finalizar</button>
                        </div>
                    </div>
                </div>
            </div>`;

      $("#cards-container").append(card);
    });
  } catch (error) {
    console.error("Erro ao buscar encomendas:", error);
    $("#cards-container").html(
      '<p class="text-center text-danger">Erro ao buscar pedidos.</p>',
    );
  }
}

function abrirModalStatus(idPedido) {
  const modal = `
    <div class="modal fade" id="modalStatus" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Alterar Status - Pedido #${idPedido}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <select id="novo_status" class="form-select">
              <option value="2">Pronto</option>
              <option value="3">Entregue</option>
              <option value="4">Cancelado</option>
            </select>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
            <button type="button" class="btn btn-primary" onclick="salvarNovoStatus(${idPedido})">Salvar</button>
          </div>
        </div>
      </div>
    </div>`;

  $("#modais").html(modal);
  new bootstrap.Modal(document.getElementById("modalStatus")).show();
}

function abrirModalEditar(idPedido) {
  const modal = `
    <div class="modal fade" id="modalEditar" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Editar Produtos - Pedido #${idPedido}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <p>Funcionalidade de edição dos produtos virá aqui...</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
            <button type="button" class="btn btn-primary" onclick="salvarEdicaoPedido(${idPedido})">Salvar</button>
          </div>
        </div>
      </div>
    </div>`;

  $("#modais").html(modal);
  new bootstrap.Modal(document.getElementById("modalEditar")).show();
}

function abrirModalFinalizar(idPedido) {
  const modal = `
    <div class="modal fade" id="modalFinalizar" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Finalizar Pedido #${idPedido}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <input type="text" id="numero_ficha" class="form-control" placeholder="Número da Ficha">
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
            <button type="button" class="btn btn-success" onclick="salvarFinalizacaoPedido(${idPedido})">Salvar</button>
          </div>
        </div>
      </div>
    </div>`;

  $("#modais").html(modal);
  new bootstrap.Modal(document.getElementById("modalFinalizar")).show();
}
