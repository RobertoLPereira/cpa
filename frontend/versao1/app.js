// ============================================================================
// pdv_nfce.js - PARTE 1 DE 2 (Estado, Relógio, Bipagem e Bobina)
// ============================================================================

let vendaIniciada = false;
let menuAuxiliarAberto = false;
let carrinhoLocal = [];
let cpfCnpjClienteAtual = null;
let nomeClienteAtual = null;
let totalBrutoCupom = 0.00;
let totalCupomAtual = 0.00;
let totalDesconto = 0.00;
let percAcrescimo = 0.00;
let qtdeAtual = 1.00;

// Relógio em tempo real (Data e Hora do cabeçalho)
setInterval(() => {
    const agora = new Date();
    const elData = document.getElementById("lbl-data");
    const elHora = document.getElementById("lbl-hora");
    if (elData) elData.innerText = "Data: " + agora.toLocaleDateString("pt-BR");
    if (elHora) elHora.innerText = "Hora: " + agora.toLocaleTimeString("pt-BR");
}, 1000);

function formatarMoeda(valor) {
    return Number(valor || 0).toLocaleString("pt-BR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function iniciarVenda() {
    if (vendaIniciada && carrinhoLocal.length > 0) {
        alert("Para iniciar uma nova venda, finalize ou cancele a venda em aberto!");
        return;
    }
    limparExibicaoTelas();
    vendaIniciada = true;
    document.getElementById("lbl-status-venda").innerText = "Venda Aberta";
    document.getElementById("lbl-status-venda").style.color = "#000099";
    document.getElementById("btn-iniciar").disabled = true;
    document.getElementById("btn-acrescimo").disabled = false;
    focarEAN();
}

function limparExibicaoTelas() {
    vendaIniciada = false;
    carrinhoLocal = [];
    cpfCnpjClienteAtual = null;
    nomeClienteAtual = null;
    totalBrutoCupom = 0.00;
    totalCupomAtual = 0.00;
    totalDesconto = 0.00;
    percAcrescimo = 0.00;
    qtdeAtual = 1.00;

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

function atualizarVisoresTotais() {
    totalCupomAtual = Math.max(0, totalBrutoCupom - totalDesconto);
    document.getElementById("visor-desconto").value = formatarMoeda(totalDesconto);
    document.getElementById("visor-total").value = formatarMoeda(totalCupomAtual);
}

function focarEAN() {
    const inp = document.getElementById("input-scanner");
    if (inp) {
        inp.disabled = false;
        inp.focus();
        inp.select();
    }
}

function alterarQuantidade() {
    if (!vendaIniciada) iniciarVenda();
    if (typeof operadorAtivo !== "undefined" && operadorAtivo && operadorAtivo.alterar_qtde === "N") {
        return alert("Seu usuário não possui permissão para alterar quantidade.");
    }
    const novaQtde = prompt("Informe a Quantidade:", qtdeAtual.toFixed(2));
    if (novaQtde === null) return;
    const parsed = parseFloat(novaQtde.replace(",", "."));
    if (isNaN(parsed) || parsed <= 0) return alert("Quantidade inválida!");
    qtdeAtual = parsed;
    document.getElementById("input-quantidade").value = qtdeAtual.toFixed(2);
    focarEAN();
}

function aplicarAcrescimo() {
    if (!vendaIniciada) iniciarVenda();
    if (totalBrutoCupom > 0) {
        return alert("O % de Acréscimo só pode ser informado no início da venda (antes dos itens)!");
    }
    const val = prompt("Informe o percentual de Acréscimo (%):", percAcrescimo);
    if (val === null) return;
    const perc = parseFloat(val.replace(",", "."));
    if (isNaN(perc) || perc < 0) return alert("Percentual inválido!");
    percAcrescimo = perc;
    document.getElementById("lbl-perc-acrescimo").innerText = `${percAcrescimo}%`;
    focarEAN();
}

function aplicarDesconto() {
    if (!vendaIniciada || totalBrutoCupom <= 0) {
        return alert("Não há itens lançados para aplicar desconto.");
    }
    const val = prompt("Informe o valor do Desconto (R$):", totalDesconto.toFixed(2));
    if (val === null) return;
    const desc = parseFloat(val.replace(",", "."));
    if (isNaN(desc) || desc < 0) return alert("Valor de desconto não pode ser negativo!");
    if (desc > totalBrutoCupom * 0.5) {
        return alert("Valor Desconto não pode ser maior que 50% do Total do Cupom!");
    }
    totalDesconto = desc;
    atualizarVisoresTotais();
    focarEAN();
}

async function registrarItemCarrinho() {
    if (!vendaIniciada) iniciarVenda();
    const inp = document.getElementById("input-scanner");
    const codigoBipado = inp.value.trim();
    if (!codigoBipado) return;

    carrinhoLocal.push({
        codigo: codigoBipado,
        quantidade: qtdeAtual,
        preco_contingencia: 0.00,
        acrescimo_perc: percAcrescimo
    });

    inp.value = "";
    qtdeAtual = 1.00;
    document.getElementById("input-quantidade").value = "1.00";
    focarEAN();

    await atualizarCupomNaTela();
}

async function atualizarCupomNaTela() {
    if (carrinhoLocal.length === 0) {
        limparExibicaoTelas();
        return;
    }

    try {
        const resposta = await fetch(`${API_URL}/caixa/calcular-cupom`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ itens_carrinho: carrinhoLocal })
        });
        if (!resposta.ok) throw new Error("Erro na comunicação com a API.");
        const dados = await resposta.json();

        if (dados.itens_bloqueados && dados.itens_bloqueados.length > 0) {
            const bloq = dados.itens_bloqueados[0];
            alert(`ALERTA: '${bloq.nome_produto.toUpperCase()}' está sem preço ou não cadastrado!`);
            carrinhoLocal.pop();
            return;
        }

        let textoBobina =
            "*---------------- Venda Aberta ----------------*\n" +
            "ITEM  QTDE    UNIT    TOTAL DESCRIÇÃO\n" +
            "------------------------------------------------\n";

        dados.itens_aprovados.forEach((item, index) => {
            const num = String(index + 1).padStart(3, "0");
            const qtdStr = item.qCom.toFixed(2).padStart(7, " ");
            const unitStr = item.vUnCom.toFixed(2).padStart(8, " ");
            const totStr = item.vProd.toFixed(2).padStart(8, " ");
            const desc = item.nome_produto.substring(0, 22);

            textoBobina += `${num}${qtdStr}${unitStr}${totStr} ${desc}\n`;

            if (index === dados.itens_aprovados.length - 1) {
                document.getElementById("txt-descricao").value = item.nome_produto;
                document.getElementById("txt-unidade").value = item.uCom || "UN";
                document.getElementById("txt-preco-unit").value = formatarMoeda(item.vUnCom);
                document.getElementById("txt-total-prod").value = formatarMoeda(item.vProd);
            }
        });

        if (dados.itens_aprovados.length > 0) {
            document.getElementById("btn-acrescimo").disabled = true;
        }

        const bobinaEl = document.getElementById("bobina-cupom");
        bobinaEl.innerText = textoBobina;
        bobinaEl.scrollTop = bobinaEl.scrollHeight;

        totalBrutoCupom = dados.resumo.vNF;
        atualizarVisoresTotais();
    } catch (erro) {
        alert("Falha ao comunicar com o Motor Fiscal.");
        carrinhoLocal.pop();
    }
}
// ============================================================================
// pdv_nfce.js - PARTE 2 DE 2 (Finalização, Cancelamentos, Menu F7 e Teclado)
// ============================================================================

