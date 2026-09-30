function toggleBlock(n) {
  const bloco = document.querySelector(`.accordion-block[data-block="${n}"]`);
  const jaAberto = bloco.classList.contains("open");
  document
    .querySelectorAll(".accordion-block")
    .forEach((b) => b.classList.remove("open"));
  if (!jaAberto) bloco.classList.add("open");
  atualizarResumos();
}

function avancarBloco(atual) {
  atualizarResumos();
  document
    .querySelectorAll(".accordion-block")
    .forEach((b) => b.classList.remove("open"));
  const proximo = document.querySelector(
    `.accordion-block[data-block="${atual + 1}"]`,
  );
  if (proximo) proximo.classList.add("open");
}

function voltarBloco(atual) {
  document
    .querySelectorAll(".accordion-block")
    .forEach((b) => b.classList.remove("open"));
  const anterior = document.querySelector(
    `.accordion-block[data-block="${atual - 1}"]`,
  );
  if (anterior) anterior.classList.add("open");
}

function atualizarResumos() {
  // Bloco 1: cliente, telefone, tipo
  const cliente = document.getElementById("cliente").value.trim();
  const telefone = document.getElementById("telefone").value.trim();
  const tipoSelecionado = document.querySelector(
    'input[name="tipo_entrega"]:checked',
  );
  const tipoLabel = tipoSelecionado
    ? document
        .querySelector(`label[for="${tipoSelecionado.id}"]`)
        .textContent.trim()
    : "";

  let resumo1 = "Preencha os dados do cliente";
  if (cliente) {
    resumo1 = cliente;
    if (telefone) resumo1 += ` · ${telefone}`;
    if (tipoLabel) resumo1 += ` · ${tipoLabel}`;
  }
  document.getElementById("resumo-bloco-1").textContent = resumo1;

  // Bloco 2: quantidade de itens
  const linhas = document.querySelectorAll("#tabela_itens tbody tr").length;
  document.getElementById("resumo-bloco-2").textContent =
    linhas === 0
      ? "Nenhum item adicionado"
      : linhas === 1
        ? "1 item adicionado"
        : `${linhas} itens adicionados`;

  // Bloco 3: total
  const total = document.getElementById("valor_total_pedido").value || "0,00";
  document.getElementById("resumo-bloco-3").textContent = `Total: R$ ${total}`;
}

// Atualiza resumo do cliente ao digitar/selecionar (chame também no seu JS de sugestões)
document.getElementById("cliente").addEventListener("input", atualizarResumos);
document.getElementById("telefone").addEventListener("input", atualizarResumos);
document
  .querySelectorAll('input[name="tipo_entrega"]')
  .forEach((r) => r.addEventListener("change", atualizarResumos));

// Abre o primeiro bloco por padrão
document
  .querySelector('.accordion-block[data-block="1"]')
  .classList.add("open");
atualizarResumos();
