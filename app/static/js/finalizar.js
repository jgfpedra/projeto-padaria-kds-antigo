let _fin = null;
let _filaFin = Promise.resolve();
const totalItemFin = (it) => it.preco_venda * (it.peso || 0);
const qtdFin = (it) => (it.peso > 0 ? it.peso : it.un);

const brl = (v) =>
  Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function abrirModalFinalizar(idPedido, impresso) {
  return abrirModalFinalizacao(idPedido, "ficha", impresso);
}

function abrirModalFinalizarVRFood(idPedido) {
  return abrirModalFinalizacao(idPedido, "vrfood", true);
}

async function abrirModalFinalizacao(idPedido, sistema, impresso) {
  if (!impresso) {
    alert("Imprima o pedido primeiro!");
    return;
  }
  try {
    const response = await fetch(`/api/pedido/${idPedido}`);
    const pedido = await response.json();
    if (!pedido || pedido.erro) {
      alert("Erro ao buscar pedido para finalização.");
        return;
    }
    _fin = {
      idPedido,
      sistema,
      idLoja: pedido.id_loja,
      itens: (pedido.itens || []).map((it) => {
        const peso = parseFloat(it.quantidade) || 0;
        const un = Number(it.quantidade_un) || 0;
        return {
          cod_produto: String(it.cod_produto),
          descricao: it.descricao,
          preco_venda: parseFloat(it.preco_venda) || 0,
          id_setor: it.id_setor || null,
          peso,
          un,
          pesoUn: parseFloat(it.peso_bruto) || (un > 0 ? peso / un : 0),
          observacao: it.observacao || "",
          cod_produto_associado: it.cod_produto_associado || "",
        };
      }),
    };

    const titulo = sistema === "ficha" ? "Finalizar Pedido (VR Ficha)" : "Finalizar Pedido (VRFood)";
    const campoFicha =
      sistema === "ficha"
        ? `<div class="mb-3">
             <label for="numeroFicha" class="form-label">Número da Ficha</label>
             <input type="text" id="numeroFicha" class="form-control" placeholder="Digite o número da ficha">
           </div>`
        : "";

    const modalHtml = `
    <div class="modal fade" id="modalFinalizacao" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">${titulo} - Pedido #${idPedido}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fechar"></button>
          </div>
          <div class="modal-body">
            ${campoFicha}

            <label class="form-label">Etiqueta ou código do produto</label>
            <input type="text" id="finCodigo" class="form-control"
                   placeholder="Bipe a etiqueta ou digite o código e pressione ENTER" autocomplete="off">
            <small id="finMsg" class="text-danger"></small>

            <div id="finAddArea" class="mt-3"></div>

            <hr>
            <div class="table-responsive">
              <table class="table table-sm table-bordered align-middle">
                <thead>
                  <tr>
                    <th>Cod</th>
                    <th>Descrição</th>
                    <th style="width:110px">Peso (Kg)</th>
                    <th style="width:100px">Unidade</th>
                    <th>Preço</th>
                    <th>Total</th>
                    <th style="width:60px"></th>
                  </tr>
                </thead>
                <tbody id="finTbody"></tbody>
              </table>
            </div>
            <div class="d-flex justify-content-end pe-3">
              <h5 id="finTotal">Valor Total: ${brl(0)}</h5>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
            <button type="button" class="btn btn-success" onclick="salvarFinalizacao()">Finalizar</button>
          </div>
        </div>
      </div>
    </div>`;

    $("#modais").html(modalHtml);
    const el = document.getElementById("modalFinalizacao");
    const modal = new bootstrap.Modal(el);
    el.addEventListener("shown.bs.modal", () =>
      document.getElementById(sistema === "ficha" ? "numeroFicha" : "finCodigo").focus(),
    );
    el.addEventListener("hidden.bs.modal", () => {
      _fin = null;
      el.remove();
    });

    document.getElementById("finCodigo").addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        const v = ev.target.value.trim();
        ev.target.value = "";
        if (v) processarEntradaFin(v);
      }
    });

    el.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter") return;
      const alvo = ev.target;
      const valor = (alvo.value || "").trim();
      const semUnderscore = valor.replace(/^_/, "");
      const ehEtiqueta = /^\d{13}$/.test(semUnderscore);
      if (alvo.id === "finCodigo") {
        ev.preventDefault();
        alvo.value = "";
        if (valor) processarEntradaFin(valor);
        return;
      }
      if (ehEtiqueta && alvo.tagName === "INPUT") {
        ev.preventDefault();
        alvo.value = alvo.defaultValue;
        processarEntradaFin(semUnderscore);
        return;
      }
      if (alvo.id === "numeroFicha") {
        ev.preventDefault();
        document.getElementById("finCodigo")?.focus();
      }
    });

    renderTabelaFin();
    modal.show();
  } catch (e) {
    console.error(e);
    alert("Erro ao abrir pedido para finalização.");
  }
}

