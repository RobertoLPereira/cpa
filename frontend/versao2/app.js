// Configuração da URL base da API do Gerente Central
const API_URL = "http://localhost:8000/api/v1";

// Estado em memória do Carrinho de Compras atual do Caixa
let carrinhoLocal = [];

// 1. GERENCIAMENTO DE ABAS DA INTERFACE
function alternarAba(aba) {
    const abaCaixa = document.getElementById("aba-caixa");
    const abaGerente = document.getElementById("aba-gerente");
    const btnCaixa = document.getElementById("btn-caixa");
    const btnGerente = document.getElementById("btn-gerente");

    if (aba === "caixa") {
        abaCaixa.classList.remove("hidden");
        abaCaixa.classList.add("flex");
        abaGerente.classList.add("hidden");
        btnCaixa.className = "px-4 py-2 rounded bg-blue-700 font-semibold shadow text-white";
        btnGerente.className = "px-4 py-2 rounded text-gray-300 hover:text-white font-semibold";
    } else {
        abaCaixa.classList.add("hidden");
        abaCaixa.classList.remove("flex");
        abaGerente.classList.remove("hidden");
        btnCaixa.className = "px-4 py-2 rounded text-gray-300 hover:text-white font-semibold";
        btnGerente.className = "px-4 py-2 rounded bg-blue-700 font-semibold shadow text-white";
    }
}

// 2. OPERAÇÕES DO FRENTE DE CAIXA (PDV) REFORMULADAS
function registrarItemCarrinho() {
    const inputScanner = document.getElementById("input-scanner");
    const inputQuantidade = document.getElementById("input-quantidade");
    const inputPrecoManual = document.getElementById("input-preco-manual");

    const codigoBipado = inputScanner.value.trim();

    if (!codigoBipado) return;

    // Converte os padrões brasileiros "1.500" ou "10,50" para floats puros de banco (1.5 e 10.5)
    const qtdFormatada = parseFloat(inputQuantidade.value.replace(/\./g, "").replace(",", "."));
    const precoFormatado = parseFloat(inputPrecoManual.value.replace(/\./g, "").replace(",", "."));
    
    // Monta o payload estruturado para o Motor Fiscal do Gerente Central
    const itemPayload = {
        codigo: codigoBipado,
        quantidade: isNaN(qtdFormatada) ? 1.000 : qtdFormatada,
        preco_contingencia: isNaN(precoFormatado) ? 0.00 : precoFormatado
    };

    // Adiciona o objeto completo na memória do caixa
    carrinhoLocal.push(itemPayload);

    // Reseta os campos para o padrão comercial de forma suave
    inputScanner.value = "";
    inputQuantidade.value = "1,000";
    inputPrecoManual.value = "0,00";
    inputScanner.focus();

    // Dispara a atualização assíncrona recalculando o cupom inteiro em lote
    atualizarCupomNaTela();
}

async function atualizarCupomNaTela() {
    if (carrinhoLocal.length === 0) {
        limparExibicaoTelas();
        return;
    }

    try {
        // Envia o lote estruturado (com as quantidades decimais e preços de contingência)
        const resposta = await fetch(`${API_URL}/caixa/calcular-cupom`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ itens_carrinho: carrinhoLocal })
        });

        if (!resposta.ok) throw new Error("Erro na comunicação com a API do Gerente.");

        const dadosCupom = await resposta.json();
        renderizarCarrinhoECupom(dadosCupom);

    } catch (erro) {
        console.error("[Erro Caixa]:", erro);
        alert("Falha ao comunicar com o Motor Fiscal do Gerente. Verifique se o backend está ativo.");
    }
}

