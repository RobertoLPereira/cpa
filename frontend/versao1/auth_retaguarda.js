// Salve este arquivo como auth_retaguarda.js

let terminalAtivo = { codigo: "CAIXA-01", serie: "1" };
const API_URL = "http://localhost:8000/api/v1";

document.addEventListener("DOMContentLoaded", async () => {
    injetarTelaLogin();
    injetarDrawerRetaguarda();

    const infoEl = document.getElementById("login-loja-info");
    const sel = document.getElementById("login-terminal");

    try {
        const res = await fetch(`${API_URL}/auth/config-login`);
        if (res.ok) {
            const cfg = await res.json();

            // Preenche a lista de terminais vindos do .env (TOTAL_CAIXAS_LOJA)
            sel.innerHTML = cfg.terminais.map(t =>
                `<option value="${t.codigo}" data-serie="${t.serie}">${t.label}</option>`
            ).join("");

            if (cfg.emitente) {
                infoEl.innerText = `${cfg.emitente.razao} • CNPJ: ${cfg.emitente.cnpj}`;
                infoEl.style.color = "#94a3b8";
                if (typeof atualizarTextoLojaNoDOM === "function") {
                    atualizarTextoLojaNoDOM(cfg.emitente.razao, cfg.emitente.cnpj);
                }
            } else {
                infoEl.innerText = "Sistema não inicializado • Acesso restrito ao Administrador/Suporte";
                infoEl.style.color = "#fbbf24";
                // Seleciona RETAGUARDA automaticamente quando o banco ainda está vazio
                sel.value = "RETAGUARDA";
            }
        } else {
            const err = await res.json();
            infoEl.innerText = err.detail || "Erro ao carregar configurações da loja.";
            infoEl.style.color = "#f43f5e";
        }
    } catch {
        infoEl.innerText = "Servidor offline • Modo Contingência Local";
        infoEl.style.color = "#fbbf24";
        sel.innerHTML = `<option value="CAIXA-01" data-serie="1">Caixa 01 (Contingência)</option>
        <option value="Suporte" data-serie="1">Suporte</option>
        <option value="Gerente" data-serie="1">Gerente</option>
        <option value="Admin" data-serie="1">Admin</option>`;
    }

    const inpUser = document.getElementById("login-usuario");
    const inpGrupo = document.getElementById("login-grupo");
    const inpSenha = document.getElementById("login-senha");

    inpUser.addEventListener("keydown", e => { if (e.key === "Enter") inpGrupo.focus(); });
    inpGrupo.addEventListener("keydown", e => { if (e.key === "Enter") inpSenha.focus(); });
    inpSenha.addEventListener("keydown", e => { if (e.key === "Enter") validarLoginOperador(); });
    inpUser.focus();
});

function injetarTelaLogin() {
    const htmlLogin = `
    <div id="overlay-login-cpa" style="position:fixed;inset:0;background:rgba(2,6,23,0.97);display:flex;align-items:center;justify-content:center;z-index:9999;font-family:sans-serif;">
        <div style="background:#0f172a;border:1px solid #334155;padding:32px;border-radius:12px;width:400px;color:#f8fafc;box-shadow:0 20px 40px rgba(0,0,0,0.6);">
            <h2 style="margin:0;text-align:center;color:#38bdf8;font-size:20px;font-weight:bold;">Acesso ao Sistema PDV</h2>
            <p id="login-loja-info" style="text-align:center;color:#94a3b8;font-size:11px;margin:6px 0 18px 0;">Carregando loja...</p>
            
            <div id="login-msg-erro" style="display:none;background:#450a0a;border:1px solid #e11d48;color:#fecdd3;padding:10px;border-radius:6px;font-size:12px;margin-bottom:14px;font-weight:bold;"></div>

            <label style="display:block;font-size:12px;color:#cbd5e1;margin-bottom:4px;">Terminal / Caixa</label>
            <select id="login-terminal" style="width:100%;padding:9px;margin-bottom:12px;border-radius:6px;background:#1e293b;border:1px solid #475569;color:#fff;font-size:13px;"></select>

            <label style="display:block;font-size:12px;color:#cbd5e1;margin-bottom:4px;">Nome do Usuário</label>
            <input id="login-usuario" type="text" autocomplete="off" style="width:100%;padding:9px;margin-bottom:12px;border-radius:6px;background:#1e293b;border:1px solid #475569;color:#fff;font-size:13px;box-sizing:border-box;">

            <label style="display:block;font-size:12px;color:#cbd5e1;margin-bottom:4px;">Grupo</label>
            <input id="login-grupo" type="text" autocomplete="off" style="width:100%;padding:9px;margin-bottom:12px;border-radius:6px;background:#1e293b;border:1px solid #475569;color:#fff;font-size:13px;box-sizing:border-box;">

            <label style="display:block;font-size:12px;color:#cbd5e1;margin-bottom:4px;">Senha</label>
            <input id="login-senha" type="password" style="width:100%;padding:9px;margin-bottom:18px;border-radius:6px;background:#1e293b;border:1px solid #475569;color:#fff;font-size:13px;box-sizing:border-box;">

            <button onclick="validarLoginOperador()" style="width:100%;padding:11px;background:#0284c7;color:#fff;border:none;border-radius:6px;font-weight:bold;font-size:14px;cursor:pointer;">
                EFETUAR LOGIN (ENTER)
            </button>
        </div>
    </div>`;
    document.body.insertAdjacentHTML("beforeend", htmlLogin);
}