// ---------- entrada: etiqueta (bip) ou código digitado ----------
function setMsgFin(msg) {
  const el = document.getElementById("finMsg");
  if (el) el.textContent = msg || "";
}

function processarEntradaFin(valor) {
  // enfileira: cada leitura espera a anterior terminar
  _filaFin = _filaFin.then(() => _processarEntradaFin(valor)).catch(console.error);
  return _filaFin;
}

async function _processarEntradaFin(valor) {
  setMsgFin("");
  document.getElementById("finAddArea").innerHTML = "";

  const semUnderscore = String(valor).trim().replace(/^_/, "");
  if (/^\d{13}$/.test(semUnderscore)) {
    await adicionarPorEtiquetaFin(semUnderscore);
  } else {
    await adicionarPorCodigoFin(semUnderscore);
  }
  document.getElementById("finCodigo")?.focus();
}

function parseEtiquetaBalanca(raw) {
  const s = String(raw || "").trim().replace(/^_/, "");
  if (!/^\d{13}$/.test(s)) return null;
  const codigo = String(parseInt(s.slice(1, 5), 10));
  const inteiro = parseInt(s.slice(5, 10), 10);
  const decimal = parseInt(s.slice(10, 13), 10);
  const centavos = inteiro * 100 + Math.round(decimal / 10);
  if (!parseInt(codigo, 10) || centavos <= 0) return null;
  return { codigo, centavos, valor: centavos / 100 };
}

async function buscarProdutoFin(cod) {
  const r = await fetch(
    `/api/produto/${encodeURIComponent(cod)}?id_pedido=${_fin.idPedido}`,
  );
  if (!r.ok) return null;
  const p = await r.json();
  if (!p || p.erro) return null;
  return {
    cod_produto: String(p.cod_produto ?? cod),
    descricao: p.descricao,
    preco_venda: parseFloat(p.preco_venda) || 0,
    id_setor: p.id_setor || null,
    setor: p.descricao_setor || "",
    tipo_embalagem: p.tipo_embalagem || "",
    peso_unitario: parseFloat(p.peso_unitario) || 0,
    unidade: p.unidade || "UN",
  };
}

async function adicionarPorEtiquetaFin(raw) {
  const et = parseEtiquetaBalanca(raw);
  if (!et) return setMsgFin("Etiqueta inválida!");

  const doProduto = _fin.itens.filter((i) => i.cod_produto === et.codigo);
  const ref = doProduto[0];
  const prod = ref || (await buscarProdutoFin(et.codigo));
  if (!prod) return setMsgFin(`Produto ${et.codigo} não encontrado.`);
  if (!prod.preco_venda) return setMsgFin("Produto sem preço de venda.");

  const peso = +(et.valor / prod.preco_venda).toFixed(3);
  const pesoUn = prod.pesoUn ?? prod.peso_unitario ?? 0;

  const jaSubstituiu = doProduto.some((i) => i.etiqueta);
  const alvo = jaSubstituiu ? null : doProduto.find((i) => !i.etiqueta);

  if (alvo) {
    alvo.peso = peso;
    alvo.un = 0;
    alvo.etiqueta = true;
  } else {
    _fin.itens.push({
      cod_produto: prod.cod_produto,
      descricao: prod.descricao,
      preco_venda: prod.preco_venda,
      id_setor: prod.id_setor,
      peso,
      un: 0,
      pesoUn,
      etiqueta: true,
      observacao: "",
      cod_produto_associado: "",
    });
  }
  renderTabelaFin();
}

