let vendaIniciada = false;
let menuAuxiliarAberto = false;
let carrinhoLocal = [];
let cpfCnpjClienteAtual = null;
let nomeClienteAtual = null;
let totalBrutoCupom = 0.00;
let totalDesconto = 0.00;
let percAcrescimo = 0.00;
let qtdeAtual = 1.00;
let numeroPedidoAtual = 1;

// Relógio em tempo real (equivalente ao Timer do formWindowOpened no Java)
setInterval(() => {
    const agora = new Date();
    document.getElementById("lbl-data").innerText = "Data: " + agora.toLocaleDateString("pt-BR");
    document.getElementById("lbl-hora").innerText = "Hora: " + agora.toLocaleTimeString("pt-BR");
}, 1000);

function formatarMoeda(valor) {
    return valor.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function iniciarVenda() {
    if (vendaIniciada && carrinhoLocal.length > 0) {
        alert("Para iniciar uma nova venda, finalize ou cancele a venda em aberto!");
        return;
    }
    vendaIniciada = true;
    carrinhoLocal = [];
    cpfCnpjClienteAtual = null;
    nomeClienteAtual = null;
    totalBrutoCupom = 0.00;
    totalDesconto = 0.00;
    percAcrescimo = 0.00;
    qtdeAtual = 1.00;

    document.getElementById("lbl-status-venda").innerText = "Venda Aberta";
    document.getElementById("lbl-status-venda").className = "text-2xl font-extrabold text-blue-900";
    document.getElementById("txt-descricao").value = "";
    document.getElementById("input-quantidade").value = "1.00";
    document.getElementById("txt-preco-unit").value = "0,00";
    document.getElementById("txt-total-prod").value = "0,00";
    document.getElementById("lbl-doc-cliente").innerText = "Documento: Não informado";
    document.getElementById("lbl-perc-acrescimo").innerText = "";
    document.getElementById("btn-acrescimo").disabled = false;
    document.getElementById("btn-iniciar").disabled = true;

    document.getElementById("bobina-cupom").innerHTML = `
        <div>*---------------- Venda Aberta ----------------*</div>
        <div>ITEM CODIGO    DESCRIÇÃO        QTD   UNIT   TOTAL</div>
        <div>------------------------------------------------</div>
    `;
    atualizarVisoresTotais();
    focarEAN();
}

function focarEAN() {
    const inp = document.getElementById("input-scanner");
    inp.disabled = false;
    inp.focus();
    inp.select();
}

function alterarQuantidade() {
    if (!vendaIniciada) return alert("Inicie uma venda primeiro!");
    if (operadorAtivo && operadorAtivo.alterar_qtde === "N") {
        const senha = prompt("Operador sem permissão. Digite a senha do Gerente/Supervisor:");
        if (!senha) return;
    }
    const novaQtde = prompt("Informe a Quantidade:", qtdeAtual.toFixed(2));
    if (novaQtde === null) return;
    const parsed = parseFloat(novaQtde.replace(",", "."));
    if (isNaN(parsed) || parsed <= 0) {
        alert("Quantidade inválida!");
        return;
    }
    qtdeAtual = parsed;
    document.getElementById("input-quantidade").value = qtdeAtual.toFixed(2);
    focarEAN();
}

// Trata EAN, ".codInterno", "*codFornecedor" e código de balança "2..." (igual ao buscarProduto do Java)
async function registrarItemCarrinho() {
    if (!vendaIniciada) iniciarVenda();
    const inp = document.getElementById("input-scanner");
    let codigo = inp.value.trim();
    if (!codigo) return;

    let tipoBusca = "ean";
    if (codigo.startsWith(".")) {
        tipoBusca = "codigo_interno";
        codigo = codigo.substring(1).trim();
    } else if (codigo.startsWith("*")) {
        tipoBusca = "codigo_fornecedor";
        codigo = codigo.substring(1).trim().toUpperCase();
    } else if (codigo.startsWith("2") && codigo.length === 13) {
        tipoBusca = "balanca";
    }

    carrinhoLocal.push({
        codigo: codigo,
        tipo_busca: tipoBusca,
        quantidade: qtdeAtual,
        acrescimo_perc: percAcrescimo
    });

    inp.value = "";
    qtdeAtual = 1.00;
    document.getElementById("input-quantidade").value = "1.00";
    await sincronizarCupomBackend();
}

async function sincronizarCupomBackend() {
    try {
        const resp = await fetch(`${API_URL}/caixa/calcular-cupom`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ itens_carrinho: carrinhoLocal })
        });
        if (!resp.ok) throw new Error("Erro ao calcular item.");
        const dados = await resp.json();

        const bobina = document.getElementById("bobina-cupom");
        bobina.innerHTML = `
            <div>ITEM CODIGO    DESCRIÇÃO        QTD   UNIT   TOTAL</div>
            <div>------------------------------------------------</div>
        `;

        dados.itens_aprovados.forEach((item, idx) => {
            const num = String(idx + 1).padStart(3, "0");
            const desc = item.nome_produto.substring(0, 16).padEnd(16, " ");
            const qtdStr = item.qCom.toFixed(2).padStart(6, " ");
            const unitStr = item.vUnCom.toFixed(2).padStart(7, " ");
            const totStr = item.vProd.toFixed(2).padStart(7, " ");

            bobina.innerHTML += `<div>${num} ${qtdStr} ${unitStr} ${totStr} ${desc}</div>`;

            // Atualiza painel esquerdo com o último item lançado
            if (idx === dados.itens_aprovados.length - 1) {
                document.getElementById("txt-descricao").value = item.nome_produto;
                document.getElementById("txt-unidade").value = item.uCom || "UN";
                document.getElementById("txt-preco-unit").value = formatarMoeda(item.vUnCom);
                document.getElementById("txt-total-prod").value = formatarMoeda(item.vProd);
            }
        });

        // Bloqueia acréscimo percentual após o 1º item (regra do NFCe.java)
        if (dados.itens_aprovados.length > 0) {
            document.getElementById("btn-acrescimo").disabled = true;
        }

        totalBrutoCupom = dados.resumo.vNF;
        atualizarVisoresTotais();
        bobina.scrollTop = bobina.scrollHeight;
    } catch (err) {
        alert("Erro ao consultar produto no servidor: " + err.message);
        carrinhoLocal.pop();
    }
}