function renderizarCarrinhoECupom(dados) {
    const tbody = document.getElementById("tabela-carrinho");
    const cupomLinhas = document.getElementById("cupom-linhas");
    const cupomRodape = document.getElementById("cupom-rodape");
    const monitorItem = document.getElementById("monitor-item");

    tbody.innerHTML = "";
    cupomLinhas.innerHTML = "";

    // 1. Renderiza os Itens Aprovados no Carrinho e no Cupom Térmico
    dados.itens_aprovados.forEach((item, index) => {
        const numItem = String(index + 1).zfill(3);
        console.log(item);
        // Linha da Tabela Comercial do PDV
        tbody.innerHTML += `
            <tr class="hover:bg-gray-50 border-b">
                <td class="p-2 pl-4 font-bold text-gray-500">${numItem}</td>
                <td class="p-2 flex flex-col">
                    <span class="font-bold text-gray-800">${item.nome_produto}</span>
                    <span class="text-xs text-gray-400 font-sans">NCM: ${item.ncm} </span>
                </td>
                <td class="p-2 text-center">${item.qCom.toFixed(3)} ${item.uCom}</td>
                <td class="p-2 text-right pr-4 font-bold text-gray-700">R$ ${item.vProd.toFixed(2)}</td>
            </tr>
        `;

        // Linha do Cupom Fiscal Fiel ao Padrão de Saída
        cupomLinhas.innerHTML += `
            <div class="flex justify-between">
                <span>${numItem} ${item.id_produto} ${item.nome_produto.substring(0, 16)} ${item.qCom.toFixed(3)} ${item.uCom} x ${item.vUnCom.toFixed(2)} </span>
                <span>R$${item.vProd.toFixed(2)}</span>
            </div>
            
        `;

        // Alimenta o monitor do último item bipado
        if (index === dados.itens_aprovados.length - 1) {
            monitorItem.classList.remove("hidden");
            document.getElementById("monitor-nome").innerText = item.nome_produto;
            document.getElementById("monitor-detalhe").innerText = `${item.qCom.toFixed(3)} ${item.uCom} x R$ ${item.vUnCom.toFixed(2)} = R$ ${item.vProd.toFixed(2)} (${item.regime})`;
        }
    });

    // 2. Exibe os Itens Bloqueados ou Rejeitados pelo Gerente (Preço Zerado)
        // 2. Exibe os Itens Bloqueados ou Rejeitados pelo Gerente (Preço Zerado)
        // 2. Exibe os Itens Bloqueados ou Rejeitados pelo Gerente (Preço Zerado)
    dados.itens_bloqueados.forEach((item) => {
        const cardScanner = document.querySelector(".scanner-card");
        const statusScanner = document.getElementById("status-scanner");
        const inputPreco = document.getElementById("input-preco-manual");
        const inputScanner = document.getElementById("input-scanner");

        // 1. Altera as cores para vermelho (Alerta visual sem travar a tela)
        cardScanner.style.backgroundColor = "#450a0a"; 
        cardScanner.style.borderColor = "var(--accent-rose)";
        
        // 2. Atualiza o texto de status superior com o nome do produto
        statusScanner.innerText = `[ALERTA: PRODUTO '${item.nome_produto.toUpperCase()}' ESTÁ SEM PREÇO]`;
        statusScanner.style.color = "var(--accent-rose)";

        // 3. Devolve o código do produto rejeitado para o visor
        inputScanner.value = item.id_produto || "";

        // 4. DIRECIONA O FOCO AUTOMATICAMENTE PARA O CAMPO DE PREÇO
        inputPreco.focus();
        inputPreco.setSelectionRange(inputPreco.value.length, inputPreco.value.length);

        // Remove o último registro inválido da memória local para limpar a fila
        carrinhoLocal.pop();

        // 5. EVENTO DE LIMPEZA: Restaura as cores originais assim que o operador interagir
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


    // 3. Atualiza os Visores de Totais Acumulados
    document.getElementById("visor-total").innerText = `R$ ${dados.resumo.vNF.toFixed(2)}`;
    document.getElementById("resumo-ibs").innerText = `R$ ${dados.resumo.vIBS_Total.toFixed(2)}`;
    document.getElementById("resumo-cbs").innerText = `R$ ${dados.resumo.vCBS_Total.toFixed(2)}`;

    // 4. Renderiza o Rodapé do Cupom (Matriz de Impostos do IBPT e IVA)
        // 4. Renderiza o Rodapé do Cupom (Matriz de Impostos do IBPT e IVA Compactada com Foco no Total)
    cupomRodape.classList.remove("hidden");
    cupomRodape.innerHTML = `
        <!-- TOTAL EM NEGRITO DESTACADO -->
        <div style="display: flex; justify-content: space-between; font-weight: bold; font-size: 13px; color: #000; border-bottom: 1px dashed #78350f; padding-bottom: 4px; margin-bottom: 4px;">
            <span>TOTAL R$</span>
            <span>${dados.resumo.vNF.toFixed(2)}</span>
        </div>
        
        <!-- ÁREA MINI/COMPACTA DE TRIBUTOS SECUNDÁRIOS -->
        <div style="font-size: 9px; color: #4b5563; display: flex; flex-direction: column; gap: 1px;">
            <p style="font-weight: bold; color: #1e293b;">TRIBUTOS REFORMA (IVA DUAL LC 214/2025)</p>
            <div style="display: flex; justify-content: space-between; padding-left: 4px;">
                <span>* TOTAL IBS CALCULADO:</span>
                <span>R$ ${dados.resumo.vIBS_Total.toFixed(2)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding-left: 4px;">
                <span>* TOTAL CBS CALCULADO:</span>
                <span>R$ ${dados.resumo.vCBS_Total.toFixed(2)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-weight: bold; color: #1e293b; border-top: 1px dotted #cbd5e1; padding-top: 1px; margin-top: 1px;">
                <span>CARGA TRIBUTÁRIA REAL:</span>
                <span>R$ ${(dados.resumo.vIBS_Total + dados.resumo.vCBS_Total).toFixed(2)}</span>
            </div>
            
            <p style="font-weight: bold; color: #1e293b; border-top: 1px dashed #78350f; padding-top: 3px; margin-top: 2px;">FONTE DO IMPOSTO APROXIMADO (IBPT)</p>
            <div style="display: flex; justify-content: space-between; padding-left: 4px;">
                <span>* Fed: R$ ${dados.resumo.ibpt_total_fed.toFixed(2)} | Est: R$ ${dados.resumo.ibpt_total_est.toFixed(2)}</span>
                <span style="font-weight: bold;">R$ ${dados.resumo.vTotTrib.toFixed(2)}</span>
            </div>
        </div>
    `;
}
// NOVA FUNÇÃO: CANCELAMENTO ATÔMICO DE UM ITEM DO CUPOM
function cancelarItemEspecifico() {
    if (carrinhoLocal.length === 0) {
        alert("O carrinho está vazio. Não há itens para cancelar.");
        return;
    }

    // Solicita o número do item (ex: 1, 2, 3...) de forma ágil pelo teclado
    const numeroItemTexto = prompt("Digite o número do ITEM que deseja cancelar (ex: 001):");
    
    if (!numeroItemTexto) return;

    // Converte para inteiro (ex: "002" vira 2)
    const indexParaRemover = parseInt(numeroItemTexto, 10) - 1;

    // Valida se o índice informado existe na matriz do carrinho atual
    if (isNaN(indexParaRemover) || indexParaRemover < 0 || indexParaRemover >= carrinhoLocal.length) {
        alert("Número de item inválido ou não localizado no cupom atual.");
        return;
    }

    // Confirmação rápida de segurança com os dados do item
    if (confirm(`Confirma o cancelamento do ITEM ${numeroItemTexto}?`)) {
        // Remove cirurgicamente o item do array sem quebrar o resto do lote
        carrinhoLocal.splice(indexParaRemover, 1);
        
        // Dispara a recontagem do lote e do IVA Dual na SEFAZ retaguarda
        atualizarCupomNaTela();
        
        alert(`ITEM ${numeroItemTexto} cancelado com sucesso.`);
    }
}

function cancelarCupomAtual() {
    if (confirm("Deseja realmente cancelar o cupom atual e limpar o carrinho?")) {
        carrinhoLocal = [];
        limparExibicaoTelas();
    }
}

function limparExibicaoTelas() {
    carrinhoLocal = [];
    document.getElementById("tabela-carrinho").innerHTML = "";
    // Restaura a estrutura de scroll limpa com o aviso inicial
    document.getElementById("cupom-linhas").innerHTML = `<div style="text-align: center; color: #64748b; padding-top: 24px; font-style: italic;" id="cupom-vazio-msg">Nenhum item faturado ate o momento.</div>`;
    document.getElementById("cupom-rodape").classList.add("hidden");
    document.getElementById("monitor-item").classList.add("hidden");
    document.getElementById("visor-total").innerText = "R$ 0,00";
    document.getElementById("resumo-ibs").innerText = "R$ 0,00";
    document.getElementById("resumo-cbs").innerText = "R$ 0,00";
}

// ATUALIZE A SUA FUNÇÃO EXISTENTE POR ESTA VERSÃO
async function finalizarFaturamentoCupom() {
    if (carrinhoLocal.length === 0) return;
    
    try {
        // 1. Faz a chamada regular de faturamento e baixa de estoque
        const respostaCalculo = await fetch(`${API_URL}/caixa/calcular-cupom`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ codigos_scaneados: carrinhoLocal })
        });
        const dados = await respostaCalculo.json();
        //println("retornou "+dados);
        // 2. Prepara a lista simplificada de produtos mapeados com seus valores para enviar para a rota do XML
        const produtosMapeados = dados.itens_aprovados.map(item => ({
            id_produto: item.id_produto,
            valor_venda: item.vProd
        }));

        const numNota = 40563; // Número hipotético simulado de cupom
        //alert("nota ="+numNota+produtosMapeados);
        // 3. Chamada assíncrona dedicada para obter a string XML completa do documento fiscal
        const respostaXML = await fetch(`${API_URL}/caixa/gerar-xml-nota`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                numero_nota: numNota,
                produtos: produtosMapeados
            })
        });

        const xmlTexto = await respostaXML.text();

        // 4. MÁGICA DO PWA: Cria um link de download em memória (Blob) e aciona o download silencioso no navegador
        const blob = new Blob([xmlTexto], { type: "application/xml" });
        const urlDownload = window.URL.createObjectURL(blob);
        const linkFalso = document.createElement("a");
        
        linkFalso.href = urlDownload;
        linkFalso.download = `conferencia_nota_${numNota}.xml`;
        document.body.appendChild(linkFalso);
        linkFalso.click(); // Dispara o clique invisível de download
        document.body.removeChild(linkFalso);
        window.URL.revokeObjectURL(urlDownload);
        
        alert(`[NFC-e Homologada!]\nEstoque baixado na tabela mestre e arquivo XML enviado automaticamente para a pasta de Downloads.`);
        limparExibicaoTelas();
        
    } catch (e) {
        console.error(e);
        alert("Falha ao encerrar o lote fiscal e exportar o XML.");
    }
}


