// acougue.js — Módulo de controle de pendências do açougue
// Setor ID: 15 | Loja ID: 2
// Requer: Bootstrap 5, as variáveis globais do kds.html (pedidos, setorSelecionado, lojaSelecionada)

const ACOUGUE_SETOR_ID = "15";
const ACOUGUE_LOJA_ID = "2";

// ─── Persistência via backend (acougue.txt) ──────────────────────────────────

async function acougue_ler_pendencias(idCliente) {
  try {
    const res = await fetch(`/api/acougue/pendencias?id_cliente=${idCliente}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.pendencias || [];
  } catch {
    return [];
  }
}

async function acougue_salvar_pendencias(pendencias, idCliente) {
  await fetch("/api/acougue/pendencias", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pendencias, id_cliente: idCliente }),
  });
}
// ─── Modal de quantidade enviada ────────────────────────────────────────────

function acougue_criarModal() {
  if (document.getElementById("modalAcougue")) return;

  document.body.insertAdjacentHTML(
    "beforeend",
    `
    <div class="modal fade" id="modalAcougue" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header py-2">
            <h5 class="modal-title">🥩 Finalizar — Açougue</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div id="acougue-modal-produto" class="mb-2 fw-bold fs-5"></div>
            <div class="mb-1 text-muted" id="acougue-modal-pedido-total-label"></div>
            <label class="form-label mt-2">Quantidade enviada (kg/un):</label>
            <input
              type="number"
              id="acougue-qtd-input"
              class="form-control"
              min="0"
              step="0.001"
              placeholder="Ex: 2.500"
            />
            <div id="acougue-aviso-falta" class="alert alert-warning mt-3 d-none" role="alert">
              ⚠️ Quantidade menor que o pedido. A diferença será registrada como pendência.
            </div>
          </div>
          <div class="modal-footer py-2">
            <button class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
            <button class="btn btn-success" id="acougue-btn-confirmar">
              <i class="fa-solid fa-check"></i> Confirmar
            </button>
          </div>
        </div>
      </div>
    </div>
  `,
  );
  document
    .getElementById("acougue-qtd-input")
    .addEventListener("input", function () {
      const val = this.value;
      // permite apenas números e vírgula/ponto com até 3 casas decimais
      const regex = /^\d*([.,]\d{0,3})?$/;
      if (!regex.test(val)) {
        this.value = val.slice(0, -1);
      }
    });
}

// ─── Ponto de entrada: intercept do finalizar ────────────────────────────────

async function acougue_abrirModalFinalizar(
  chave,
  dia = null,
  idsOverride = null,
) {
  acougue_criarModal();

  // Monta lista de ids e total a partir dos pedidos globais
  let itensFiltrados = window.pedidos.filter((p) => {
    const k =
      (p.descricao || p.produto || p.id_produto) + "|" + (p.observacao || "");
    if (k !== chave || p.id_status != 1) return false;
    if (dia === "hoje") return window.isHoje(p.data);
    if (dia === "amanha") return window.isAmanha(p.data);
    return true;
  });

  if (idsOverride) {
    itensFiltrados = itensFiltrados.filter((p) =>
      idsOverride.includes(p.id_item),
    );
  }

  if (!itensFiltrados.length) return;

  const nomeProduto =
    itensFiltrados[0].descricao ||
    itensFiltrados[0].produto ||
    itensFiltrados[0].id_produto;
  const observacao = itensFiltrados[0].observacao || "";
  const totalPedido = itensFiltrados.reduce(
    (s, p) => s + parseFloat(p.peso || p.quantidade || 0),
    0,
  );
  const ids = itensFiltrados.map((p) => p.id_item);
  console.log(itensFiltrados[0].id_cliente);
  const idCliente = itensFiltrados[0].id_cliente;
  const CLIENTES_ACOUGUE = ["5306", "131"];

  const isAcougue = itensFiltrados.some(
    (p) => String(p.tipo_entrega || "").toLowerCase() === "acougue",
  );

  // Preenche modal
  const elProduto = document.getElementById("acougue-modal-produto");
  elProduto.textContent = nomeProduto + (observacao ? ` — ${observacao}` : "");
  elProduto.dataset.total = totalPedido;
  elProduto.dataset.chave = chave;
  elProduto.dataset.ids = JSON.stringify(ids);
  elProduto.dataset.isAcougue = isAcougue ? "1" : "0";
  elProduto.dataset.idCliente = idCliente;
  elProduto.dataset.isAcougue =
    isAcougue && CLIENTES_ACOUGUE.includes(String(idCliente)) ? "1" : "0";

  document.getElementById("acougue-modal-pedido-total-label").textContent =
    `Total do pedido: ${totalPedido.toLocaleString("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 })} kg/un`;
  document.getElementById("acougue-qtd-input").value = "";
  document.getElementById("acougue-aviso-falta").classList.add("d-none");

  const modal = new bootstrap.Modal(document.getElementById("modalAcougue"));
  modal.show();

  // Handler do botão confirmar — remove listener anterior para não acumular
  const btnConfirmar = document.getElementById("acougue-btn-confirmar");
  const novoBtn = btnConfirmar.cloneNode(true);
  btnConfirmar.replaceWith(novoBtn);

  novoBtn.addEventListener("click", async () => {
    const enviado = parseFloat(
      document.getElementById("acougue-qtd-input").value.replace(",", "."),
    );
    const idCliente = elProduto.dataset.idCliente;
    const totalReq = parseFloat(elProduto.dataset.total);
    const idsParam = JSON.parse(elProduto.dataset.ids);
    const prodNome = elProduto.textContent;
    const flagAcougue = elProduto.dataset.isAcougue === "1";

    console.log(idCliente);

    if (isNaN(enviado) || enviado < 0) {
      alert("Informe uma quantidade válida.");
      return;
    }

    if (enviado === 0) {
      const confirmar = confirm(
        "Quantidade zero. Deseja registrar tudo como pendência?",
      );
      if (!confirmar) return;
    }

    if (flagAcougue && enviado < totalReq) {
      document.getElementById("acougue-aviso-falta").classList.remove("d-none");
      // aguarda o usuário ver o aviso — o fluxo continua normalmente
    }

    modal.hide();

    const res = await fetch("/api/kds/item/finalizar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: idsParam }),
    });
    const ret = await res.json();
    if (!ret.success) {
      alert("Falha ao finalizar itens!");
      return;
    }
    console.log("3: " + idCliente);
    if (flagAcougue && enviado < totalReq) {
      const falta = totalReq - enviado;
      const pendencias = await acougue_ler_pendencias(idCliente);
      pendencias.push({
        produto: prodNome,
        falta: parseFloat(falta.toFixed(3)),
        data: new Date().toISOString().slice(0, 10),
        enviado: parseFloat(enviado.toFixed(3)),
        totalPedido: parseFloat(totalReq.toFixed(3)),
      });
      await acougue_salvar_pendencias(pendencias, idCliente);
    }

    await window.atualizarPedidos();
  });
}

function acougue_isAcougueAtivo() {
  const loja = document.getElementById("selectLoja").value;
  const setor = document.getElementById("selectSetor").value;
  return loja === ACOUGUE_LOJA_ID && setor === ACOUGUE_SETOR_ID;
}

function acougue_ativarIntercept() {
  const _finalizarPedidos = window.finalizarPedidos;
  const _finalizarPedidosDia = window.finalizarPedidosDia;
  const _atualizarPedidos = window.atualizarPedidos;

  window.finalizarPedidos = async function (chave) {
    if (acougue_isAcougueAtivo()) {
      await acougue_abrirModalFinalizar(chave, null);
    } else {
      await _finalizarPedidos(chave);
    }
  };

  window.finalizarPedidosDia = async function (chave, dia) {
    if (acougue_isAcougueAtivo()) {
      await acougue_abrirModalFinalizar(chave, dia);
    } else {
      await _finalizarPedidosDia(chave, dia);
    }
  };

  window.atualizarPedidos = async function (auto = false) {
    await _atualizarPedidos(auto);
    if (!acougue_isAcougueAtivo()) return;

    const pendencias = await acougue_ler_pendencias();
    if (!pendencias.length) return;

    // Injeta observação nos pedidos de açougue em memória antes de re-renderizar
    let alterou = false;
    window.pedidos.forEach((p) => {
      if (String(p.tipo_entrega || "").toLowerCase() !== "acougue") return;

      const nomeProduto = (p.descricao || p.produto || String(p.id_produto))
        .trim()
        .toLowerCase();

      const pendencia = pendencias.find(
        (pen) => pen.produto.trim().toLowerCase() === nomeProduto,
      );
      if (!pendencia) return;

      const faltaStr = pendencia.falta.toLocaleString("pt-BR", {
        minimumFractionDigits: 3,
        maximumFractionDigits: 3,
      });
      const obs = `Faltando do último pedido de carnes: ${faltaStr} kg/un`;
      if (!(p.observacao || "").includes(obs)) {
        p.observacao = [p.observacao, obs].filter(Boolean).join(" | ");
      }
    });

    if (alterou) window.renderCards();
  };
}

document.addEventListener("DOMContentLoaded", () => {
  acougue_ativarIntercept();
});
