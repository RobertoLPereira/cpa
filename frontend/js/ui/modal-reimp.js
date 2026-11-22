// ==========================================================================
// UI/MODAL-REIMP.JS - Reimpressão e envio de pendentes [F3] (PedidosPendentes)
// ==========================================================================
import { estadoPDV, formatarMoeda, getTerminal } from "../state.js";
import { pdvAPI } from "../api.js";
import { focarEAN, imprimirReimpressaoNaBobina } from "./bobina.js";

let notasEncontradas = [];
let indiceNota = -1;

export function abrirModalReimpressao() {
  estadoPDV.modalAtivo = "REIMPRESSAO";
  notasEncontradas = [];
  indiceNota = -1;
  document.getElementById("modal-reimpressao").classList.remove("hidden");
  carregarNotas("TODAS");
}

export function fecharModalReimpressao() {
  estadoPDV.modalAtivo = null;
  document.getElementById("modal-reimpressao").classList.add("hidden");
  focarEAN();
}

export async function carregarNotas(filtro = "TODAS") {
  const tbody = document.getElementById("tbody-notas-reimpressao");
  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:18px;">Carregando notas...</td></tr>`;

  try {
    const data = await pdvAPI.listarNotasReimpressao(filtro, getTerminal().serie);
    notasEncontradas = data.notas || [];
    indiceNota = notasEncontradas.length > 0 ? 0 : -1;
    document.getElementById("lbl-qtd-notas-reimp").innerText = `${notasEncontradas.length} nota(s) encontrada(s)`;
    renderizarTabela();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:18px; color:#cc0000;">${e.message}</td></tr>`;
  }
}

function renderizarTabela() {
  const tbody = document.getElementById("tbody-notas-reimpressao");
  const btnTransm = document.getElementById("btn-transmitir-pendente");

  if (notasEncontradas.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px; color:#666;">Nenhuma nota encontrada.</td></tr>`;
    if (btnTransm) btnTransm.disabled = true;
    return;
  }

  tbody.innerHTML = notasEncontradas.map((n, idx) => {
    const sel = idx === indiceNota ? "selecionado" : "";
    const corStatus = n.status_sefaz === "AUTORIZADA" ? "#16a34a" : "#cc0000";
    return `
      <tr class="${sel}"
          onclick="window.pdvUI.selecionarLinhaReimp(${idx})"
          ondblclick="window.pdvUI.executarReimpressao(false, false)">
        <td>${String(n.nnf).padStart(6, "0")}</td>
        <td>${n.serie}</td>
        <td>${n.modelo}</td>
        <td>${(n.dhemi || "").replace("T", " ").substring(0, 16)}</td>
        <td>${n.cliente_nome}</td>
        <td style="text-align:right;">${formatarMoeda(n.vnf)}</td>
        <td style="text-align:center; color:${sel ? "#fff" : corStatus};">${n.status_sefaz}</td>
      </tr>
    `;
  }).join("");

  const notaAtual = notasEncontradas[indiceNota];
  if (btnTransm) btnTransm.disabled = !notaAtual || notaAtual.status_sefaz === "AUTORIZADA";

  const linhaAtiva = tbody.querySelector("tr.selecionado");
  if (linhaAtiva) linhaAtiva.scrollIntoView({ block: "nearest" });
}

export function selecionarLinhaReimp(idx) {
  indiceNota = idx;
  renderizarTabela();
}

export async function executarReimpressao(apenasBaixarXml = false, imprimirDireto = false) {
  if (indiceNota < 0 || !notasEncontradas[indiceNota]) return;
  const notaResumo = notasEncontradas[indiceNota];

  try {
    const dados = await pdvAPI.obterDetalhesReimpressao(notaResumo.id);
    if (apenasBaixarXml) {
      if (!dados.nota.xml_completo) return alert("Esta nota ainda não possui XML gravado no banco.");
      const blob = new Blob([dados.nota.xml_completo], { type: "application/xml" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = dados.nota.chnfe ? `NFe${dados.nota.chnfe}.xml` : `nota_${dados.nota.nnf}.xml`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      return;
    }

    fecharModalReimpressao();
    imprimirReimpressaoNaBobina(dados);
    if (imprimirDireto) setTimeout(() => window.print(), 150);
  } catch (e) {
    alert("Falha na reimpressão: " + e.message);
  }
}

export async function transmitirPendente() {
  if (indiceNota < 0 || !notasEncontradas[indiceNota]) return;
  const nota = notasEncontradas[indiceNota];
  if (!confirm(`Deseja transmitir a NFC-e Nº ${nota.nnf} (Série ${nota.serie}) para a SEFAZ?`)) return;

  const btn = document.getElementById("btn-transmitir-pendente");
  btn.disabled = true;
  btn.innerText = "Transmitindo...";

  try {
    const res = await pdvAPI.transmitirNotaPendente(nota.id);
    alert(`${res.mensagem}\nProtocolo: ${res.nprot}`);
    await carregarNotas("TODAS");
  } catch (e) {
    alert("Erro na transmissão: " + e.message);
  } finally {
    btn.innerText = "Transmitir Pendente";
  }
}

export function inicializarModalReimpressao() {
  window.addEventListener("keydown", (e) => {
    if (estadoPDV.modalAtivo !== "REIMPRESSAO") return;
    if (e.key === "ArrowDown" && indiceNota < notasEncontradas.length - 1) {
      e.preventDefault(); indiceNota++; renderizarTabela();
    } else if (e.key === "ArrowUp" && indiceNota > 0) {
      e.preventDefault(); indiceNota--; renderizarTabela();
    } else if (e.key === "Enter") {
      e.preventDefault(); executarReimpressao(false, false);
    } else if (e.key === "Escape") {
      e.preventDefault(); fecharModalReimpressao();
    }
  }, true);
}
