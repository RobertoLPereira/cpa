// ==========================================================================
// UI/MODAL-PAGAMENTO.JS - Tela de fechamento e cálculo de troco [F8]
// ==========================================================================
import { estadoPDV, formatarMoeda, NOMES_FORMA_PGTO, getOperador, getTerminal } from "../state.js";
import { pdvAPI } from "../api.js";
import { focarEAN } from "./bobina.js";

let pagamentosLancados = [];
let trocoAtual = 0.00;
let onVendaConcluidaCallback = null;

export function abrirModalPagamento(onConcluida) {
  if (estadoPDV.carrinho.length === 0) {
    return alert("Não existe nenhum item digitado para esta venda! Escolha CANCELA VDA.");
  }
  onVendaConcluidaCallback = onConcluida;
  estadoPDV.modalAtivo = "PAGAMENTO";
  pagamentosLancados = [];
  trocoAtual = 0.00;

  document.getElementById("modal-efetua-pagamento").classList.remove("hidden");
  document.getElementById("select-forma-pgto").value = "01";
  atualizarTelaPagamento();

  const inpVal = document.getElementById("input-valor-pgto");
  inpVal.focus();
  inpVal.select();
}

export function fecharModalPagamento() {
  estadoPDV.modalAtivo = null;
  document.getElementById("modal-efetua-pagamento").classList.add("hidden");
  focarEAN();
}

function atualizarTelaPagamento() {
  const totalPago = pagamentosLancados.reduce((acc, p) => acc + p.vpag, 0);
  const restante = Math.max(0, Number((estadoPDV.totalLiquido - totalPago).toFixed(2)));
  trocoAtual = totalPago > estadoPDV.totalLiquido ? Number((totalPago - estadoPDV.totalLiquido).toFixed(2)) : 0.00;

  document.getElementById("pgto-total-cupom").innerText = formatarMoeda(estadoPDV.totalLiquido);
  document.getElementById("pgto-total-pago").innerText = formatarMoeda(totalPago);
  document.getElementById("pgto-restante").innerText = formatarMoeda(restante);
  document.getElementById("pgto-troco").innerText = formatarMoeda(trocoAtual);

  const inpVal = document.getElementById("input-valor-pgto");
  inpVal.value = formatarMoeda(restante);

  document.getElementById("tbody-pagamentos-lancados").innerHTML = pagamentosLancados.map((p, idx) => `
    <tr>
      <td>${NOMES_FORMA_PGTO[p.tpag] || p.tpag}</td>
      <td style="text-align:right;">${formatarMoeda(p.vpag)}</td>
      <td style="text-align:center;">
        <button onclick="window.pdvUI.removerPagamento(${idx})" style="color:#cc0000; font-weight:bold; cursor:pointer;">X</button>
      </td>
    </tr>
  `).join("");

  const btnConfirmar = document.getElementById("btn-confirmar-pgto-final");
  btnConfirmar.disabled = restante > 0.009;
  if (!btnConfirmar.disabled) {
    btnConfirmar.focus();
  } else {
    inpVal.focus();
    inpVal.select();
  }
}

export function adicionarPagamento() {
  const tpag = document.getElementById("select-forma-pgto").value;
  const valor = parseFloat(document.getElementById("input-valor-pgto").value.replace(/\./g, "").replace(",", "."));
  if (isNaN(valor) || valor <= 0) return alert("Informe um valor válido maior que zero!");

  const totalPago = pagamentosLancados.reduce((acc, p) => acc + p.vpag, 0);
  const restante = Number((estadoPDV.totalLiquido - totalPago).toFixed(2));
  if (tpag !== "01" && valor > restante + 0.009) {
    return alert("Para Cartão/PIX o valor não pode ser maior que o saldo restante!");
  }

  pagamentosLancados.push({ tpag, vpag: Number(valor.toFixed(2)) });
  atualizarTelaPagamento();
}

export function removerPagamento(idx) {
  pagamentosLancados.splice(idx, 1);
  atualizarTelaPagamento();
}

export async function confirmarEncerramentoVenda() {
  const totalPago = pagamentosLancados.reduce((acc, p) => acc + p.vpag, 0);
  if (totalPago + 0.009 < estadoPDV.totalLiquido) return alert("O valor pago ainda é menor que o total da venda!");

  const btnConfirmar = document.getElementById("btn-confirmar-pgto-final");
  btnConfirmar.disabled = true;
  btnConfirmar.innerText = "TRANSMITINDO NFC-e...";

  const operador = getOperador();
  const terminal = getTerminal();
  const modeloNota = (estadoPDV.cpfCnpjCliente && estadoPDV.cpfCnpjCliente.length === 14)
    ? "55"
    : (operador?.modelonfe || "65");

  const payload = {
    terminal_id: terminal.codigo,
    modelo: modeloNota,
    serie: terminal.serie,
    cpf_cnpj_destinatario: estadoPDV.cpfCnpjCliente,
    nome_destinatario: estadoPDV.nomeCliente,
    desconto_total: estadoPDV.totalDesconto,
    itens_carrinho: estadoPDV.carrinho,
    pagamentos: pagamentosLancados.map((p, idx) => ({
      tpag: p.tpag,
      vpag: p.vpag,
      vtroco: idx === pagamentosLancados.length - 1 ? trocoAtual : 0.00
    }))
  };

  try {
    const resultado = await pdvAPI.finalizarVenda(payload);
    if (resultado.xml) {
      const blob = new Blob([resultado.xml], { type: "application/xml" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = resultado.chave_acesso ? `NFe${resultado.chave_acesso}.xml` : `nota_${resultado.numero_nota}.xml`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }

    const msgTroco = trocoAtual > 0 ? `\nTROCO: R$ ${formatarMoeda(trocoAtual)}` : "";
    alert(`[Venda Finalizada!]\nTerminal: ${terminal.codigo}\nNota Nº: ${resultado.numero_nota}\nStatus SEFAZ: ${resultado.status_sefaz}${msgTroco}`);

    fecharModalPagamento();
    if (onVendaConcluidaCallback) onVendaConcluidaCallback();
  } catch (e) {
    alert(`Falha ao finalizar venda: ${e.message}`);
  } finally {
    btnConfirmar.innerText = "[F8] CONFIRMAR E EMITIR NFC-e";
    atualizarTelaPagamento();
  }
}

export function inicializarModalPagamento() {
  const inpVal = document.getElementById("input-valor-pgto");
  const selForma = document.getElementById("select-forma-pgto");

  inpVal.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const totalPago = pagamentosLancados.reduce((acc, p) => acc + p.vpag, 0);
      if (totalPago + 0.009 >= estadoPDV.totalLiquido && pagamentosLancados.length > 0) {
        confirmarEncerramentoVenda();
      } else {
        adicionarPagamento();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      fecharModalPagamento();
    }
  });

  selForma.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); inpVal.focus(); inpVal.select(); }
    if (e.key === "Escape") { e.preventDefault(); fecharModalPagamento(); }
  });
}