function informarCpfNota() {
    const doc = prompt("Informe o CPF ou CNPJ do consumidor (apenas números):", cpfCnpjClienteAtual || "");
    if (doc === null) return;

    const docLimpo = doc.replace(/\D/g, "");
    if (docLimpo === "") {
        cpfCnpjClienteAtual = null;
        nomeClienteAtual = null;
        document.getElementById("lbl-doc-cliente").innerText = "Documento: Não informado";
        return;
    }

    if (docLimpo.length !== 11 && docLimpo.length !== 14) {
        return alert("Documento inválido! Digite 11 dígitos para CPF ou 14 dígitos para CNPJ.");
    }

    cpfCnpjClienteAtual = docLimpo;
    nomeClienteAtual = docLimpo.length === 14
        ? (prompt("Informe a Razão Social / Nome do cliente:", nomeClienteAtual || "") || "CONSUMIDOR")
        : "CONSUMIDOR";

    document.getElementById("lbl-doc-cliente").innerText = `Documento: ${cpfCnpjClienteAtual} - ${nomeClienteAtual}`;
    focarEAN();
}

function cancelarItemEspecifico() {
    if (carrinhoLocal.length === 0) return alert("Não existe nenhum item digitado para esta venda!");
    const numeroItemTexto = prompt("Digite o número do ITEM que deseja cancelar (ex: 001):");
    if (!numeroItemTexto) return;

    const indexParaRemover = parseInt(numeroItemTexto, 10) - 1;
    if (isNaN(indexParaRemover) || indexParaRemover < 0 || indexParaRemover >= carrinhoLocal.length) {
        return alert("Número de item inválido.");
    }
    if (confirm(`Confirma o Cancelamento do Item [ ${numeroItemTexto} ] ?`)) {
        carrinhoLocal.splice(indexParaRemover, 1);
        atualizarCupomNaTela();
    }
}