// =========================================================================
// 3. OPERAÇÕES ADMINISTRATIVAS (RETAGUARDA DO GERENTE)
// =========================================================================

// =========================================================================
// 3. OPERAÇÕES ADMINISTRATIVAS (RETAGUARDA DO GERENTE - DADOS REAIS DO BANCO)
// =========================================================================

async function executarCargaMockMySQL() {
    // READEQUAÇÃO DE PRODUÇÃO: Remove os dados locais e avisa o operador
    alert("[Aviso]: O sistema está configurado no modo de Produção Fria. Os dados já residem de forma definitiva na tabela produtos do SQLite local.");
}

async function executarSincronizacaoMatriz() {
    try {
        // Dispara o comando SQL de UPDATE relacional em lote baseado no NCM real das tabelas
        const res = await fetch(`${API_URL}/retaguarda/matriz/sincronizar`, { method: "POST" });
        const data = await res.json();
        alert(`[Sincronizador Real]: ${data.mensagem}`);
    } catch (e) {
        alert("Erro na rotina relacional de sincronização.");
    }
}

async function carregarRelatorioInconsistencias() {
    try {
        // Roda a varredura viva cruzando os dados reais inseridos na tabela mestre
        const res = await fetch(`${API_URL}/auditoria/inconsistencias`);
        const data = await res.json();
        
        const container = document.getElementById("container-auditoria");
        container.innerHTML = "";

        if (data.inconsistencias.length === 0) {
            container.innerHTML = `<p class="p-4 text-center text-green-600 font-bold">[✓] Cadastro Mestre Higienizado. Nenhuma inconsistência fiscal ou comercial detectada na base física!</p>`;
            return;
        }

        data.inconsistencias.forEach((err) => {
            container.innerHTML += `
                <div class="p-3 bg-red-50/50 flex flex-col gap-1 border-b border-red-100">
                    <div class="flex justify-between font-bold text-red-900">
                        <span>ID: ${err.id_produto} | ${err.nome_produto}</span>
                        <span class="bg-red-200 text-red-800 px-2 py-0.5 rounded text-xs font-sans tracking-wide">${err.tipo_inconsistencia}</span>
                    </div>
                    <p class="text-xs text-gray-500">NCM cadastrado: ${err.ncm} | Diagnóstico: ${err.detalhe_erro}</p>
                </div>
            `;
        });
    } catch (e) {
        alert("Erro ao puxar dados vivos do Módulo de Auditoria.");
    }
}
// 5. CONTROLE DO MODAL DE AJUDA E ARQUITETURA
function abrirModalAjuda() {
    const modal = document.getElementById("modal-ajuda");
    modal.classList.remove("hidden");
}

