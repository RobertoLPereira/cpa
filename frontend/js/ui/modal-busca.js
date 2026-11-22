// ==========================================================================
// UI/MODAL-BUSCA.JS - Pesquisa de produtos [F1] (ImportaProduto)
// ==========================================================================
import { estadoPDV, formatarMoeda } from "../state.js";
import { pdvAPI } from "../api.js";
import { focarEAN } from "./bobina.js";

let produtosEncontrados = [];
let indiceSelecionado = -1;
let timerBusca = null;
let onSelecionarCallback = null;

export function abrirModalBusca(onSelecionar) {
  onSelecionarCallback = onSelecionar;
  estadoPDV.modalAtivo = "BUSCA";
  produtosEncontrados = [];
  indiceSelecionado = -1;

  document.getElementById("modal-procura-produto").classList.remove("hidden");
  const inp = document.getElementById("input-busca-produto");
  inp.value = "";
  inp.focus();
  consultarProdutos();
}

export function fecharModalBusca() {
  estadoPDV.modalAtivo = null;
  document.getElementById("modal-procura-produto").classList.add("hidden");
  focarEAN();
}

export async function consultarProdutos() {
  const termo = document.getElementById("input-busca-produto").value.trim();
  const tbody = document.getElementById("tbody-produtos-busca");
  tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:16px;">Buscando produtos...</td></tr>`;

  try {
    const dados = await pdvAPI.buscarProdutos(termo);
    produtosEncontrados = dados.produtos || [];
    indiceSelecionado = produtosEncontrados.length > 0 ? 0 : -1;
    renderizarTabela();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:16px; color:#cc0000;">${err.message}</td></tr>`;
  }
}

function renderizarTabela() {
  const tbody = document.getElementById("tbody-produtos-busca");
  if (produtosEncontrados.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px; color:#666;">Nenhum produto encontrado com preço maior que zero.</td></tr>`;
    return;
  }

  tbody.innerHTML = produtosEncontrados.map((p, idx) => `
    <tr class="${idx === indiceSelecionado ? "selecionado" : ""}"
        onclick="window.pdvUI.selecionarLinhaBusca(${idx})"
        ondblclick="window.pdvUI.confirmarProdutoBusca()">
      <td>${p.cprod || ""}</td>
      <td>${p.cean || "SEM GTIN"}</td>
      <td>${p.xprod || ""}</td>
      <td style="text-align:center;">${p.ucom || "UN"}</td>
      <td style="text-align:right;">${formatarMoeda(p.vuncom)}</td>
    </tr>
  `).join("");

  const linhaAtiva = tbody.querySelector("tr.selecionado");
  if (linhaAtiva) linhaAtiva.scrollIntoView({ block: "nearest" });
}

export function selecionarLinhaBusca(idx) {
  indiceSelecionado = idx;
  renderizarTabela();
}

export function confirmarProdutoBusca() {
  if (indiceSelecionado < 0 || !produtosEncontrados[indiceSelecionado]) return;
  const prod = produtosEncontrados[indiceSelecionado];
  const eanValido = prod.cean && prod.cean.trim() !== "" && prod.cean !== "SEM GTIN";
  const codigo = eanValido ? prod.cean.trim() : String(prod.cprod).trim();

  fecharModalBusca();
  if (onSelecionarCallback) onSelecionarCallback(codigo);
}

export function inicializarModalBusca() {
  const inp = document.getElementById("input-busca-produto");
  inp.addEventListener("input", () => {
    clearTimeout(timerBusca);
    timerBusca = setTimeout(consultarProdutos, 250);
  });

  inp.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" && indiceSelecionado < produtosEncontrados.length - 1) {
      e.preventDefault();
      indiceSelecionado++;
      renderizarTabela();
    } else if (e.key === "ArrowUp" && indiceSelecionado > 0) {
      e.preventDefault();
      indiceSelecionado--;
      renderizarTabela();
    } else if (e.key === "Enter") {
      e.preventDefault();
      confirmarProdutoBusca();
    } else if (e.key === "Escape") {
      e.preventDefault();
      fecharModalBusca();
    }
  });
}