async function adicionarPorCodigoFin(cod) {
  const prod = await buscarProdutoFin(cod);
  if (!prod) return setMsgFin(`Produto ${cod} não encontrado.`);
  mostrarFormAdicionarFin(prod);
}

// ---------- componente de adicionar item (PROVISÓRIO) ----------
// Quando você enviar o outro arquivo, substituímos esta função
// pelos mesmos componentes da tela de pedido.
async function mostrarFormAdicionarFin(prod) {
  const area = document.getElementById("finAddArea");
  const num = (v) => parseFloat(String(v ?? "").replace(",", ".")) || 0;

  let associados = [];
  try {
    const r = await fetch(
      `/api/produtos/opcoes_associadas/${encodeURIComponent(prod.cod_produto)}`,
    );
    if (r.ok) associados = await r.json();
  } catch (_) {}

  const optsAssoc = associados.length
    ? `<option value="">Selecione...</option>` +
      associados.map((a) => `<option value="${a.id}">${a.nome}</option>`).join("")
    : "";

  area.innerHTML = `
    <div class="border rounded p-3 bg-light">
      <div class="row g-2">
        <div class="col-md-2">
          <label class="form-label mb-0">ID Produto</label>
          <input type="text" class="form-control form-control-sm" value="${prod.cod_produto}" readonly>
        </div>
        <div class="col-md-${associados.length ? 4 : 6}">
          <label class="form-label mb-0">Descrição Produto</label>
          <input type="text" class="form-control form-control-sm" value="${prod.descricao}" readonly>
        </div>
        ${
          associados.length
            ? `<div class="col-md-4">
                 <label class="form-label mb-0">Item Produção</label>
                 <select id="finAddAssoc" class="form-select form-select-sm">${optsAssoc}</select>
               </div>`
            : ""
        }
        <div class="col-md-2">
          <label class="form-label mb-0">Embalagem</label>
          <input type="text" class="form-control form-control-sm" value="${prod.tipo_embalagem || ""}" readonly>
        </div>
      </div>

      <div class="row g-2 mt-1">
        <div class="col-md-2">
          <label class="form-label mb-0">Peso Unitário</label>
          <input type="text" id="finAddPesoUn" class="form-control form-control-sm" value="${prod.peso_unitario || ""}" placeholder="0,000">
        </div>
        <div class="col-md-2">
          <label class="form-label mb-0">Setor</label>
          <input type="text" class="form-control form-control-sm" value="${prod.setor || ""}" readonly>
        </div>
        <div class="col-md-2">
          <label class="form-label mb-0">Peso Total</label>
          <input type="number" step="any" id="finAddPeso" class="form-control form-control-sm" placeholder="0,000">
        </div>
        <div class="col-md-2">
          <label class="form-label mb-0">Unidades</label>
          <input type="number" step="any" id="finAddUn" class="form-control form-control-sm" placeholder="0">
        </div>
        <div class="col-md-2">
          <label class="form-label mb-0">Preço Venda</label>
          <input type="text" class="form-control form-control-sm" value="${prod.preco_venda.toFixed(2)}" readonly>
        </div>
        <div class="col-md-2">
          <label class="form-label mb-0">Total</label>
          <input type="text" id="finAddTotal" class="form-control form-control-sm" value="0.00" readonly>
        </div>
      </div>

      <div class="row g-2 mt-1">
        <div class="col-12">
          <label class="form-label mb-0">Observação</label>
          <input type="text" id="finAddObs" class="form-control form-control-sm" placeholder="Detalhes do item...">
        </div>
      </div>

      <div class="d-flex justify-content-end gap-2 mt-3">
        <button type="button" class="btn btn-outline-secondary btn-sm" id="finAddCancel">Cancelar</button>
        <button type="button" class="btn btn-primary btn-sm" id="finAddBtn">Adicionar Produto</button>
      </div>
    </div>`;

  const elPesoUn = document.getElementById("finAddPesoUn");
  const elPeso = document.getElementById("finAddPeso");
  const elUn = document.getElementById("finAddUn");
  const elTotal = document.getElementById("finAddTotal");

  const calcTotal = () => {
    elTotal.value = (num(elPeso.value) * prod.preco_venda).toFixed(2);
  };
  elUn.addEventListener("input", () => {
    const un = num(elUn.value);
    const pu = num(elPesoUn.value);
    if (un > 0 && pu > 0) elPeso.value = (un * pu).toFixed(3);
    calcTotal();
  });
  elPeso.addEventListener("input", calcTotal);
  elPesoUn.addEventListener("input", () => {
    const un = num(elUn.value);
    const pu = num(elPesoUn.value);
    if (un > 0 && pu > 0) elPeso.value = (un * pu).toFixed(3);
    calcTotal();
  });

  const fechar = () => {
    area.innerHTML = "";
    document.getElementById("finCodigo")?.focus();
  };

  const confirmar = () => {
    const un = num(elUn.value);
    const peso = num(elPeso.value);
    const selAssoc = document.getElementById("finAddAssoc");

    if (selAssoc && !selAssoc.value) return alert("Selecione o item associado!");
    if (un <= 0 && peso <= 0) return alert("Informe uma quantidade válida.");

    const pesoUn = num(elPesoUn.value);
    _fin.itens.push({
      cod_produto: prod.cod_produto,
      descricao: prod.descricao,
      preco_venda: prod.preco_venda,
      id_setor: prod.id_setor,
      peso: peso > 0 ? peso : +(un * pesoUn).toFixed(3),
      un: un > 0 ? un : 0,
      pesoUn,
      observacao: document.getElementById("finAddObs").value.trim(),
      cod_produto_associado: selAssoc ? selAssoc.value : "",
    });  
    fechar();
    renderTabelaFin();
  };

  document.getElementById("finAddBtn").onclick = confirmar;
  document.getElementById("finAddCancel").onclick = fechar;
  area.querySelectorAll("input:not([readonly])").forEach((inp) =>
    inp.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        confirmar();
      }
    }),
  );

  (prod.unidade === "KG" ? elPeso : elUn).focus();
}