function fecharModalAjuda() {
    const modal = document.getElementById("modal-ajuda");
    modal.classList.add("hidden");
}

// Fecha o modal se o usuário clicar na área escura de fora dele
window.onclick = function(event) {
    const modal = document.getElementById("modal-ajuda");
    if (event.target === modal) {
        fecharModalAjuda();
    }
};

// 4. PROTOCOLO AUXILIAR DE STRING (Nativo do pad do Cupom)
String.prototype.zfill = function(size) {
    let s = this;
    while (s.length < (size || 2)) {s = "0" + s;}
    return s;
};

// Vincula a tecla Enter do campo de scanner ao faturamento automático do item
document.getElementById("input-scanner").addEventListener("keypress", function(e) {
    if (e.key === "Enter") registrarItemCarrinho();
});
// Captura e formatação em tempo real das casas decimais
function aplicarMascaraDecimal(input, casasDecimais) {
    input.addEventListener("input", function(e) {
        // Remove tudo que não for dígito numérico
        let digits = this.value.replace(/\D/g, "");
        if (!digits) digits = "0";
        
        let valorNumerico = parseInt(digits, 10);
        let divisor = Math.pow(10, casasDecimais);
        let resultado = valorNumerico / divisor;
        
        // Formata com a quantidade exata de casas decimais usando o padrão brasileiro
        this.value = resultado.toLocaleString("pt-BR", {
            minimumFractionDigits: casasDecimais,
            maximumFractionDigits: casasDecimais
        });
    });

    // Limpa a seleção e foca no final do texto ao clicar
    input.addEventListener("focus", function() {
        setTimeout(() => { this.setSelectionRange(this.value.length, this.value.length); }, 10);
    });
}

