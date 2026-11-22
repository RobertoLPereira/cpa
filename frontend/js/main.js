// ==========================================================================
// MAIN.JS - Orquestrador do PDV: inicializa eventos, relógio e teclas F1..F12
// ==========================================================================
import { estadoPDV, getOperador } from "./state.js";
import { focarEAN } from "./ui/bobina.js";
import { inicializarModalUniversal, fecharModalUniversal } from "./ui/modal-universal.js";
import { inicializarModalBusca, abrirModalBusca, fecharModalBusca, consultarProdutos, selecionarLinhaBusca, confirmarProdutoBusca } from "./ui/modal-busca.js";
import { inicializarModalPagamento, abrirModalPagamento, fecharModalPagamento, adicionarPagamento, removerPagamento, confirmarEncerramentoVenda } from "./ui/modal-pagamento.js";
import { inicializarModalReimpressao, abrirModalReimpressao, fecharModalReimpressao, carregarNotas, selecionarLinhaReimp, executarReimpressao, transmitirPendente } from "./ui/modal-reimp.js";
import { iniciarVenda, registrarItem, alterarQuantidade, aplicarAcrescimo, aplicarDesconto, informarCpfNota, cancelarItem, cancelarVenda, limparVendaCompleta } from "./operacoes/venda.js";
import { toggleMenuAuxiliar, executarSuprimento, executarSangria, emitirLeituraX } from "./operacoes/gaveta.js";
import "./retaguarda/produtos.js";
import "./retaguarda/importa-nfe.js";
import "./retaguarda/usuarios.js";

// Expõe ações para os botões onclick do HTML
window.pdvUI = {
  iniciarVenda,
  focarEAN,
  alterarQuantidade,
  aplicarAcrescimo,
  aplicarDesconto,
  informarCpfNota,
  cancelarItem,
  cancelarVenda,
  toggleMenuAuxiliar,
  executarSuprimento,
  executarSangria,
  emitirLeituraX,
  abrirBusca: () => abrirModalBusca((codigo) => registrarItem(codigo)),
  fecharBusca: fecharModalBusca,
  consultarProdutos,
  selecionarLinhaBusca,
  confirmarProdutoBusca,
  abrirPagamento: () => abrirModalPagamento(() => {
    limparVendaCompleta();
    document.getElementById("lbl-status-venda").innerText = "Venda Finalizada";
    focarEAN();
  }),
  fecharPagamento: fecharModalPagamento,
  adicionarPagamento,
  removerPagamento,
  confirmarEncerramentoVenda,
  abrirReimpressao: abrirModalReimpressao,
  fecharReimpressao: fecharModalReimpressao,
  carregarNotas,
  selecionarLinhaReimp,
  executarReimpressao,
  transmitirPendente,
  fecharUniversal: fecharModalUniversal,
  confirmarUniversal: () => fecharModalUniversal(document.getElementById("modal-univ-campo").value),
  abrirCalculadora: () => { toggleMenuAuxiliar(false); alert("Data/Hora: " + new Date().toLocaleString("pt-BR")); },
  abrirCaixa: () => { toggleMenuAuxiliar(false); alert("Caixa aberto para movimentação."); }
};

// Compatibilidade com auth_retaguarda.js ao fazer logoff
window.limparExibicaoTelas = limparVendaCompleta;

// Relógio em tempo real
setInterval(() => {
  const agora = new Date();
  document.getElementById("lbl-data").innerText = "Data: " + agora.toLocaleDateString("pt-BR");
  document.getElementById("lbl-hora").innerText = "Hora: " + agora.toLocaleTimeString("pt-BR");
}, 1000);

// Inicializa todos os modais e o leitor de código de barras
document.addEventListener("DOMContentLoaded", () => {
  inicializarModalUniversal();
  inicializarModalBusca();
  inicializarModalPagamento();
  inicializarModalReimpressao();

  document.getElementById("input-scanner").addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      registrarItem();
    }
  });
});

// Atalhos globais do teclado (F1..F12)
window.addEventListener("keydown", (e) => {
  const operador = getOperador();
  if (!operador) return;

  if (e.key === "F10") {
    e.preventDefault();
    if (typeof window.fazerLogoff === "function") window.fazerLogoff();
    return;
  }

  // Se algum modal estiver aberto, deixa o próprio modal tratar as teclas
  if (estadoPDV.modalAtivo) return;

  const ehCaixa = (operador.grupo_geral || "").trim().toUpperCase() === "CAIXA";
  if (!ehCaixa) return;

  if (e.key === "F7") { e.preventDefault(); toggleMenuAuxiliar(); return; }

  if (estadoPDV.menuAuxiliarAberto) {
    if (e.key === "F1") { e.preventDefault(); executarSuprimento(); }
    if (e.key === "F2") { e.preventDefault(); executarSangria(); }
    if (e.key === "F3") { e.preventDefault(); abrirModalReimpressao(); }
    if (e.key === "F4") { e.preventDefault(); window.pdvUI.abrirCalculadora(); }
    if (e.key === "F5") { e.preventDefault(); window.pdvUI.abrirCaixa(); }
    if (e.key === "F6") { e.preventDefault(); emitirLeituraX(); }
    return;
  }

  if (e.key === "F1")  { e.preventDefault(); window.pdvUI.abrirBusca(); }
  if (e.key === "F2")  { e.preventDefault(); alterarQuantidade(); }
  if (e.key === "F4")  { e.preventDefault(); informarCpfNota(); }
  if (e.key === "F5")  { e.preventDefault(); cancelarItem(); }
  if (e.key === "F6")  { e.preventDefault(); cancelarVenda(); }
  if (e.key === "F8")  { e.preventDefault(); window.pdvUI.abrirPagamento(); }
  if (e.key === "F9")  { e.preventDefault(); focarEAN(); }
  if (e.key === "F11") { e.preventDefault(); aplicarDesconto(); }
  if (e.key === "F12") { e.preventDefault(); aplicarAcrescimo(); }
});
