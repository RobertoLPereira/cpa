// ==========================================================================
// STATE.JS - Estado único da venda e funções auxiliares de formatação
// ==========================================================================

export const NOMES_FORMA_PGTO = {
  "01": "01 - DINHEIRO",
  "02": "02 - CHEQUE",
  "03": "03 - CARTÃO DE CRÉDITO",
  "04": "04 - CARTÃO DE DÉBITO",
  "05": "05 - CRÉDITO LOJA",
  "17": "17 - PIX",
  "99": "99 - OUTROS"
};

export const estadoPDV = {
  vendaIniciada: false,
  menuAuxiliarAberto: false,
  modalAtivo: null, // 'BUSCA' | 'PAGAMENTO' | 'REIMPRESSAO' | 'UNIVERSAL' | null
  carrinho: [],
  cpfCnpjCliente: null,
  nomeCliente: null,
  totalBruto: 0.00,
  totalLiquido: 0.00,
  totalDesconto: 0.00,
  percAcrescimo: 0.00,
  qtdeProxima: 1.00
};

export function resetarEstadoVenda() {
  estadoPDV.vendaIniciada = false;
  estadoPDV.carrinho = [];
  estadoPDV.cpfCnpjCliente = null;
  estadoPDV.nomeCliente = null;
  estadoPDV.totalBruto = 0.00;
  estadoPDV.totalLiquido = 0.00;
  estadoPDV.totalDesconto = 0.00;
  estadoPDV.percAcrescimo = 0.00;
  estadoPDV.qtdeProxima = 1.00;
}

export function formatarMoeda(valor) {
  return Number(valor || 0).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

export function getOperador() {
  return window.operadorAtivo || null;
}

export function getTerminal() {
  return window.terminalAtivo || { codigo: "CAIXA-01", serie: "1" };
}