function injetarDrawerRetaguarda() {
    const htmlDrawer = `
    <button id="btn-abrir-retaguarda" onclick="toggleDrawerRetaguarda()" style="display:none;position:fixed;bottom:14px;left:14px;z-index:9000;background:#0284c7;color:#fff;border:none;padding:8px 14px;border-radius:6px;font-weight:bold;font-size:12px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.4);">
        ☰ Menu Retaguarda
    </button>
    <div id="drawer-retaguarda" style="display:none;position:fixed;top:0;left:0;bottom:0;width:260px;background:#090d16;border-right:1px solid #1e293b;color:#f1f5f9;z-index:9500;padding:16px;overflow-y:auto;font-family:sans-serif;box-shadow:6px 0 20px rgba(0,0,0,0.6);">
        <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1e293b;padding-bottom:10px;margin-bottom:12px;">
            <strong style="color:#38bdf8;font-size:15px;">Menu Retaguarda</strong>
            <button onclick="toggleDrawerRetaguarda()" style="background:none;border:none;color:#94a3b8;font-size:16px;cursor:pointer;">✕</button>
        </div>
        <div style="font-size:12px;line-height:2;">
            <div style="color:#38bdf8;font-weight:bold;margin-top:6px;">📁 Cadastros</div>
            <div style="padding-left:10px;color:#cbd5e1;">• Clientes / Destinatários<br>• Produtos & Tributação<br>• Cod. Fiscal Operação<br>• Formas de Pagto<br>• Cidades (IBGE)</div>
            <div style="color:#38bdf8;font-weight:bold;margin-top:10px;">🔄 Movimentações</div>
            <div style="padding-left:10px;color:#cbd5e1;">• Cancelamento de NF-e/NFC-e<br>• Devolução Total da NFe<br>• Importa NFe de Compra</div>
            <div style="color:#38bdf8;font-weight:bold;margin-top:10px;">📊 Relatórios</div>
            <div style="padding-left:10px;color:#cbd5e1;">• Movimento no Período<br>• Recebimento no Período</div>
            <div style="color:#38bdf8;font-weight:bold;margin-top:10px;">⚙ Administração</div>
            <div style="padding-left:10px;color:#cbd5e1;">• Dados do Emitente<br>• Usuários<br>• Posição Caixa<br>• Numeração NF-e/NFC-e</div>
        </div>
    </div>`;
    document.body.insertAdjacentHTML("beforeend", htmlDrawer);
}

function toggleDrawerRetaguarda() {
    const d = document.getElementById("drawer-retaguarda");
    const estaOculto = d.style.display === "none";
    d.style.display = estaOculto ? "block" : "none";
    document.body.style.paddingLeft = estaOculto ? "260px" : "0px";
}