function cancelarCupomAtual() {
    if (carrinhoLocal.length === 0 && !vendaIniciada) return;
    if (confirm("Confirma o Cancelamento da Venda?")) {
        limparExibicaoTelas();
        document.getElementById("lbl-status-venda").innerText = "Venda Cancelada";
        document.getElementById("lbl-status-venda").style.color = "#cc0000";
        document.getElementById("bobina-cupom").innerText +=
            "\n************************************************\nVENDA CANCELADA\n";
    }
}

// ============================================================================
// MODAL [F8] EFETUA PAGAMENTO (Equivalente ao EfetuaPagamento.java)
// ============================================================================
let modalPgtoAberto = false;
let listaPagamentosCupom = [];
let valorTrocoAtual = 0.00;

const NOMES_FORMA_PGTO = {
    "01": "01 - DINHEIRO",
    "02": "02 - CHEQUE",
    "03": "03 - CARTÃO DE CRÉDITO",
    "04": "04 - CARTÃO DE DÉBITO",
    "05": "05 - CRÉDITO LOJA",
    "17": "17 - PIX",
    "99": "99 - OUTROS"
};

function finalizarFaturamentoCupom() {
    if (carrinhoLocal.length === 0) {
        return alert("Não existe nenhum item digitado para esta venda! Escolha CANCELA VDA.");
    }

    modalPgtoAberto = true;
    listaPagamentosCupom = [];
    valorTrocoAtual = 0.00;

    document.getElementById("modal-efetua-pagamento").classList.remove("hidden");
    document.getElementById("select-forma-pgto").value = "01";
    atualizarTelaPagamento();

    const inpVal = document.getElementById("input-valor-pgto");
    inpVal.focus();
    inpVal.select();
}

function fecharModalPagamento() {
    modalPgtoAberto = false;
    document.getElementById("modal-efetua-pagamento").classList.add("hidden");
    focarEAN();
}