function atualizarVisoresTotais() {
    const totalLiquido = Math.max(0, totalBrutoCupom - totalDesconto);
    document.getElementById("visor-desconto").value = formatarMoeda(totalDesconto);
    document.getElementById("visor-total").value = formatarMoeda(totalLiquido);
}

// [F12] Acréscimo (%) - Somente no início da venda (totCupom == 0)
function aplicarAcrescimo() {
    if (!vendaIniciada || totalBrutoCupom > 0) {
        alert("O % de Acréscimo só pode ser informado no início da venda (antes dos itens)!");
        return;
    }
    const val = prompt("Informe o percentual de Acréscimo (%):", percAcrescimo);
    if (val === null) return;
    const perc = parseFloat(val.replace(",", "."));
    if (isNaN(perc) || perc < 0) return alert("Percentual inválido!");
    percAcrescimo = perc;
    document.getElementById("lbl-perc-acrescimo").innerText = `${percAcrescimo}%`;
    focarEAN();
}

// [F11] Desconto (Vlr) - Máximo de 50% do total do cupom (regra do NFCe.java)
function aplicarDesconto() {
    if (!vendaIniciada || totalBrutoCupom <= 0) return alert("Não há itens para aplicar desconto.");
    const val = prompt("Informe o valor do Desconto (R$):", totalDesconto.toFixed(2));
    if (val === null) return;
    const desc = parseFloat(val.replace(",", "."));
    if (isNaN(desc) || desc < 0) return alert("Valor de desconto não pode ser negativo!");
    if (desc > totalBrutoCupom * 0.5) {
        return alert("Valor do Desconto não pode ser maior que 50% do Total do Cupom!");
    }
    totalDesconto = desc;
    atualizarVisoresTotais();
    focarEAN();
}

// [F7] Abre/Fecha Menu Auxiliar (Suprimento, Sangria, Reimpressão, Leitura X)
function toggleMenuAuxiliar(forcarEstado) {
    menuAuxiliarAberto = typeof forcarEstado === "boolean" ? forcarEstado : !menuAuxiliarAberto;
    const painel = document.getElementById("painel-menu-aux");
    painel.classList.toggle("hidden", !menuAuxiliarAberto);
}

function executarSuprimento() {
    const val = prompt("Valor do SUPRIMENTO (R$):");
    if (val) alert(`Suprimento de R$ ${val} registrado no ${terminalAtivo.codigo}.`);
    toggleMenuAuxiliar(false);
}

function executarSangria() {
    const val = prompt("Valor da SANGRIA (R$):");
    if (val) alert(`Sangria de R$ ${val} registrada no ${terminalAtivo.codigo}.`);
    toggleMenuAuxiliar(false);
}

function reimprimirCupom() { alert("Abrindo consulta de pedidos para reimpressão..."); toggleMenuAuxiliar(false); }
function abrirCalculadora() { alert("Data/Hora atual: " + new Date().toLocaleString("pt-BR")); toggleMenuAuxiliar(false); }
function abrirCaixa() { alert("Caixa aberto para movimentação."); toggleMenuAuxiliar(false); }
function emitirLeituraX() { alert("Gerando relatório de Leitura X..."); toggleMenuAuxiliar(false); }
function abrirBuscaProduto() { alert("Abrir modal de pesquisa de produtos (ImportaProduto)."); }

// Mapeamento completo das teclas de função do NFCe.java
document.getElementById("input-scanner").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        registrarItemCarrinho();
    }
});

window.addEventListener("keydown", (e) => {
    if (!operadorAtivo) return;
    const tecla = e.key;

    if (tecla === "F7") { e.preventDefault(); toggleMenuAuxiliar(); return; }

    // Atalhos quando o Menu Auxiliar [F7] está aberto
    if (menuAuxiliarAberto) {
        if (tecla === "F1") { e.preventDefault(); executarSuprimento(); }
        if (tecla === "F2") { e.preventDefault(); executarSangria(); }
        if (tecla === "F3") { e.preventDefault(); reimprimirCupom(); }
        if (tecla === "F4") { e.preventDefault(); abrirCalculadora(); }
        if (tecla === "F5") { e.preventDefault(); abrirCaixa(); }
        if (tecla === "F6") { e.preventDefault(); emitirLeituraX(); }
return;
}
// Atalhos normais da Frente de Caixa
if (tecla === "F1")  { e.preventDefault(); abrirBuscaProduto(); }
if (tecla === "F2")  { e.preventDefault(); alterarQuantidade(); }
if (tecla === "F4")  { e.preventDefault(); informarCpfNota(); }
if (tecla === "F5")  { e.preventDefault(); cancelarItemEspecifico(); }
if (tecla === "F6")  { e.preventDefault(); cancelarCupomAtual(); }
if (tecla === "F8")  { e.preventDefault(); finalizarFaturamentoCupom(); }
if (tecla === "F9")  { e.preventDefault(); focarEAN(); }
if (tecla === "F10") { e.preventDefault(); fazerLogoff(); }
if (tecla === "F11") { e.preventDefault(); aplicarDesconto(); }
if (tecla === "F12") { e.preventDefault(); aplicarAcrescimo(); }
}, true);