// Ativa as máscaras automáticas nos campos criados
aplicarMascaraDecimal(document.getElementById("input-quantidade"), 3); // 3 Casas: 1,000
aplicarMascaraDecimal(document.getElementById("input-preco-manual"), 2); // 2 Casas: 0,00

// INTERCEPTADOR DE ATALHOS DE TECLADO (F1, F2 e F9)
// CORREÇÃO DOS ATALHOS GLOBAIS DE TECLADO (Substitua a sua escuta anterior do F5)
window.addEventListener("keydown", function(e) {
    if (e.key === "F1") {
        e.preventDefault();
        const campoPreco = document.getElementById("input-preco-manual");
        campoPreco.focus();
        campoPreco.setSelectionRange(campoPreco.value.length, campoPreco.value.length);
    }
    if (e.key === "F2") {
        e.preventDefault();
        const campoQtd = document.getElementById("input-quantidade");
        campoQtd.focus();
        campoQtd.setSelectionRange(campoQtd.value.length, campoQtd.value.length);
    }
    if (e.key === "F5") {
        e.preventDefault();
        cancelarItemEspecifico(); // Alterado de limparExibicaoTelas para a nova função
    }
    if (e.key === "F6") {
        e.preventDefault();
        cancelarCupomAtual();
    }
    if (e.key === "F8") {
        e.preventDefault();
        finalizarFaturamentoCupom();
    }
    if (e.key === "F9") {
        e.preventDefault();
        document.getElementById("input-scanner").focus();
    }
});

// VINCULA A TECLA ENTER DO CAMPO DE PREÇO AO FATURAMENTO DE CONTINGÊNCIA
document.getElementById("input-preco-manual").addEventListener("keypress", function(e) {
    if (e.key === "Enter") {
        const inputScanner = document.getElementById("input-scanner");
        const precoTexto = this.value.trim();

        // Só executa o faturamento se houver um código de produto na tela e o preço for maior que zero
        if (inputScanner.value.trim() !== "" && precoTexto !== "0,00") {
            e.preventDefault(); // Impede comportamentos indesejados do formulário
            
            // Dispara a mesma função de registro, que agora lê a contingência automaticamente
            registrarItemCarrinho();
        }
    }
});