function atualizarTelaPagamento() {
    const totalPago = listaPagamentosCupom.reduce((acc, p) => acc + p.vpag, 0);
    const restante = Math.max(0, Number((totalCupomAtual - totalPago).toFixed(2)));
    valorTrocoAtual = totalPago > totalCupomAtual
        ? Number((totalPago - totalCupomAtual).toFixed(2))
        : 0.00;

    document.getElementById("pgto-total-cupom").innerText = formatarMoeda(totalCupomAtual);
    document.getElementById("pgto-total-pago").innerText = formatarMoeda(totalPago);
    document.getElementById("pgto-restante").innerText = formatarMoeda(restante);
    document.getElementById("pgto-troco").innerText = formatarMoeda(valorTrocoAtual);

    const inpVal = document.getElementById("input-valor-pgto");
    inpVal.value = formatarMoeda(restante);

    const tbody = document.getElementById("tbody-pagamentos-lancados");
    tbody.innerHTML = listaPagamentosCupom.map((p, idx) => `
        <tr>
            <td>${NOMES_FORMA_PGTO[p.tpag] || p.tpag}</td>
            <td style="text-align: right;">${formatarMoeda(p.vpag)}</td>
            <td style="text-align: center;">
                <button onclick="removerPagamentoLista(${idx})" style="color: #cc0000; font-weight: bold; cursor: pointer;">X</button>
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

function adicionarPagamentoLista() {
    const tpag = document.getElementById("select-forma-pgto").value;
    const rawVal = document.getElementById("input-valor-pgto").value.replace(/\./g, "").replace(",", ".");
    const valor = parseFloat(rawVal);

    if (isNaN(valor) || valor <= 0) {
        return alert("Informe um valor válido maior que zero!");
    }

    const totalPagoAtual = listaPagamentosCupom.reduce((acc, p) => acc + p.vpag, 0);
    const restanteAtual = Number((totalCupomAtual - totalPagoAtual).toFixed(2));

    // Regra fiscal NFC-e: apenas Dinheiro (01) pode gerar troco
    if (tpag !== "01" && valor > restanteAtual + 0.009) {
        return alert("Para Cartão/PIX o valor não pode ser maior que o saldo restante!");
    }

    listaPagamentosCupom.push({ tpag: tpag, vpag: Number(valor.toFixed(2)) });
    atualizarTelaPagamento();
}

function removerPagamentoLista(idx) {
    listaPagamentosCupom.splice(idx, 1);
    atualizarTelaPagamento();
}

async function confirmarEncerramentoVenda() {
    const totalPago = listaPagamentosCupom.reduce((acc, p) => acc + p.vpag, 0);
    if (totalPago + 0.009 < totalCupomAtual) {
        return alert("O valor pago ainda é menor que o total da venda!");
    }

    const btnConfirmar = document.getElementById("btn-confirmar-pgto-final");
    btnConfirmar.disabled = true;
    btnConfirmar.innerText = "TRANSMITINDO NFC-e...";

    const modeloNota = (cpfCnpjClienteAtual && cpfCnpjClienteAtual.length === 14)
        ? "55"
        : (operadorAtivo && operadorAtivo.modelonfe ? operadorAtivo.modelonfe : "65");

    // Envia pagamentos + vtroco no formato do schema FastAPI
    const pagamentosPayload = listaPagamentosCupom.map((p, idx) => ({
        tpag: p.tpag,
        vpag: p.vpag,
        vtroco: idx === listaPagamentosCupom.length - 1 ? valorTrocoAtual : 0.00
    }));

    const payloadFechamento = {
        terminal_id: terminalAtivo.codigo,
        modelo: modeloNota,
        serie: terminalAtivo.serie,
        cpf_cnpj_destinatario: cpfCnpjClienteAtual,
        nome_destinatario: nomeClienteAtual,
        desconto_total: totalDesconto,
        itens_carrinho: carrinhoLocal,
        pagamentos: pagamentosPayload
    };

    try {
        const resposta = await fetch(`${API_URL}/caixa/finalizar-venda`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payloadFechamento)
        });

        if (!resposta.ok) {
            const erroApi = await resposta.json();
            throw new Error(erroApi.detail || "Erro ao processar fechamento.");
        }

        const resultado = await resposta.json();
        if (resultado.xml) {
            const blob = new Blob([resultado.xml], { type: "application/xml" });
            const urlDownload = window.URL.createObjectURL(blob);
            const linkFalso = document.createElement("a");
            linkFalso.href = urlDownload;
            linkFalso.download = resultado.chave_acesso
                ? `NFe${resultado.chave_acesso}.xml`
                : `nota_${resultado.numero_nota}.xml`;
            document.body.appendChild(linkFalso);
            linkFalso.click();
            document.body.removeChild(linkFalso);
            window.URL.revokeObjectURL(urlDownload);
        }

        const msgTroco = valorTrocoAtual > 0 ? `\nTROCO: R$ ${formatarMoeda(valorTrocoAtual)}` : "";
        alert(
            `[Venda Finalizada!]\n` +
            `Terminal: ${terminalAtivo.codigo}\n` +
            `Nota Nº: ${resultado.numero_nota}\n` +
            `Status SEFAZ: ${resultado.status_sefaz}${msgTroco}`
        );

        fecharModalPagamento();
        limparExibicaoTelas();
        document.getElementById("lbl-status-venda").innerText = "Venda Finalizada";
        focarEAN();
    } catch (e) {
        alert(`Falha ao finalizar venda: ${e.message}`);
    } finally {
        btnConfirmar.innerText = "[F8] CONFIRMAR E EMITIR NFC-e";
        atualizarTelaPagamento();
    }
}

// Atalhos de teclado dentro do Modal de Pagamento
document.getElementById("input-valor-pgto").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        const totalPago = listaPagamentosCupom.reduce((acc, p) => acc + p.vpag, 0);
        if (totalPago + 0.009 >= totalCupomAtual && listaPagamentosCupom.length > 0) {
            confirmarEncerramentoVenda();
        } else {
            adicionarPagamentoLista();
        }
    } else if (e.key === "Escape") {
        e.preventDefault();
        fecharModalPagamento();
    }
});

document.getElementById("select-forma-pgto").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        const inpVal = document.getElementById("input-valor-pgto");
        inpVal.focus();
        inpVal.select();
    } else if (e.key === "Escape") {
        e.preventDefault();
        fecharModalPagamento();
    }
});

// Menu Auxiliar [F7]
function toggleMenuAuxiliar(forcarEstado) {
    menuAuxiliarAberto = typeof forcarEstado === "boolean" ? forcarEstado : !menuAuxiliarAberto;
    document.getElementById("painel-menu-aux").classList.toggle("hidden", !menuAuxiliarAberto);
}

// ============================================================================
// MODAL [F3] REIMPRESSÃO / PEDIDOS PENDENTES (Equivalente ao PedidosPendentes.java)
// ============================================================================
let modalReimpAberto = false;
let listaNotasReimp = [];
let indiceNotaReimp = -1;

function reimprimirCupom() {
    toggleMenuAuxiliar(false);
    modalReimpAberto = true;
    listaNotasReimp = [];
    indiceNotaReimp = -1;

    document.getElementById("modal-reimpressao").classList.remove("hidden");
    carregarNotasReimpressao("TODAS");
}

function fecharModalReimpressao() {
    modalReimpAberto = false;
    document.getElementById("modal-reimpressao").classList.add("hidden");
    focarEAN();
}

async function carregarNotasReimpressao(filtro = "TODAS") {
    const tbody = document.getElementById("tbody-notas-reimpressao");
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:18px;">Carregando notas...</td></tr>`;

    try {
        const params = new URLSearchParams({
            filtro: filtro,
            serie: terminalAtivo?.serie || ""
        });
        const resp = await fetch(`${API_URL}/caixa/notas-reimpressao?${params.toString()}`);
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Erro ao consultar notas.");

        listaNotasReimp = data.notas || [];
        indiceNotaReimp = listaNotasReimp.length > 0 ? 0 : -1;
        document.getElementById("lbl-qtd-notas-reimp").innerText = `${listaNotasReimp.length} nota(s) encontrada(s)`;
        renderizarTabelaReimpressao();
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:18px; color:#cc0000;">${e.message}</td></tr>`;
    }
}

function renderizarTabelaReimpressao() {
    const tbody = document.getElementById("tbody-notas-reimpressao");
    const btnTransm = document.getElementById("btn-transmitir-pendente");

    if (listaNotasReimp.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px; color:#666;">Nenhuma nota encontrada para o filtro selecionado.</td></tr>`;
        if (btnTransm) btnTransm.disabled = true;
        return;
    }

    tbody.innerHTML = listaNotasReimp.map((n, idx) => {
        const sel = idx === indiceNotaReimp ? "selecionado" : "";
        const dataFmt = (n.dhemi || "").replace("T", " ").substring(0, 16);
        const corStatus = n.status_sefaz === "AUTORIZADA" ? "#16a34a" : "#cc0000";

        return `
            <tr class="${sel}" onclick="selecionarLinhaReimp(${idx})" ondblclick="executarReimpressaoSelecionada(false, false)">
                <td>${String(n.nnf).padStart(6, "0")}</td>
                <td>${n.serie}</td>
                <td>${n.modelo}</td>
                <td>${dataFmt}</td>
                <td>${n.cliente_nome}</td>
                <td style="text-align:right;">${formatarMoeda(n.vnf)}</td>
                <td style="text-align:center; color:${sel ? "#fff" : corStatus};">${n.status_sefaz}</td>
            </tr>
        `;
    }).join("");

    // Habilita "Transmitir Pendente" somente se a nota selecionada NÃO estiver AUTORIZADA
    const notaAtual = listaNotasReimp[indiceNotaReimp];
    if (btnTransm) {
        btnTransm.disabled = !notaAtual || notaAtual.status_sefaz === "AUTORIZADA";
    }

    const linhaAtiva = tbody.querySelector("tr.selecionado");
    if (linhaAtiva) linhaAtiva.scrollIntoView({ block: "nearest" });
}
async function transmitirNotaPendente() {
    if (indiceNotaReimp < 0 || !listaNotasReimp[indiceNotaReimp]) return;
    const nota = listaNotasReimp[indiceNotaReimp];

    if (nota.status_sefaz === "AUTORIZADA") {
        return alert("Esta nota já está autorizada na SEFAZ.");
    }
    if (!confirm(`Deseja transmitir a NFC-e Nº ${nota.nnf} (Série ${nota.serie}) agora para a SEFAZ?`)) {
        return;
    }

    const btnTransm = document.getElementById("btn-transmitir-pendente");
    btnTransm.disabled = true;
    btnTransm.innerText = "Transmitindo...";

    try {
        const resp = await fetch(`${API_URL}/caixa/notas/${nota.id}/transmitir`, {
            method: "POST"
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Falha ao transmitir nota.");

        alert(`${data.mensagem}\nProtocolo: ${data.nprot}`);
        await carregarNotasReimpressao("TODAS");
    } catch (e) {
        alert("Erro na transmissão: " + e.message);
    } finally {
        btnTransm.innerText = "Transmitir Pendente";
    }
}
function selecionarLinhaReimp(idx) {
    indiceNotaReimp = idx;
    renderizarTabelaReimpressao();
}

async function executarReimpressaoSelecionada(apenasBaixarXml = false) {
    if (indiceNotaReimp < 0 || !listaNotasReimp[indiceNotaReimp]) return;
    const notaResumo = listaNotasReimp[indiceNotaReimp];

    try {
        const resp = await fetch(`${API_URL}/caixa/notas/${notaResumo.id}/detalhes-reimpressao`);
        const dados = await resp.json();
        if (!resp.ok) throw new Error(dados.detail || "Erro ao obter detalhes da nota.");

        const { nota, itens, pagamentos } = dados;

        if (apenasBaixarXml) {
            if (!nota.xml_completo) return alert("Esta nota ainda não possui XML gravado no banco.");
            const blob = new Blob([nota.xml_completo], { type: "application/xml" });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = nota.chnfe ? `NFe${nota.chnfe}.xml` : `nota_${nota.nnf}.xml`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            return;
        }

        // Imprime a 2ª via completa na Bobina Térmica da tela
        let textoCupom =
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
            textoCupom += `${num}${qtd}${unit}${tot} ${(it.xprod || "").substring(0, 22)}\n`;
        });

        textoCupom +=
            "------------------------------------------------\n" +
            `SUBTOTAL R$ : ${formatarMoeda(nota.vprod).padStart(33, " ")}\n` +
            `DESCONTO R$ : ${formatarMoeda(nota.vdesc).padStart(33, " ")}\n` +
            `TOTAL R$    : ${formatarMoeda(nota.vnf).padStart(33, " ")}\n` +
            "------------------------------------------------\n" +
            "PAGAMENTOS:\n";

        pagamentos.forEach((pg) => {
            const nomePg = (NOMES_FORMA_PGTO[pg.tpag] || pg.tpag).padEnd(25, " ");
            const valPg = `R$ ${formatarMoeda(pg.vpag)}`.padStart(20, " ");
            textoCupom += `  ${nomePg}${valPg}\n`;
        });

        textoCupom +=
            "------------------------------------------------\n" +
            `Chave: ${nota.chnfe || "EM CONTINGÊNCIA"}\n` +
            "================================================\n";

        fecharModalReimpressao();
        const bobina = document.getElementById("bobina-cupom");
        bobina.innerText = textoCupom;
        bobina.scrollTop = 0;

        if (imprimirDireto) {
            setTimeout(() => window.print(), 150);
        }
    } catch (e) {
        alert("Falha na reimpressão: " + e.message);
    }
}

// Navegação por teclado quando o Modal [F3] estiver aberto
window.addEventListener("keydown", (e) => {
    if (!modalReimpAberto) return;
    if (e.key === "ArrowDown") {
        e.preventDefault();
        if (indiceNotaReimp < listaNotasReimp.length - 1) {
            indiceNotaReimp++;
            renderizarTabelaReimpressao();
        }
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (indiceNotaReimp > 0) {
            indiceNotaReimp--;
            renderizarTabelaReimpressao();
        }
    } else if (e.key === "Enter") {
        e.preventDefault();
        executarReimpressaoSelecionada(false);
    } else if (e.key === "Escape") {
        e.preventDefault();
        fecharModalReimpressao();
    }
}, true);

function abrirCalculadora() { alert("Data/Hora atual: " + new Date().toLocaleString("pt-BR")); toggleMenuAuxiliar(false); }
function abrirCaixa() { alert("Caixa aberto."); toggleMenuAuxiliar(false); }

// ============================================================================
// MODAL [F1] PROCURA PRODUTO (Equivalente ao ImportaProduto.java)
// ============================================================================
let modalBuscaAberto = false;
let listaProdutosEncontrados = [];
let indiceProdutoSelecionado = -1;
let timerBuscaProduto = null;

function abrirBuscaProduto() {
    if (!vendaIniciada) iniciarVenda();
    modalBuscaAberto = true;
    listaProdutosEncontrados = [];
    indiceProdutoSelecionado = -1;

    const modal = document.getElementById("modal-procura-produto");
    const input = document.getElementById("input-busca-produto");
    modal.classList.remove("hidden");
    input.value = "";
    input.focus();
    consultarProdutosAPI();
}

function fecharBuscaProduto() {
    modalBuscaAberto = false;
    document.getElementById("modal-procura-produto").classList.add("hidden");
    focarEAN();
}

async function consultarProdutosAPI() {
    const termo = document.getElementById("input-busca-produto").value.trim();
    const tbody = document.getElementById("tbody-produtos-busca");
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:16px;">Buscando produtos...</td></tr>`;

    try {
        const resp = await fetch(`${API_URL}/produtos/buscar?q=${encodeURIComponent(termo)}`);
        if (!resp.ok) throw new Error("Endpoint /produtos/buscar indisponível.");
        const dados = await resp.json();

        listaProdutosEncontrados = Array.isArray(dados) ? dados : (dados.produtos || []);
        indiceProdutoSelecionado = listaProdutosEncontrados.length > 0 ? 0 : -1;
        renderizarTabelaBusca();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:16px; color:#cc0000;">Erro ao buscar: ${err.message}</td></tr>`;
    }
}

function renderizarTabelaBusca() {
    const tbody = document.getElementById("tbody-produtos-busca");
    if (listaProdutosEncontrados.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px; color:#666;">Nenhum produto encontrado com preço maior que zero.</td></tr>`;
        return;
    }

    tbody.innerHTML = listaProdutosEncontrados.map((p, idx) => {
        const selecionado = idx === indiceProdutoSelecionado ? "selecionado" : "";
        const codigo = p.cprod || "";
        const ean = p.cean || "SEM GTIN";
        const desc = p.xprod || "";
        const unid = p.ucom || "UN";
        const preco = Number(p.vuncom || 0);

        return `
            <tr class="${selecionado}" onclick="selecionarLinhaBusca(${idx})" ondblclick="confirmarProdutoSelecionado()">
                <td>${codigo}</td>
                <td>${ean}</td>
                <td>${desc}</td>
                <td style="text-align:center;">${unid}</td>
                <td style="text-align:right;">${formatarMoeda(preco)}</td>
            </tr>
        `;
    }).join("");

    const linhaAtiva = tbody.querySelector("tr.selecionado");
    if (linhaAtiva) linhaAtiva.scrollIntoView({ block: "nearest" });
}

function selecionarLinhaBusca(idx) {
    indiceProdutoSelecionado = idx;
    renderizarTabelaBusca();
}

function confirmarProdutoSelecionado() {
    if (indiceProdutoSelecionado < 0 || !listaProdutosEncontrados[indiceProdutoSelecionado]) return;
    const prod = listaProdutosEncontrados[indiceProdutoSelecionado];

    // Usa cEAN se válido; caso contrário usa cProd (padrão do seu endpoint /calcular-cupom)
    const eanValido = prod.cean && prod.cean.trim() !== "" && prod.cean !== "SEM GTIN";
    const codigoParaLancar = eanValido ? prod.cean.trim() : String(prod.cprod).trim();

    fecharBuscaProduto();
    document.getElementById("input-scanner").value = codigoParaLancar;
    registrarItemCarrinho();
}
// Navegação por teclado dentro do Modal (Setas, Enter e ESC)
document.getElementById("input-busca-produto").addEventListener("input", () => {
    clearTimeout(timerBuscaProduto);
    timerBuscaProduto = setTimeout(consultarProdutosAPI, 250);
});

document.getElementById("input-busca-produto").addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") {
        e.preventDefault();
        if (indiceProdutoSelecionado < listaProdutosEncontrados.length - 1) {
            indiceProdutoSelecionado++;
            renderizarTabelaBusca();
        }
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (indiceProdutoSelecionado > 0) {
            indiceProdutoSelecionado--;
            renderizarTabelaBusca();
        }
    } else if (e.key === "Enter") {
        e.preventDefault();
        confirmarProdutoSelecionado();
    } else if (e.key === "Escape") {
        e.preventDefault();
        fecharBuscaProduto();
    }
});