async function validarLoginOperador() {
    const inpUser = document.getElementById("login-usuario");
    const inpGrupo = document.getElementById("login-grupo");
    const inpSenha = document.getElementById("login-senha");
    const selTerm = document.getElementById("login-terminal");
    const boxErro = document.getElementById("login-msg-erro");

    [inpUser, inpGrupo, inpSenha].forEach(el => el.style.borderColor = "#475569");
    boxErro.style.display = "none";

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
            boxErro.innerText = det.mensagem || "Falha na validação do login.";
            boxErro.style.display = "block";
            const campos = { usua_nome: inpUser, grupo: inpGrupo, usua_senha: inpSenha };
            if (campos[det.campo]) {
                campos[det.campo].style.borderColor = "#e11d48";
                campos[det.campo].focus();
            }
            return;
        }

        operadorAtivo = data.operador;
        const opt = selTerm.options[selTerm.selectedIndex];
        terminalAtivo = {
            codigo: selTerm.value || "CAIXA-01",
            serie: opt ? opt.getAttribute("data-serie") : "1"
        };

        document.getElementById("overlay-login-cpa").style.display = "none";

        const ehGrupoCaixa = (operadorAtivo.grupo_geral || "").trim().toUpperCase() === "CAIXA";

        // 1. Controla a visibilidade da área e dos cards do PDV (visível SOMENTE para grupo CAIXA)
        const areaPdv = document.getElementById("aba-caixa");
        if (areaPdv) {
            if (ehGrupoCaixa) {
                areaPdv.style.removeProperty("display");
            } else {
                areaPdv.style.setProperty("display", "none", "important");
            }
        }

        document.querySelectorAll(".scanner-card, #tabela-carrinho, #cupom-linhas, #visor-total").forEach(el => {
            const alvo = el.closest("section, .card, .grid > div") || el;
            if (alvo && alvo.id !== "overlay-login-cpa" && alvo.id !== "drawer-retaguarda") {
                alvo.style.setProperty("display", ehGrupoCaixa ? "" : "none", "important");
            }
        });
        // 2. Oculta botões de operação de venda (F1 a F9) para NÃO-CAIXA, mantendo "F10 Sair"
        document.querySelectorAll("button").forEach(btn => {
            const txt = (btn.textContent || "").toUpperCase();
            const ehAtalhoVenda = ["F1 ", "F2 ", "F4 ", "F5 ", "F6 ", "F8 ", "F9 ", "CANCELAR ITEM", "CANC. VENDA", "FINALIZAR VENDA", "FOCAR SCANNER"]
            .some(termo => txt.includes(termo));
            if (ehAtalhoVenda) {
                btn.style.setProperty("display", ehGrupoCaixa ? "inline-flex" : "none", "important");
            }
        });
        // 3. Controla botões e painéis de Gerente / Retaguarda (visíveis SOMENTE para NÃO-CAIXA)
        ["btn-gerente", "aba-gerente", "btn-abrir-retaguarda", "drawer-retaguarda"].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            if (ehGrupoCaixa) {
                el.style.setProperty("display", "none", "important");
            } else {
                el.style.removeProperty("display");
                if (id === "btn-gerente" || id === "btn-abrir-retaguarda") {
                    el.style.setProperty("display", "inline-block", "important");
                }
                if (id === "drawer-retaguarda") {
                    el.style.setProperty("display", "block", "important");
                }
            }
        }
        });
        // 4. Ajusta a margem esquerda da página para o Menu Retaguarda (260px) não sobrepor os textos
        document.body.style.paddingLeft = ehGrupoCaixa ? "0px" : "260px";
        // 5. Varre botões/textos da interface para garantir a separação dos perfis
        document.querySelectorAll("button, a, span, div, section").forEach(el => {
        const txt = (el.textContent || "").trim().toUpperCase();
        // Oculta botões de Gerente/Retaguarda para o Caixa
        if (el.children.length <= 2 && (txt.includes("PAINEL GERENTE") || txt.includes("MENU RETAGUARDA"))) {
            el.style.setProperty("display", ehGrupoCaixa ? "none" : "inline-block", "important");
        }
        // Oculta o bloco "Administração Fiscal Retaguarda" para o Caixa e exibe para os demais
        if (txt.startsWith("ADMINISTRAÇÃO FISCAL RETAGUARDA") && el.children.length <= 6) {
            el.style.setProperty("display", ehGrupoCaixa ? "none" : "block", "important");
        }
        });
        // 6. Foca no scanner apenas se for Caixa
        if (ehGrupoCaixa) {
            const scanner = document.getElementById("input-scanner");
            if (scanner) scanner.focus();
        }
        } catch {
            boxErro.innerText = "Erro de conexão com o backend Python.";
            boxErro.style.display = "block";
        }
    }
function fazerLogoff() {
    // 1. Impede sair acidentalmente se houver venda em andamento no Caixa
    if (typeof carrinhoLocal !== "undefined" && carrinhoLocal.length > 0) {
        if (!confirm("Há itens abertos no carrinho. Deseja realmente sair?")) return;
    }

    // 2. Limpa a tela do PDV se a função existir no script principal
    if (typeof limparExibicaoTelas === "function") {
        limparExibicaoTelas();
    }

    // 3. Reseta o operador ativo
    operadorAtivo = null;

    // 4. Fecha o drawer da retaguarda, oculta o botão flutuante e remove o recuo da tela
    const drawer = document.getElementById("drawer-retaguarda");
    const btnRet = document.getElementById("btn-abrir-retaguarda");
    if (drawer) drawer.style.display = "none";
    if (btnRet) btnRet.style.display = "none";
    document.body.style.paddingLeft = "0px";

    // 5. Limpa o campo de senha e reabre o overlay de login
    const inpSenha = document.getElementById("login-senha");
    const boxErro = document.getElementById("login-msg-erro");
    const overlay = document.getElementById("overlay-login-cpa");

    if (inpSenha) inpSenha.value = "";
    if (boxErro) boxErro.style.display = "none";
    if (overlay) {
        overlay.style.display = "flex";
        const inpUser = document.getElementById("login-usuario");
        if (inpUser) inpUser.focus();
    }
}

// Garante que o atalho F10 funcione independentemente do perfil logado (Caixa ou Retaguarda)
window.addEventListener("keydown", function (e) {
    if (e.key === "F10" && operadorAtivo) {
        e.preventDefault();
        fazerLogoff();
    }
}, true);
