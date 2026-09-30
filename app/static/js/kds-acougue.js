// kds-acougue.js

(function () {
  const SETOR_ACOUGUE_ID = 15;
  const CAMPO_QUANTIDADE = "peso";
  function isSetorAcougue() {
    return String(setorSelecionado) === String(SETOR_ACOUGUE_ID);
  }

  function totalDoGrupo(itens) {
    return itens.reduce((s, p) => s + parseFloat(p[CAMPO_QUANTIDADE] || 0), 0);
  }

  // Guarda as funções originais para setores que não são açougue.
  const _finalizarPedidosOriginal = window.finalizarPedidos;
  const _finalizarPedidosDiaOriginal = window.finalizarPedidosDia;
  const _finalizarTodosOriginal = window.finalizarTodos;

  function coletarItensDoGrupo(chave, filtroExtra) {
    return pedidos.filter((p) => {
      const k =
        (p.descricao || p.produto || p.id_produto) + "|" + (p.observacao || "");
      return (
        k === chave && p.id_status == 1 && (!filtroExtra || filtroExtra(p))
      );
    });
  }

  // --- Modal de quantidade enviada ---
  let modalAcougue = null;
  let callbackAtual = null;

  function garantirModal() {
    if (document.getElementById("modalQtdAcougue")) return;
    const div = document.createElement("div");
    div.innerHTML = `
      <div class="modal fade" id="modalQtdAcougue" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">Quantidade enviada</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body" id="modalQtdAcougueBody"></div>
            <div class="modal-footer">
              <button class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
              <button class="btn btn-success" id="btnConfirmarQtdAcougue">Confirmar</button>
            </div>
          </div>
        </div>
      </div>`;
    document.body.appendChild(div.firstElementChild);

    document
      .getElementById("btnConfirmarQtdAcougue")
      .addEventListener("click", () => {
        const linhas = document.querySelectorAll(
          "#modalQtdAcougueBody .qtd-linha",
        );
        const resultados = [];
        for (const linha of linhas) {
          const chave = linha.dataset.chave;
          const input = linha.querySelector(".qtd-input");
          const valor = parseFloat(input.value.replace(",", "."));
          if (isNaN(valor) || valor < 0) {
            input.classList.add("is-invalid");
            return; // não fecha o modal enquanto houver valor inválido
          }
          input.classList.remove("is-invalid");
          resultados.push({ chave, quantidadeEnviada: valor });
        }
        modalAcougue.hide();
        if (callbackAtual) callbackAtual(resultados);
      });
  }

  function abrirModalQuantidade(grupos, aoConfirmar) {
    garantirModal();
    if (!modalAcougue) {
      modalAcougue = new bootstrap.Modal(
        document.getElementById("modalQtdAcougue"),
      );
    }
    callbackAtual = (resultadosBrutos) => {
      const resultados = resultadosBrutos.map((r) => {
        const grupo = grupos.find((g) => g.chave === r.chave);
        return {
          chave: r.chave,
          itens: grupo.itens,
          quantidadeEnviada: r.quantidadeEnviada,
        };
      });
      console.log(resultados);
      aoConfirmar(resultados);
    };

    const body = document.getElementById("modalQtdAcougueBody");
    body.innerHTML = grupos
      .map((g) => {
        const totalPedido = totalDoGrupo(g.itens);
        const totalFormatado = totalPedido.toLocaleString("pt-BR", {
          minimumFractionDigits: 3,
          maximumFractionDigits: 3,
        });
        return `
          <div class="mb-3 qtd-linha" data-chave="${escHtml(g.chave)}">
            <label class="form-label">
              <b>${escHtml(g.produto)}</b><br>
              <span class="text-muted">Pedido: ${totalFormatado} ${CAMPO_QUANTIDADE === "peso" ? "Kg" : "UN"}</span>
            </label>
            <input type="number" step="0.001" min="0" class="form-control qtd-input" value="${totalPedido}">
          </div>`;
      })
      .join("");

    modalAcougue.show();
  }

  async function processarFinalizacaoAcougue(resultados) {
    const idsFinalizar = [];
    const pendenciasPorCliente = {}; // agrupa por id_cliente
    console.log(resultados)
    const CLIENTES_ACOUGUE = ["5306", "131"];
    resultados.forEach(({ itens, quantidadeEnviada }) => {
      console.log("id_cliente dos itens:", itens.map(p => p.id_cliente));
      const totalPedido = totalDoGrupo(itens);
      itens.forEach((p) => idsFinalizar.push(p.id_item));

      const faltante = totalPedido - quantidadeEnviada;
      if (faltante > 0.001) {
        const produto = itens[0].descricao || itens[0].produto || itens[0].id_produto;
        const idCliente = String(itens[0].id_cliente || "");

        if (!CLIENTES_ACOUGUE.includes(idCliente)) return; // ignora outros clientes

        if (!pendenciasPorCliente[idCliente]) pendenciasPorCliente[idCliente] = [];
        pendenciasPorCliente[idCliente].push({
          produto: String(produto).trim(),
          quantidade_pedida: totalPedido,
          quantidade_enviada: quantidadeEnviada,
          falta: parseFloat(faltante.toFixed(3)),
          enviado: parseFloat(quantidadeEnviada.toFixed(3)),
          totalPedido: parseFloat(totalPedido.toFixed(3)),
          data: new Date().toISOString().slice(0, 10),
        });
      }
    });

    if (!idsFinalizar.length) return;

    try {
      const res = await fetch("/api/kds/item/finalizar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: idsFinalizar }),
      });
      const ret = await res.json();
      if (!ret.success) {
        alert("Falha ao finalizar itens!");
        return;
      }
      for (const [idCliente, novas] of Object.entries(pendenciasPorCliente)) {
        const resGet = await fetch(`/api/acougue/pendencias?id_cliente=${idCliente}`);
        const dadosAtuais = await resGet.json();
        const existentes = Array.isArray(dadosAtuais.pendencias) ? dadosAtuais.pendencias : [];
        const payload = {
          id_cliente: idCliente,
          pendencias: [...existentes, ...novas],
        };
        console.log("payload enviado:", JSON.stringify(payload)); // ← adiciona isso
        await fetch("/api/acougue/pendencias", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }

      await atualizarPedidos();
    } catch (e) {
      console.error("Erro ao finalizar itens do açougue:", e);
      alert("Erro ao finalizar itens.");
    }
  }

  // --- Sobrescreve as funções de finalizar só para o setor açougue ---
  window.finalizarPedidos = async function (chave) {
    if (!isSetorAcougue()) return _finalizarPedidosOriginal(chave);
    const itens = coletarItensDoGrupo(chave);
    if (!itens.length) return;
    console.log(itens, chave);
    const produto =
      itens[0].descricao || itens[0].produto || itens[0].id_produto;
    abrirModalQuantidade(
      [{ chave, produto, itens }],
      processarFinalizacaoAcougue,
    );
  };

  window.finalizarPedidosDia = async function (chave, dia) {
    if (!isSetorAcougue()) return _finalizarPedidosDiaOriginal(chave, dia);
    const filtroDia = dia === "hoje" ? isHoje : isAmanha;
    const itens = coletarItensDoGrupo(chave, (p) => filtroDia(p.data));
    if (!itens.length) return;
    console.log(itens, chave);
    const produto =
      itens[0].descricao || itens[0].produto || itens[0].id_produto;
    abrirModalQuantidade(
      [{ chave, produto, itens }],
      processarFinalizacaoAcougue,
    );
  };

  window.finalizarTodos = async function () {
    if (!isSetorAcougue()) return _finalizarTodosOriginal();
    const grupos = [];
    Object.keys(agrupadosGlobal).forEach((chave) => {
      const itens = agrupadosGlobal[chave].filter((p) => p.id_status == 1);
      if (itens.length) {
        const produto =
          itens[0].descricao || itens[0].produto || itens[0].id_produto;
        grupos.push({ chave, produto, itens });
      }
    });
    if (!grupos.length) return;
    abrirModalQuantidade(grupos, processarFinalizacaoAcougue);
  };
})();