// Eventos de teclado
document.getElementById("input-scanner").addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        registrarItemCarrinho();
    }
});

window.addEventListener("keydown", (e) => {
    if (typeof operadorAtivo === "undefined" || !operadorAtivo) return;
    if (e.key === "F10") { e.preventDefault(); fazerLogoff(); return; }

    const ehCaixa = (operadorAtivo.grupo_geral || "").trim().toUpperCase() === "CAIXA";
    if (!ehCaixa) return;

    if (e.key === "F7") { e.preventDefault(); toggleMenuAuxiliar(); return; }

    if (menuAuxiliarAberto) {
        if (e.key === "F1") { e.preventDefault(); executarSuprimento(); }
        if (e.key === "F2") { e.preventDefault(); executarSangria(); }
        if (e.key === "F3") { e.preventDefault(); reimprimirCupom(); }
        if (e.key === "F4") { e.preventDefault(); abrirCalculadora(); }
        if (e.key === "F5") { e.preventDefault(); abrirCaixa(); }
        if (e.key === "F6") { e.preventDefault(); emitirLeituraX(); }
        return;
    }

    if (e.key === "F1")  { e.preventDefault(); abrirBuscaProduto(); }
    if (e.key === "F2")  { e.preventDefault(); alterarQuantidade(); }
    if (e.key === "F4")  { e.preventDefault(); informarCpfNota(); }
    if (e.key === "F5")  { e.preventDefault(); cancelarItemEspecifico(); }
    if (e.key === "F6")  { e.preventDefault(); cancelarCupomAtual(); }
    if (e.key === "F8")  { e.preventDefault(); finalizarFaturamentoCupom(); }
    if (e.key === "F9")  { e.preventDefault(); focarEAN(); }
    if (e.key === "F11") { e.preventDefault(); aplicarDesconto(); }
    if (e.key === "F12") { e.preventDefault(); aplicarAcrescimo(); }
});
// ============================================================================
// MENU AUXILIAR [F7]: SUPRIMENTO, SANGRIA E LEITURA X
// ============================================================================
function verificarPermissaoGerente() {
    const grupo = (operadorAtivo?.grupo_geral || "").trim().toUpperCase();
    if (grupo === "GERENTE" || grupo === "ADMIN" || grupo === "SUPORTE") {
        return operadorAtivo.usua_nome;
    }
    const gerente = prompt("Operação restrita! Informe o usuário/senha do Gerente ou Supervisor:");
    return gerente && gerente.trim() !== "" ? gerente.trim() : null;
}