function renderTabelaFin() {
  const tbody = document.getElementById("finTbody");
  if (!tbody || !_fin) return;

  tbody.innerHTML =
    _fin.itens
      .map(
        (it, i) => `
      <tr>
        <td>${it.cod_produto}</td>
        <td>${it.descricao}</td>
        <td>
          <input type="number" step="0.001" min="0" id="finPeso-${i}" class="form-control form-control-sm"
                 value="${it.peso}" onchange="alterarCampoFin(${i}, 'peso', this.value)">
        </td>
        <td>
          <input type="number" step="1" min="0" id="finUn-${i}" class="form-control form-control-sm"
                 value="${it.un}" onchange="alterarCampoFin(${i}, 'un', this.value)">
        </td>
        <td>${brl(it.preco_venda)}</td>
        <td id="finLinhaTotal-${i}">${brl(totalItemFin(it))}</td>
        <td class="text-center">
          <button type="button" class="btn btn-sm btn-outline-danger" onclick="removerItemFin(${i})">&times;</button>
        </td>
      </tr>`,
      )
      .join("") ||
    `<tr><td colspan="7" class="text-center text-muted">Nenhum item</td></tr>`;

  atualizarTotalFin();
}

function alterarCampoFin(i, campo, valor) {
  const it = _fin.itens[i];
  const v = parseFloat(valor) || 0;
  if (campo === "peso") {
    it.peso = v;
    if (it.un > 0 && it.pesoUn > 0) it.un = Math.round(v / it.pesoUn);
  } else {
    it.un = v;
    if (v > 0 && it.pesoUn > 0) it.peso = +(v * it.pesoUn).toFixed(3);
  }
  const elPeso = document.getElementById(`finPeso-${i}`);
  const elUn = document.getElementById(`finUn-${i}`);
  const elTot = document.getElementById(`finLinhaTotal-${i}`);
  if (elPeso) elPeso.value = it.peso;
  if (elUn) elUn.value = it.un;
  if (elTot) elTot.textContent = brl(totalItemFin(it));
  atualizarTotalFin();
}

