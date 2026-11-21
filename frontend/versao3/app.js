let operadorAtivo = null;
let carrinhoLocal = [];
let cpfCnpjClienteAtual = null;
let nomeClienteAtual = null;
let totalCupomAtual = 0.00;

// 2. AUTENTICAÇÃO GRANULAR CONTRA TABELA 'usuarios'
async function executarLogin() {
    const inpUser = document.getElementById("login-usuario");
    const inpGrupo = document.getElementById("login-grupo");
    const inpSenha = document.getElementById("login-senha");
    const selTerm = document.getElementById("login-terminal");
    const erroBox = document.getElementById("login-erro-box");

    [inpUser, inpGrupo, inpSenha].forEach(el => el.classList.remove("border-rose-500"));
    erroBox.classList.add("hidden");

    try {
        const resp = await fetch(`${API_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                usua_nome: inpUser.value,
                grupo: inpGrupo.value,
                usua_senha: inpSenha.value
            })
        });

        const data = await resp.json();
        if (!resp.ok) {
            const det = data.detail || {};
            erroBox.innerText = det.mensagem || "Erro de autenticação.";
            erroBox.classList.remove("hidden");
            const mapa = { usua_nome: inpUser, grupo: inpGrupo, usua_senha: inpSenha };
            if (mapa[det.campo]) {
                mapa[det.campo].classList.add("border-rose-500");
                mapa[det.campo].focus();
            }
            return;
        }

        operadorAtivo = data.operador;
        const optSel = selTerm.options[selTerm.selectedIndex];
        
        document.getElementById("tela-login").classList.add("hidden");
        document.getElementById("sistema-principal").classList.remove("hidden");
        document.getElementById("header-terminal-badge").innerText = terminalAtivo.codigo;
        document.getElementById("header-operador-badge").innerText = `Operador: ${operadorAtivo.usua_nome} [${operadorAtivo.grupo_informado}]`;
        document.getElementById("sidebar-operador-info").innerText = `${operadorAtivo.usua_nome} (${operadorAtivo.grupo_informado})`;

        // Perfil CAIXA oculta a retaguarda; outros perfis mantêm o menu lateral visível
        if (operadorAtivo.grupo_geral === "CAIXA") {
            document.getElementById("sidebar-retaguarda").classList.add("hidden");
        } else {
            document.getElementById("sidebar-retaguarda").classList.remove("hidden");
        }
        abrirTelaPDV();

    } catch (err) {
        erroBox.innerText = "Falha de conexão com o servidor Python.";
        erroBox.classList.remove("hidden");
    }
}

function toggleMenu(id) {
    document.getElementById(id).classList.toggle("hidden");
}

function abrirTelaPDV() {
    document.getElementById("view-modulo-retaguarda").classList.add("hidden");
    document.getElementById("aba-gerente").classList.add("hidden");
    const abaCx = document.getElementById("aba-caixa");
    abaCx.classList.remove("hidden");
    abaCx.classList.add("flex");
    document.getElementById("btn-caixa").className = "px-3 py-1 rounded bg-blue-700 font-semibold text-white";
    document.getElementById("btn-gerente").className = "px-3 py-1 rounded text-gray-300 hover:text-white font-semibold";
    setTimeout(() => document.getElementById("input-scanner").focus(), 100);
}

function abrirModuloRetaguarda(nomeModulo) {
    document.getElementById("aba-caixa").classList.add("hidden");
    document.getElementById("aba-caixa").classList.remove("flex");
    document.getElementById("aba-gerente").classList.add("hidden");
    const view = document.getElementById("view-modulo-retaguarda");
    view.classList.remove("hidden");
    view.innerHTML = `
        <div class="max-w-4xl mx-auto bg-white p-6 rounded-xl shadow">
            <h2 class="text-xl font-bold text-slate-800 border-b pb-3 mb-4">Módulo Retaguarda: ${nomeModulo}</h2>
            <p class="text-sm text-slate-600">Tela pronta para conectar aos endpoints REST do banco espelho XML.</p>
        </div>
    `;
}

function abrirAbaGerenteAuditoria() {
    document.getElementById("view-modulo-retaguarda").classList.add("hidden");
    document.getElementById("aba-caixa").classList.add("hidden");
    document.getElementById("aba-caixa").classList.remove("flex");
    document.getElementById("aba-gerente").classList.remove("hidden");
    document.getElementById("btn-gerente").className = "px-3 py-1 rounded bg-blue-700 font-semibold text-white";
    document.getElementById("btn-caixa").className = "px-3 py-1 rounded text-gray-300 hover:text-white font-semibold";
}

// 3. OPERAÇÕES DO PDV (BIPAGEM E CARRINHO)
function informarCpfNota() {
    const doc = prompt("Informe o CPF ou CNPJ do consumidor (apenas números):", cpfCnpjClienteAtual || "");
    if (doc === null) return;

    const docLimpo = doc.replace(/\D/g, "");
    if (docLimpo === "") {
        cpfCnpjClienteAtual = null;
        nomeClienteAtual = null;
        alert("CPF/CNPJ removido do cupom.");
        return;
    }

    if (docLimpo.length !== 11 && docLimpo.length !== 14) {
        alert("Documento inválido! Digite 11 dígitos para CPF ou 14 dígitos para CNPJ.");
        return;
    }

    cpfCnpjClienteAtual = docLimpo;
    nomeClienteAtual = docLimpo.length === 14
        ? (prompt("Informe a Razão Social / Nome do cliente:", nomeClienteAtual || "") || "CONSUMIDOR")
        : "CONSUMIDOR";

    alert(`Cliente vinculado ao cupom: ${cpfCnpjClienteAtual}`);
}

function registrarItemCarrinho() {
    const inputScanner = document.getElementById("input-scanner");
    const inputQuantidade = document.getElementById("input-quantidade");
    const inputPrecoManual = document.getElementById("input-preco-manual");

    const codigoBipado = inputScanner.value.trim();
    if (!codigoBipado) return;

    const qtdFormatada = parseFloat(inputQuantidade.value.replace(/\./g, "").replace(",", "."));
    const precoFormatado = parseFloat(inputPrecoManual.value.replace(/\./g, "").replace(",", "."));

    carrinhoLocal.push({
        codigo: codigoBipado,
        quantidade: isNaN(qtdFormatada) ? 1.000 : qtdFormatada,
        preco_contingencia: isNaN(precoFormatado) ? 0.00 : precoFormatado
    });

    inputScanner.value = "";
    inputQuantidade.value = "1,000";
    inputPrecoManual.value = "0,00";
    inputScanner.focus();

    atualizarCupomNaTela();
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
        const dadosCupom = await resposta.json();
        renderizarCarrinhoECupom(dadosCupom);
    } catch (erro) {
        alert("Falha ao comunicar com o Motor Fiscal.");
    }
}
function renderizarCarrinhoECupom(dados) {
    const tbody = document.getElementById("tabela-carrinho");
    const cupomLinhas = document.getElementById("cupom-linhas");
    const cupomRodape = document.getElementById("cupom-rodape");
    const monitorItem = document.getElementById("monitor-item");

    tbody.innerHTML = "";
    cupomLinhas.innerHTML = "";

    dados.itens_aprovados.forEach((item, index) => {
        const numItem = String(index + 1).zfill(3);
        tbody.innerHTML += `
            <tr class="hover:bg-gray-50 border-b">
                <td class="p-2 pl-4 font-bold text-gray-500">${numItem}</td>
                <td class="p-2 flex flex-col">
                    <span class="font-bold text-gray-800">${item.nome_produto}</span>
                    <span class="text-xs text-gray-400 font-sans">NCM: ${item.ncm}</span>
                </td>
                <td class="p-2 text-center">${item.qCom.toFixed(3)} ${item.uCom}</td>
                <td class="p-2 text-right pr-4 font-bold text-gray-700">R$ ${item.vProd.toFixed(2)}</td>
            </tr>
        `;

        cupomLinhas.innerHTML += `
            <div class="flex justify-between">
                <span>${numItem} ${item.id_produto} ${item.nome_produto.substring(0, 16)} ${item.qCom.toFixed(3)} ${item.uCom} x ${item.vUnCom.toFixed(2)}</span>
                <span>R$${item.vProd.toFixed(2)}</span>
            </div>
        `;

        if (index === dados.itens_aprovados.length - 1) {
            monitorItem.classList.remove("hidden");
            document.getElementById("monitor-nome").innerText = item.nome_produto;
            document.getElementById("monitor-detalhe").innerText = `${item.qCom.toFixed(3)} ${item.uCom} x R$ ${item.vUnCom.toFixed(2)} = R$ ${item.vProd.toFixed(2)} (${item.regime})`;
        }
    });

    dados.itens_bloqueados.forEach((item) => {
        const cardScanner = document.querySelector(".scanner-card");
        const statusScanner = document.getElementById("status-scanner");
        const inputPreco = document.getElementById("input-preco-manual");
        const inputScanner = document.getElementById("input-scanner");

        cardScanner.style.backgroundColor = "#450a0a";
        cardScanner.style.borderColor = "var(--accent-rose)";
        statusScanner.innerText = `[ALERTA: '${item.nome_produto.toUpperCase()}' ESTÁ SEM PREÇO]`;
        statusScanner.style.color = "var(--accent-rose)";
        inputScanner.value = item.id_produto || "";
        inputPreco.focus();
        inputPreco.setSelectionRange(inputPreco.value.length, inputPreco.value.length);
        carrinhoLocal.pop();

        inputPreco.addEventListener("keydown", function restaurarEstiloCaixa(e) {
            if (e.key === "Enter" || inputPreco.value !== "0,00") {
                cardScanner.style.backgroundColor = "#111827";
                cardScanner.style.borderColor = "#374151";
                statusScanner.innerText = "aguardando bip...";
                statusScanner.style.color = "var(--accent-sky)";
                inputPreco.removeEventListener("keydown", restaurarEstiloCaixa);
            }
        });
    });

    document.getElementById("resumo-ibs").innerText = `R$ ${dados.resumo.vIBS_Total.toFixed(2)}`;
    document.getElementById("resumo-cbs").innerText = `R$ ${dados.resumo.vCBS_Total.toFixed(2)}`;
    totalCupomAtual = dados.resumo.vNF;
    document.getElementById("visor-total").innerText = `R$ ${dados.resumo.vNF.toFixed(2)}`;

    cupomRodape.classList.remove("hidden");
    cupomRodape.innerHTML = `
        <div style="display: flex; justify-content: space-between; font-weight: bold; font-size: 13px; color: #000; border-bottom: 1px dashed #78350f; padding-bottom: 4px; margin-bottom: 4px;">
            <span>TOTAL R$</span>
            <span>${dados.resumo.vNF.toFixed(2)}</span>
        </div>
        <div style="font-size: 9px; color: #4b5563;">
            <p style="font-weight: bold; color: #1e293b;">TRIBUTOS REFORMA (IVA DUAL LC 214/2025)</p>
            <div style="display: flex; justify-content: space-between;"><span>* IBS CALCULADO:</span><span>R$ ${dados.resumo.vIBS_Total.toFixed(2)}</span></div>
            <div style="display: flex; justify-content: space-between;"><span>* CBS CALCULADO:</span><span>R$ ${dados.resumo.vCBS_Total.toFixed(2)}</span></div>
        </div>
    `;
}

function cancelarItemEspecifico() {
    if (carrinhoLocal.length === 0) return alert("O carrinho está vazio.");
    const numeroItemTexto = prompt("Digite o número do ITEM que deseja cancelar (ex: 001):");
    if (!numeroItemTexto) return;

    const indexParaRemover = parseInt(numeroItemTexto, 10) - 1;
    if (isNaN(indexParaRemover) || indexParaRemover < 0 || indexParaRemover >= carrinhoLocal.length) {
        return alert("Número de item inválido.");
    }
    if (confirm(`Confirma o cancelamento do ITEM ${numeroItemTexto}?`)) {
        carrinhoLocal.splice(indexParaRemover, 1);
        atualizarCupomNaTela();
    }
}

function cancelarCupomAtual() {
    if (confirm("Deseja realmente cancelar o cupom atual?")) {
        limparExibicaoTelas();
    }
}

function limparExibicaoTelas() {
    carrinhoLocal = [];
    document.getElementById("tabela-carrinho").innerHTML = "";
    document.getElementById("cupom-linhas").innerHTML = `<div style="text-align: center; color: #64748b; padding-top: 24px; font-style: italic;">Nenhum item faturado ate o momento.</div>`;
    document.getElementById("cupom-rodape").classList.add("hidden");
    document.getElementById("monitor-item").classList.add("hidden");
    document.getElementById("visor-total").innerText = "R$ 0,00";
    document.getElementById("resumo-ibs").innerText = "R$ 0,00";
    document.getElementById("resumo-cbs").innerText = "R$ 0,00";
    cpfCnpjClienteAtual = null;
    nomeClienteAtual = null;
    totalCupomAtual = 0.00;
}

async function finalizarFaturamentoCupom() {
    if (carrinhoLocal.length === 0) return alert("O carrinho está vazio.");

    const formaPag = prompt(
        `Terminal: ${terminalAtivo.codigo} (Série ${terminalAtivo.serie})\n` +
        `Total a Pagar: R$ ${totalCupomAtual.toFixed(2)}\n\n` +
        `Forma de Pagamento:\n01 - Dinheiro | 03 - Crédito | 04 - Débito | 17 - PIX`,
        "01"
    );
    if (!formaPag) return;

    const modeloNota = (cpfCnpjClienteAtual && cpfCnpjClienteAtual.length === 14)
        ? "55"
        : (operadorAtivo && operadorAtivo.modelonfe ? operadorAtivo.modelonfe : "65");

    const payloadFechamento = {
        terminal_id: terminalAtivo.codigo,
        modelo: modeloNota,
        serie: terminalAtivo.serie,
        cpf_cnpj_destinatario: cpfCnpjClienteAtual,
        nome_destinatario: nomeClienteAtual,
        itens_carrinho: carrinhoLocal,
        pagamentos: [{ tpag: formaPag.trim().padStart(2, "0"), vpag: totalCupomAtual, vtroco: 0.00 }]
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
            linkFalso.download = resultado.chave_acesso ? `NFe${resultado.chave_acesso}.xml` : `nota_${resultado.numero_nota}.xml`;
            document.body.appendChild(linkFalso);
            linkFalso.click();
            document.body.removeChild(linkFalso);
            window.URL.revokeObjectURL(urlDownload);
        }

        alert(`[Venda Finalizada!]\nTerminal: ${terminalAtivo.codigo}\nNota Nº: ${resultado.numero_nota}\nStatus SEFAZ: ${resultado.status_sefaz}`);
        limparExibicaoTelas();
        document.getElementById("input-scanner").focus();
    } catch (e) {
        alert(`Falha ao finalizar venda: ${e.message}`);
    }
}

async function carregarRelatorioInconsistencias() {
    try {
        const res = await fetch(`${API_URL}/auditoria/inconsistencias`);
        const data = await res.json();
        const container = document.getElementById("container-auditoria");
        container.innerHTML = data.inconsistencias.length === 0
            ? `<p class="p-4 text-center text-green-600 font-bold">[✓] Nenhuma inconsistência fiscal detectada!</p>`
            : data.inconsistencias.map(err => `<div class="p-3 bg-red-50 border-b text-xs text-red-900 font-bold">ID: ${err.id_produto} | ${err.falha}</div>`).join("");
    } catch (e) {
        alert("Erro ao puxar dados do Módulo de Auditoria.");
    }
}

String.prototype.zfill = function(size) {
    let s = this;
    while (s.length < (size || 2)) { s = "0" + s; }
    return s;
};

function aplicarMascaraDecimal(input, casasDecimais) {
    input.addEventListener("input", function() {
        let digits = this.value.replace(/\D/g, "") || "0";
        let resultado = parseInt(digits, 10) / Math.pow(10, casasDecimais);
        this.value = resultado.toLocaleString("pt-BR", { minimumFractionDigits: casasDecimais, maximumFractionDigits: casasDecimais });
    });
    input.addEventListener("focus", function() {
        setTimeout(() => { this.setSelectionRange(this.value.length, this.value.length); }, 10);
    });
}

aplicarMascaraDecimal(document.getElementById("input-quantidade"), 3);
aplicarMascaraDecimal(document.getElementById("input-preco-manual"), 2);

document.getElementById("input-scanner").addEventListener("keypress", e => { if (e.key === "Enter") registrarItemCarrinho(); });
document.getElementById("input-preco-manual").addEventListener("keypress", function(e) {
if (e.key === "Enter" && document.getElementById("input-scanner").value.trim() !== "" && this.value.trim() !== "0,00") {
e.preventDefault();
registrarItemCarrinho();
}
});
window.addEventListener("keydown", function(e) {
 if (!operadorAtivo) return;
    if (e.key === "F10") { e.preventDefault(); fazerLogoff(); return; }

    // Bloqueia atalhos do PDV se o usuário NÃO for do grupo CAIXA
    const ehCaixa = (operadorAtivo.grupo_geral || "").trim().toUpperCase() === "CAIXA";
    if (!ehCaixa) return;
if (e.key === "F1") { e.preventDefault(); document.getElementById("input-preco-manual").focus(); }
if (e.key === "F2") {
e.preventDefault();
if (operadorAtivo.alterar_qtde === "N") return alert("Seu usuário não possui permissão para alterar quantidade.");
document.getElementById("input-quantidade").focus();
}
if (e.key === "F4") { e.preventDefault(); informarCpfNota(); }
if (e.key === "F5") { e.preventDefault(); cancelarItemEspecifico(); }
if (e.key === "F6") { e.preventDefault(); cancelarCupomAtual(); }
if (e.key === "F8") { e.preventDefault(); finalizarFaturamentoCupom(); }
if (e.key === "F9") { e.preventDefault(); document.getElementById("input-scanner").focus(); }
if (e.key === "F10") { e.preventDefault(); fazerLogoff(); }
});