async function executarSuprimento() {
    toggleMenuAuxiliar(false);
    const autorizador = verificarPermissaoGerente();
    if (!autorizador) return;

    const valStr = prompt("Informe o valor do SUPRIMENTO (R$):", "0,00");
    if (valStr === null) return;
    const valor = parseFloat(valStr.replace(/\./g, "").replace(",", "."));
    if (isNaN(valor) || valor <= 0) return alert("Valor inválido para suprimento!");

    try {
        const resp = await fetch(`${API_URL}/caixa/suprimento`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                terminal_id: terminalAtivo.codigo,
                operador: operadorAtivo.usua_nome,
                gerente_autorizador: autorizador,
                valor: valor
            })
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Erro ao gravar suprimento.");

        alert(`Suprimento de R$ ${formatarMoeda(valor)} registrado com sucesso! (ID: ${data.id})`);
    } catch (e) {
        alert("Falha no Suprimento: " + e.message);
    } finally {
        focarEAN();
    }
}

async function executarSangria() {
    toggleMenuAuxiliar(false);
    const autorizador = verificarPermissaoGerente();
    if (!autorizador) return;

    const valStr = prompt("Informe o valor da SANGRIA (R$):", "0,00");
    if (valStr === null) return;
    const valor = parseFloat(valStr.replace(/\./g, "").replace(",", "."));
    if (isNaN(valor) || valor <= 0) return alert("Valor inválido para sangria!");

    try {
        const resp = await fetch(`${API_URL}/caixa/sangria`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                terminal_id: terminalAtivo.codigo,
                operador: operadorAtivo.usua_nome,
                gerente_autorizador: autorizador,
                valor: valor
            })
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Erro ao gravar sangria.");

        alert(`Sangria de R$ ${formatarMoeda(valor)} registrada com sucesso! (ID: ${data.id})`);
    } catch (e) {
        alert("Falha na Sangria: " + e.message);
    } finally {
        focarEAN();
    }
}

async function emitirLeituraX() {
    toggleMenuAuxiliar(false);
    try {
        const params = new URLSearchParams({
            terminal_id: terminalAtivo.codigo,
            serie: terminalAtivo.serie || ""
        });
        const resp = await fetch(`${API_URL}/caixa/leitura-x?${params.toString()}`);
        const r = await resp.json();
        if (!resp.ok) throw new Error(r.detail || "Erro ao gerar Leitura X.");

        let linhasPgtos = "";
        if (r.detalhe_pagamentos && r.detalhe_pagamentos.length > 0) {
            r.detalhe_pagamentos.forEach(p => {
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
            `Terminal : ${r.terminal_id} (Série ${terminalAtivo.serie || "1"})\n` +
            `Operador : ${operadorAtivo.usua_nome}\n` +
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
    } catch (e) {
        alert("Falha ao emitir Leitura X: " + e.message);
    } finally {
        focarEAN();
    }
}
