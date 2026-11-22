// ==========================================================================
// OPERACOES/VENDA.JS - Regras de negócio da venda em andamento no PDV
// ==========================================================================
import { estadoPDV, resetarEstadoVenda, formatarMoeda, getOperador } from "../state.js";
import { pdvAPI } from "../api.js";
import { pedirDadoModal } from "../ui/modal-universal.js";
import { focarEAN, atualizarVisoresTotais, limparTelaVisual, renderizarItensBobina } from "../ui/bobina.js";
import { verificarPermissaoGerente } from "./gaveta.js";

export function limparVendaCompleta() {
  resetarEstadoVenda();
  limparTelaVisual();
}

export function iniciarVenda() {
  if (estadoPDV.vendaIniciada && estadoPDV.carrinho.length > 0) {
    return alert("Para iniciar uma nova venda, finalize ou cancele a venda em aberto!");
  }
  limparVendaCompleta();
  estadoPDV.vendaIniciada = true;

  const lblStatus = document.getElementById("lbl-status-venda");
  lblStatus.innerText = "Venda Aberta";
  lblStatus.style.color = "#000099";
  document.getElementById("btn-iniciar").disabled = true;
  document.getElementById("btn-acrescimo").disabled = false;
  focarEAN();
}

export async function registrarItem(codigoInformado = null) {
  if (!estadoPDV.vendaIniciada) iniciarVenda();
  const inp = document.getElementById("input-scanner");
  const codigo = (codigoInformado ?? inp.value).trim();
  if (!codigo) return;

  estadoPDV.carrinho.push({
    codigo,
    quantidade: estadoPDV.qtdeProxima,
    preco_contingencia: 0.00,
    acrescimo_perc: estadoPDV.percAcrescimo
  });

  inp.value = "";
  estadoPDV.qtdeProxima = 1.00;
  document.getElementById("input-quantidade").value = "1.00";
  focarEAN();

  await sincronizarCupom();
}

export async function sincronizarCupom() {
  if (estadoPDV.carrinho.length === 0) {
    limparVendaCompleta();
    return;
  }

  try {
    const dados = await pdvAPI.calcularCupom(estadoPDV.carrinho);
    if (dados.itens_bloqueados && dados.itens_bloqueados.length > 0) {
      const bloq = dados.itens_bloqueados[0];
      alert(`ALERTA: '${bloq.nome_produto.toUpperCase()}' está sem preço ou não cadastrado!`);
      estadoPDV.carrinho.pop();
      return;
    }

    renderizarItensBobina(dados.itens_aprovados);
    estadoPDV.totalBruto = dados.resumo.vNF;
    atualizarVisoresTotais();
  } catch (erro) {
    alert("Falha ao comunicar com o Motor Fiscal: " + erro.message);
    estadoPDV.carrinho.pop();
  }
}

export async function alterarQuantidade() {
  if (!estadoPDV.vendaIniciada) iniciarVenda();
  if (getOperador()?.alterar_qtde === "N") {
    const aut = await verificarPermissaoGerente();
    if (!aut) return;
  }

  const res = await pedirDadoModal({
    titulo: "ALTERAR QUANTIDADE [F2]",
    label: "Quantidade do próximo item:",
    valorInicial: estadoPDV.qtdeProxima.toLocaleString("pt-BR", { minimumFractionDigits: 3 }),
    tipo: "qtde"
  });
  if (res === null) return;

  const parsed = parseFloat(res.replace(/\./g, "").replace(",", "."));
  if (isNaN(parsed) || parsed <= 0) return alert("Quantidade inválida!");
  estadoPDV.qtdeProxima = parsed;
  document.getElementById("input-quantidade").value = parsed.toFixed(2);
}

export async function aplicarAcrescimo() {
  if (!estadoPDV.vendaIniciada) iniciarVenda();
  if (estadoPDV.totalBruto > 0) return alert("O % de Acréscimo só pode ser informado antes de lançar itens!");

  const aut = await verificarPermissaoGerente();
  if (!aut) return;

  const res = await pedirDadoModal({
    titulo: "ACRÉSCIMO PERCENTUAL [F12]",
    label: "Percentual de acréscimo (%):",
    valorInicial: formatarMoeda(estadoPDV.percAcrescimo),
    tipo: "percentual"
  });
  if (res === null) return;

  estadoPDV.percAcrescimo = parseFloat(res.replace(/\./g, "").replace(",", ".")) || 0;
  document.getElementById("lbl-perc-acrescimo").innerText = estadoPDV.percAcrescimo > 0 ? `${estadoPDV.percAcrescimo}%` : "";
}