function atualizarTotalFin() {
  if (!_fin) return;
  const total = _fin.itens.reduce((acc, it) => acc + totalItemFin(it), 0);
  const el = document.getElementById("finTotal");
  if (el) el.textContent = "Valor Total: " + brl(total);
}

// ---------- tabela editável ----------
function alterarQtdFin(i, valor) {
  const it = _fin.itens[i];
  it.qtd = parseFloat(valor) || 0;
  if (it.tipo === "KG") it.kg = it.qtd;
  else if (it.peso_bruto > 0) it.kg = +(it.qtd * it.peso_bruto).toFixed(3);
  const cel = document.getElementById(`finLinhaTotal-${i}`);
  if (cel) cel.textContent = brl(totalItemFin(it));
  atualizarTotalFin();
}

function atualizarTotalFin() {
  const total = _fin.itens.reduce((acc, it) => acc + totalItemFin(it), 0);
  const el = document.getElementById("finTotal");
  if (el) el.textContent = "Valor Total: " + brl(total);
}

function removerItemFin(i) {
  _fin.itens.splice(i, 1);
  renderTabelaFin();
}

// ---------- salvar ----------
// Ajuste aqui caso o back espere outro formato para UN
function montarPayloadItensFin() {
  return _fin.itens.map((it) => ({
    cod_produto: it.cod_produto,
    quantidade: it.peso,
    quantidade_un: Math.round(it.un),
    preco_venda: it.preco_venda,
    id_setor: it.id_setor,
    peso_bruto: it.pesoUn || 0,
    observacao: it.observacao || "",
    cod_produto_associado: it.cod_produto_associado || "",
  }));
}

async function salvarFinalizacao() {
  if (!_fin) return;

  if (!_fin.itens.length) return alert("Adicione ao menos um item.");
  if (_fin.itens.some((i) => !(qtdFin(i) > 0))) return alert("Há itens com quantidade zerada.");

  const body = { id_pedido: _fin.idPedido, itens: montarPayloadItensFin() };
  let url = "/api/encomenda/finalizar_vrfood";

  if (_fin.sistema === "ficha") {
    const numeroFicha = document.getElementById("numeroFicha").value.trim();
    if (!numeroFicha) return alert("Por favor, digite o número da ficha.");
    body.numero_ficha = numeroFicha;
    url = "/api/encomenda/finalizar";
  }

  try {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const res = await r.json();

    if (r.ok) {
      alert("Pedido finalizado com sucesso!");
      bootstrap.Modal.getInstance(document.getElementById("modalFinalizacao"))?.hide();
      pesquisarEncomendas();
    } else {
      alert("Erro ao finalizar: " + (res.erro || ""));
    }
  } catch (e) {
    console.error(e);
    alert("Erro ao finalizar pedido.");
  }
}
