// kds-acougue.js
// Módulo específico do setor Açougue (id 15).
// Depende das variáveis/funções globais de kds.html: pedidos, agrupadosGlobal,
// setorSelecionado, isHoje, isAmanha, atualizarPedidos, escHtml.

(function () {
  const SETOR_ACOUGUE_ID = 15;

  // Campo usado para comparar "pedido vs enviado". Troque para "quantidade"
  // se o controle do açougue for por unidade em vez de peso.
  const CAMPO_QUANTIDADE = "peso";

  const OBS_PENDENCIA = "Faltando do último pedido de carnes";

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
      // religa cada resultado ao grupo original (itens completos)
      const resultados = resultadosBrutos.map((r) => {
        const grupo = grupos.find((g) => g.chave === r.chave);
        return {
          chave: r.chave,
          itens: grupo.itens,
          quantidadeEnviada: r.quantidadeEnviada,
        };
      });
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

  // --- Processa a finalização após o usuário confirmar as quantidades ---
  async function processarFinalizacaoAcougue(resultados) {
    const idsFinalizar = [];
    const pendencias = [];

    resultados.forEach(({ itens, quantidadeEnviada }) => {
      const totalPedido = totalDoGrupo(itens);
      itens.forEach((p) => idsFinalizar.push(p.id_item));

      const faltante = totalPedido - quantidadeEnviada;
      if (faltante > 0.001) {
        const produto =
          itens[0].descricao || itens[0].produto || itens[0].id_produto;
        pendencias.push({
          id_produto: itens[0].id_produto,
          produto: String(produto).trim(),
          quantidade_pedida: totalPedido,
          quantidade_enviada: quantidadeEnviada,
          quantidade_faltante: faltante,
          observacao: OBS_PENDENCIA,
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

      for (const pendencia of pendencias) {
        await fetch("/api/kds/acougue/pendencia", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(pendencia),
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
