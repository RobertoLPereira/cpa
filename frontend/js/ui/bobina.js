// ==========================================================================
// UI/BOBINA.JS - Atualiza a bobina amarela, campos do produto e visores
// ==========================================================================
import { estadoPDV, formatarMoeda, NOMES_FORMA_PGTO } from "../state.js";

export function focarEAN() {
  const inp = document.getElementById("input-scanner");
  if (inp) {
    inp.disabled = false;
    inp.focus();
    inp.select();
  }
}

export function atualizarVisoresTotais() {
  estadoPDV.totalLiquido = Math.max(0, estadoPDV.totalBruto - estadoPDV.totalDesconto);
  document.getElementById("visor-desconto").value = formatarMoeda(estadoPDV.totalDesconto);
  document.getElementById("visor-total").value = formatarMoeda(estadoPDV.totalLiquido);
}

export function limparTelaVisual() {
  document.getElementById("txt-descricao").value = "CAIXA LIVRE";
  document.getElementById("input-quantidade").value = "1.00";
  document.getElementById("txt-unidade").value = "UN";
  document.getElementById("txt-preco-unit").value = "0,00";
  document.getElementById("txt-total-prod").value = "0,00";
  document.getElementById("lbl-doc-cliente").innerText = "Documento: Não informado";
  document.getElementById("lbl-perc-acrescimo").innerText = "";
  document.getElementById("btn-iniciar").disabled = false;
  document.getElementById("btn-acrescimo").disabled = false;

  document.getElementById("bobina-cupom").innerText =
    "*---------------- Venda Aberta ----------------*\n" +
    "ITEM  QTDE    UNIT    TOTAL DESCRIÇÃO\n" +
    "------------------------------------------------\n";

  atualizarVisoresTotais();
}

export function renderizarItensBobina(itensAprovados) {
  let texto =
    "*---------------- Venda Aberta ----------------*\n" +
    "ITEM  QTDE    UNIT    TOTAL DESCRIÇÃO\n" +
    "------------------------------------------------\n";

  itensAprovados.forEach((item, index) => {
    const num = String(index + 1).padStart(3, "0");
    const qtdStr = item.qCom.toFixed(2).padStart(7, " ");
    const unitStr = item.vUnCom.toFixed(2).padStart(8, " ");
    const totStr = item.vProd.toFixed(2).padStart(8, " ");
    const desc = item.nome_produto.substring(0, 22);

    texto += `${num}${qtdStr}${unitStr}${totStr} ${desc}\n`;

    if (index === itensAprovados.length - 1) {
      document.getElementById("txt-descricao").value = item.nome_produto;
      document.getElementById("txt-unidade").value = item.uCom || "UN";
      document.getElementById("txt-preco-unit").value = formatarMoeda(item.vUnCom);
      document.getElementById("txt-total-prod").value = formatarMoeda(item.vProd);
    }
  });

  document.getElementById("btn-acrescimo").disabled = itensAprovados.length > 0;

  const bobinaEl = document.getElementById("bobina-cupom");
  bobinaEl.innerText = texto;
  bobinaEl.scrollTop = bobinaEl.scrollHeight;
}

export function imprimirLeituraXNaBobina(r, operadorNome, serie) {
  let linhasPgtos = "";
  if (r.detalhe_pagamentos && r.detalhe_pagamentos.length > 0) {
    r.detalhe_pagamentos.forEach((p) => {
      const label = `${p.tpag} - ${p.descricao}`.padEnd(22, " ");
      const val = `R$ ${formatarMoeda(p.valor)}`.padStart(16, " ");
      linhasPgtos += `  ${label}${val}\n`;
    });
  } else {
    linhasPgtos = "  Nenhuma venda registrada hoje.\n";
  }

  const bobina = document.getElementById("bobina-cupom");
  bobina.innerText =
    "================================================\n" +
    "              RELATÓRIO LEITURA X               \n" +
    "================================================\n" +
    `Terminal : ${r.terminal_id} (Série ${serie})\n` +
    `Operador : ${operadorNome}\n` +
    `Emissão  : ${r.data_emissao}\n` +
    "------------------------------------------------\n" +
    "VENDAS POR FORMA DE PAGAMENTO:\n" +
    linhasPgtos +
    "------------------------------------------------\n" +
    `TOTAL VENDAS DO DIA     : R$ ${formatarMoeda(r.total_vendas)}\n` +
    "------------------------------------------------\n" +
    "MOVIMENTAÇÃO DE GAVETA (DINHEIRO):\n" +
    `(+) Suprimentos (${r.qtd_suprimentos})     : R$ ${formatarMoeda(r.total_suprimentos)}\n` +
    `(+) Vendas em Dinheiro  : R$ ${formatarMoeda(r.total_dinheiro)}\n` +
    `(-) Sangrias    (${r.qtd_sangrias})     : R$ ${formatarMoeda(r.total_sangrias)}\n` +
    "------------------------------------------------\n" +
    `(=) SALDO EM GAVETA     : R$ ${formatarMoeda(r.saldo_gaveta)}\n` +
    "================================================\n";
}

export function imprimirReimpressaoNaBobina({ nota, itens, pagamentos }) {
  let texto =
    "================================================\n" +
    "        REIMPRESSÃO - VIA CONSUMIDOR            \n" +
    "================================================\n" +
    `NFC-e Nº: ${String(nota.nnf).padStart(6, "0")}  Série: ${nota.serie}  Mod: ${nota.modelo}\n` +
    `Emissão : ${(nota.dhemi || "").replace("T", " ").substring(0, 19)}\n` +
    `Status  : ${nota.status_sefaz} ${nota.nprot ? "(Prot: " + nota.nprot + ")" : ""}\n` +
    `Cliente : ${nota.cliente_nome} ${nota.cliente_doc ? "(" + nota.cliente_doc + ")" : ""}\n` +
    "------------------------------------------------\n" +
    "ITEM  QTDE    UNIT    TOTAL DESCRIÇÃO\n" +
    "------------------------------------------------\n";

  itens.forEach((it) => {
    const num = String(it.nitem).padStart(3, "0");
    const qtd = it.qcom.toFixed(2).padStart(7, " ");
    const unit = it.vuncom.toFixed(2).padStart(8, " ");
    const tot = it.vprod.toFixed(2).padStart(8, " ");
    texto += `${num}${qtd}${unit}${tot} ${(it.xprod || "").substring(0, 22)}\n`;
  });

  texto +=
    "------------------------------------------------\n" +
    `SUBTOTAL R$ : ${formatarMoeda(nota.vprod).padStart(33, " ")}\n` +
    `DESCONTO R$ : ${formatarMoeda(nota.vdesc).padStart(33, " ")}\n` +
    `TOTAL R$    : ${formatarMoeda(nota.vnf).padStart(33, " ")}\n` +
    "------------------------------------------------\n" +
    "PAGAMENTOS:\n";

  pagamentos.forEach((pg) => {
    const nomePg = (NOMES_FORMA_PGTO[pg.tpag] || pg.tpag).padEnd(25, " ");
    const valPg = `R$ ${formatarMoeda(pg.vpag)}`.padStart(20, " ");
    texto += `  ${nomePg}${valPg}\n`;
  });

  texto +=
    "------------------------------------------------\n" +
    `Chave: ${nota.chnfe || "EM CONTINGÊNCIA"}\n` +
    "================================================\n";

  const bobina = document.getElementById("bobina-cupom");
  bobina.innerText = texto;
  bobina.scrollTop = 0;
}