export async function aplicarDesconto() {
  if (!estadoPDV.vendaIniciada || estadoPDV.totalBruto <= 0) return alert("Não há itens para aplicar desconto.");

  const aut = await verificarPermissaoGerente();
  if (!aut) return;

  const res = await pedirDadoModal({
    titulo: "DESCONTO NO CUPOM [F11]",
    label: "Valor do desconto (R$):",
    valorInicial: formatarMoeda(estadoPDV.totalDesconto),
    tipo: "moeda",
    dica: `Máximo permitido (50%): R$ ${formatarMoeda(estadoPDV.totalBruto * 0.5)}`
  });
  if (res === null) return;

  const desc = parseFloat(res.replace(/\./g, "").replace(",", ".")) || 0;
  if (desc > estadoPDV.totalBruto * 0.5) return alert("Desconto não pode ultrapassar 50% do total!");
  estadoPDV.totalDesconto = desc;
  atualizarVisoresTotais();
}

export async function informarCpfNota() {
  const doc = await pedirDadoModal({
    titulo: "IDENTIFICAÇÃO DO CONSUMIDOR [F4]",
    label: "CPF ou CNPJ do cliente:",
    valorInicial: estadoPDV.cpfCnpjCliente || "",
    tipo: "cpfcnpj",
    dica: "Deixe em branco e pressione ENTER para remover."
  });
  if (doc === null) return;

  const docLimpo = doc.replace(/\D/g, "");
  if (docLimpo === "") {
    estadoPDV.cpfCnpjCliente = null;
    estadoPDV.nomeCliente = null;
    document.getElementById("lbl-doc-cliente").innerText = "Documento: Não informado";
    return;
  }
  if (docLimpo.length !== 11 && docLimpo.length !== 14) {
    return alert("Documento inválido! Informe 11 dígitos (CPF) ou 14 dígitos (CNPJ).");
  }

  estadoPDV.cpfCnpjCliente = docLimpo;
  if (docLimpo.length === 14) {
    const razao = await pedirDadoModal({
      titulo: "RAZÃO SOCIAL DO DESTINATÁRIO",
      label: "Nome / Razão Social:",
      valorInicial: estadoPDV.nomeCliente || "",
      tipo: "texto"
    });
    estadoPDV.nomeCliente = (razao || "CONSUMIDOR").trim().toUpperCase();
  } else {
    estadoPDV.nomeCliente = "CONSUMIDOR";
  }
  document.getElementById("lbl-doc-cliente").innerText = `Documento: ${doc} - ${estadoPDV.nomeCliente}`;
}

export async function cancelarItem() {
  if (estadoPDV.carrinho.length === 0) return alert("Não existe nenhum item digitado para esta venda!");
  const numStr = await pedirDadoModal({
    titulo: "CANCELAR ITEM [F5]",
    label: "Digite o número do ITEM (ex: 1 ou 001):",
    tipo: "inteiro",
    dica: `Itens lançados: 1 até ${estadoPDV.carrinho.length}`
  });
  if (!numStr) return;

  const idx = parseInt(numStr, 10) - 1;
  if (isNaN(idx) || idx < 0 || idx >= estadoPDV.carrinho.length) return alert("Número de item inválido.");
  if (confirm(`Confirma o Cancelamento do Item [ ${String(idx + 1).padStart(3, "0")} ] ?`)) {
    estadoPDV.carrinho.splice(idx, 1);
    await sincronizarCupom();
  }
}

export function cancelarVenda() {
  if (estadoPDV.carrinho.length === 0 && !estadoPDV.vendaIniciada) return;
  if (confirm("Confirma o Cancelamento da Venda?")) {
    limparVendaCompleta();
    const lblStatus = document.getElementById("lbl-status-venda");
    lblStatus.innerText = "Venda Cancelada";
    lblStatus.style.color = "#cc0000";
    document.getElementById("bobina-cupom").innerText += "\n************************************************\nVENDA CANCELADA\n";
  }
}
