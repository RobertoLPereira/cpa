// ==========================================================================
// RETAGUARDA/PRODUTOS.JS - CRUD de Produtos & Tributação (ICMS / IBS / CBS)
// ==========================================================================
import { formatarMoeda } from "../state.js";

function getApiRetaguarda() {
  return typeof API_URL !== "undefined" ? `${API_URL}/retaguarda/produtos` : "http://localhost:8000/api/v1/retaguarda/produtos";
}

let filtroAtual = "TODOS";
let listaCache = [];
let timerBuscaRetaguarda = null;
export async function abrirCadastroProdutos() {
  const container = document.getElementById("view-modulo-retaguarda");
  if (!container) return;

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #cbd5e1; padding-bottom:10px; margin-bottom:12px;">
      <div>
        <h3 style="color:var(--cor-secundaria); font-size:18px; margin:0;">CADASTRO DE PRODUTOS &amp; TRIBUTAÇÃO</h3>
        <span style="font-size:11px; color:#475569;">Gerenciamento comercial, fiscal atual (ICMS/PIS/COFINS) e Reforma Tributária (IBS/CBS)</span>
      </div>
      <button onclick="window.retProdutos.abrirFormulario(null)" class="btn-pdv" style="height:36px; padding:0 16px; font-size:12px; color:#006600;">
        + NOVO PRODUTO
      </button>
    </div>

    <!-- Barra de Busca e Filtros de Auditoria -->
    <div style="display:flex; gap:8px; align-items:center; margin-bottom:10px; flex-wrap:wrap;">
      <input id="ret-prod-busca" type="text" placeholder="Pesquisar por descrição, código interno, EAN ou NCM..."
             style="flex:1; min-width:240px; height:32px; padding:0 10px; border:2px inset #808080; background:#ffff99; font-weight:bold; color:#000080;" />
      <button onclick="window.retProdutos.buscar()" class="btn-pdv" style="height:32px; padding:0 14px;">Pesquisar</button>
      <button onclick="window.retProdutos.filtrar('TODOS')" class="btn-pdv" style="height:32px;">Todos</button>
      <button onclick="window.retProdutos.filtrar('SEM_PRECO')" class="btn-pdv" style="height:32px; color:#cc0000;">Preço Zerado</button>
      <button onclick="window.retProdutos.filtrar('SEM_IBSCBS')" class="btn-pdv" style="height:32px; color:#b45309;">Sem IBS/CBS</button>
    </div>

    <!-- Tabela de Produtos -->
    <div style="border:2px inset #808080; max-height:calc(100vh - 245px); overflow-y:auto; background:#fff;">
      <table class="tabela-produtos">
        <thead>
          <tr>
            <th style="width:80px;">Cód.</th>
            <th style="width:125px;">EAN</th>
            <th>Descrição (xProd)</th>
            <th style="width:85px;">NCM</th>
            <th style="width:55px;">CFOP</th>
            <th style="width:45px; text-align:center;">Unid</th>
            <th style="width:95px; text-align:right;">Preço (R$)</th>
            <th style="width:75px; text-align:center;">IBS/CBS</th>
            <th style="width:110px; text-align:center;">Ações</th>
          </tr>
        </thead>
        <tbody id="ret-tbody-produtos">
          <tr><td colspan="9" style="text-align:center; padding:20px;">Carregando produtos...</td></tr>
        </tbody>
      </table>
    </div>
  `;

  const inputBusca = document.getElementById("ret-prod-busca");

  inputBusca.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      clearTimeout(timerBuscaRetaguarda);
      buscarProdutosRetaguarda();
    }
  });

  inputBusca.addEventListener("input", (e) => {
    clearTimeout(timerBuscaRetaguarda);
    const termo = e.target.value.trim();

    // Dispara a busca a partir do 3º caractere ou se o usuário limpar o campo
    if (termo.length >= 3 || termo.length === 0) {
      timerBuscaRetaguarda = setTimeout(() => {
        buscarProdutosRetaguarda();
      }, 250);
    }
  });

  await buscarProdutosRetaguarda();
}

export async function filtrarProdutosRetaguarda(novoFiltro) {
  filtroAtual = novoFiltro;
  await buscarProdutosRetaguarda();
}

export async function buscarProdutosRetaguarda() {
  const termo = document.getElementById("ret-prod-busca")?.value || "";
  const tbody = document.getElementById("ret-tbody-produtos");
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:16px;">Consultando banco de dados...</td></tr>`;

  try {
    const params = new URLSearchParams({ q: termo, filtro: filtroAtual });
    const resp = await fetch(`${getApiRetaguarda()}?${params.toString()}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Erro ao listar produtos.");

    listaCache = data.produtos || [];
    if (listaCache.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:20px; color:#666;">Nenhum produto encontrado.</td></tr>`;
      return;
    }

    tbody.innerHTML = listaCache.map((p) => {
      const preco = Number(p.vuncom || 0);
      const corPreco = preco <= 0 ? "color:#cc0000;" : "color:#000080;";
      const statusIva = p.ibscbs_cst
        ? `<span style="color:#16a34a;">CST ${p.ibscbs_cst}</span>`
        : `<span style="color:#b45309;">Pendente</span>`;

      return `
        <tr>
          <td>${p.cprod}</td>
          <td>${p.cean || "SEM GTIN"}</td>
          <td>${p.xprod}</td>
          <td>${p.ncm}</td>
          <td>${p.cfop_padrao}</td>
          <td style="text-align:center;">${p.ucom}</td>
          <td style="text-align:right; ${corPreco}">${formatarMoeda(preco)}</td>
          <td style="text-align:center;">${statusIva}</td>
          <td style="text-align:center;">
            <button onclick="window.retProdutos.abrirFormulario('${p.id}')" class="btn-pdv" style="padding:2px 6px;">Editar</button>
            <button onclick="window.retProdutos.excluir('${p.id}', '${p.xprod.replace(/'/g, "")}')" class="btn-pdv" style="padding:2px 6px; color:#cc0000;">X</button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:16px; color:#cc0000;">${e.message}</td></tr>`;
  }
}

export async function excluirProdutoRetaguarda(id, nome) {
  if (!confirm(`Deseja realmente excluir o produto "${nome}"?`)) return;
  try {
    const resp = await fetch(`${getApiRetaguarda()}/${id}`, { method: "DELETE" });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Erro ao excluir.");
    alert(data.mensagem);
    await buscarProdutosRetaguarda();
  } catch (e) {
    alert("Falha ao excluir: " + e.message);
  }
}
// ==========================================================================
// PARTE 2 - FORMULÁRIO EM 3 ABAS (Dados Gerais | Fiscal Atual | IBS/CBS)
// ==========================================================================

export async function abrirFormularioProduto(produtoId = null) {
  let p = {
    cprod: "", cean: "", xprod: "", ucom: "UN", vuncom: "0.00",
    utrib: "UN", vuntrib: "0.00", ceantrib: "", fator_conversao: "1.0000", estoque_atual: "0.0000",
    ncm: "", cest: "", cbenef: "", cfop_padrao: "5102", ind_monofasico: 0,
    icms_orig: "0", icms_cst: "102", icms_picms: "0.00",
    pis_cst: "49", pis_ppis: "0.00", cofins_cst: "49", cofins_pcofins: "0.00",
    ibpt_fed: "0.00", ibpt_est: "0.00",
    ibscbs_cst: "000", ibscbs_cclasstrib: "", ibs_pibsuf: "0.00", cbs_pcbs: "0.00"
  };

  if (produtoId) {
    try {
      const resp = await fetch(`${getApiRetaguarda()}/${produtoId}`);
      if (resp.ok) p = await resp.json();
    } catch (e) {
      return alert("Erro ao carregar produto: " + e.message);
    }
  }

  const container = document.getElementById("view-modulo-retaguarda");
  const estiloInput = "width:100%; height:30px; padding:0 6px; border:1px inset #808080; font-weight:bold;";
  const estiloLabel = "display:block; font-size:11px; font-weight:bold; color:var(--cor-primaria); margin-bottom:2px;";

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #cbd5e1; padding-bottom:8px; margin-bottom:12px;">
      <h3 style="color:var(--cor-secundaria); margin:0;">${produtoId ? "EDITAR PRODUTO" : "NOVO PRODUTO"}</h3>
      <button onclick="window.retProdutos.abrirLista()" class="btn-pdv" style="height:32px; padding:0 14px;">← Voltar para Lista</button>
    </div>

    <!-- Botões das 3 Abas -->
    <div style="display:flex; gap:6px; margin-bottom:12px;">
      <button type="button" onclick="window.retProdutos.trocarAba(1)" id="tab-btn-1" class="btn-pdv" style="height:34px; padding:0 16px; background:#ffff99;">1. Dados Gerais &amp; Preço</button>
      <button type="button" onclick="window.retProdutos.trocarAba(2)" id="tab-btn-2" class="btn-pdv" style="height:34px; padding:0 16px;">2. Fiscal (ICMS / PIS / COFINS / IBPT)</button>
      <button type="button" onclick="window.retProdutos.trocarAba(3)" id="tab-btn-3" class="btn-pdv" style="height:34px; padding:0 16px;">3. Reforma Tributária (IBS / CBS)</button>
    </div>

    <form id="form-produto-retaguarda" class="bevel-panel" style="padding:14px;">
      <!-- ABA 1: DADOS GERAIS -->
      <div id="tab-pane-1" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px;">
        <div><label style="${estiloLabel}">Código Interno (cProd)*</label><input name="cprod" value="${p.cprod || ""}" required style="${estiloInput} background:#ffff99;" /></div>
        <div><label style="${estiloLabel}">Código Barras (cEAN)</label><input name="cean" value="${p.cean || ""}" style="${estiloInput}" /></div>
        <div style="grid-column:span 2;"><label style="${estiloLabel}">Descrição do Produto (xProd)*</label><input name="xprod" value="${p.xprod || ""}" required style="${estiloInput} background:#ffff99; text-transform:uppercase;" /></div>

        <div><label style="${estiloLabel}">Unidade Com. (uCom)*</label><input name="ucom" value="${p.ucom || "UN"}" required style="${estiloInput}" /></div>
        <div><label style="${estiloLabel}">Preço Venda (vUnCom)*</label><input name="vuncom" type="number" step="0.01" value="${Number(p.vuncom || 0).toFixed(2)}" required style="${estiloInput} background:#ffff99; text-align:right;" /></div>
        <div><label style="${estiloLabel}">Estoque Atual</label><input name="estoque_atual" type="number" step="0.001" value="${Number(p.estoque_atual || 0).toFixed(3)}" style="${estiloInput} text-align:right;" /></div>
        <div><label style="${estiloLabel}">Fator Conversão</label><input name="fator_conversao" type="number" step="0.0001" value="${Number(p.fator_conversao || 1).toFixed(4)}" style="${estiloInput} text-align:right;" /></div>

        <div><label style="${estiloLabel}">Unidade Trib. (uTrib)</label><input name="utrib" value="${p.utrib || p.ucom || "UN"}" style="${estiloInput}" /></div>
        <div><label style="${estiloLabel}">Valor Unit. Trib. (vUnTrib)</label><input name="vuntrib" type="number" step="0.01" value="${Number(p.vuntrib || 0).toFixed(2)}" style="${estiloInput} text-align:right;" /></div>
        <div style="grid-column:span 2;"><label style="${estiloLabel}">EAN Tributável (cEANTrib)</label><input name="ceantrib" value="${p.ceantrib || ""}" style="${estiloInput}" /></div>
      </div>

      <!-- ABA 2: FISCAL ATUAL -->
      <div id="tab-pane-2" class="hidden" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px;">
        <div><label style="${estiloLabel}">NCM (8 dígitos)*</label><input name="ncm" maxlength="8" value="${p.ncm || ""}" required style="${estiloInput} background:#ffff99;" /></div>
        <div><label style="${estiloLabel}">CEST</label><input name="cest" maxlength="7" value="${p.cest || ""}" style="${estiloInput}" /></div>
        <div><label style="${estiloLabel}">CFOP Padrão*</label><input name="cfop_padrao" maxlength="4" value="${p.cfop_padrao || "5102"}" required style="${estiloInput} background:#ffff99;" /></div>
        <div><label style="${estiloLabel}">Cód. Benefício (cBenef)</label><input name="cbenef" value="${p.cbenef || ""}" style="${estiloInput}" /></div>

        <div><label style="${estiloLabel}">Origem (icms_orig)</label><input name="icms_orig" maxlength="1" value="${p.icms_orig || "0"}" style="${estiloInput}" /></div>
        <div><label style="${estiloLabel}">CST / CSOSN ICMS</label><input name="icms_cst" maxlength="3" value="${p.icms_cst || "102"}" style="${estiloInput}" /></div>
        <div><label style="${estiloLabel}">Alíquota ICMS (%)</label><input name="icms_picms" type="number" step="0.01" value="${Number(p.icms_picms || 0).toFixed(2)}" style="${estiloInput} text-align:right;" /></div>
        <div>
          <label style="${estiloLabel}">Monofásico PIS/COFINS?</label>
          <select name="ind_monofasico" style="${estiloInput}">
            <option value="0" ${Number(p.ind_monofasico) === 0 ? "selected" : ""}>0 - Não</option>
            <option value="1" ${Number(p.ind_monofasico) === 1 ? "selected" : ""}>1 - Sim (Monofásico)</option>
          </select>
        </div>

        <div><label style="${estiloLabel}">CST PIS</label><input name="pis_cst" maxlength="2" value="${p.pis_cst || "49"}" style="${estiloInput}" /></div>
        <div><label style="${estiloLabel}">Alíquota PIS (%)</label><input name="pis_ppis" type="number" step="0.01" value="${Number(p.pis_ppis || 0).toFixed(2)}" style="${estiloInput} text-align:right;" /></div>
        <div><label style="${estiloLabel}">CST COFINS</label><input name="cofins_cst" maxlength="2" value="${p.cofins_cst || "49"}" style="${estiloInput}" /></div>
        <div><label style="${estiloLabel}">Alíquota COFINS (%)</label><input name="cofins_pcofins" type="number" step="0.01" value="${Number(p.cofins_pcofins || 0).toFixed(2)}" style="${estiloInput} text-align:right;" /></div>

        <div><label style="${estiloLabel}">IBPT Federal (%)</label><input name="ibpt_fed" type="number" step="0.01" value="${Number(p.ibpt_fed || 0).toFixed(2)}" style="${estiloInput} text-align:right;" /></div>
        <div><label style="${estiloLabel}">IBPT Estadual (%)</label><input name="ibpt_est" type="number" step="0.01" value="${Number(p.ibpt_est || 0).toFixed(2)}" style="${estiloInput} text-align:right;" /></div>
      </div>

      <!-- ABA 3: REFORMA TRIBUTÁRIA (IBS / CBS) -->
      <div id="tab-pane-3" class="hidden" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px;">
        <div><label style="${estiloLabel}">CST IBS/CBS (ibscbs_cst)</label><input name="ibscbs_cst" maxlength="3" value="${p.ibscbs_cst || ""}" style="${estiloInput} background:#ffff99;" /></div>
        <div><label style="${estiloLabel}">Class. Tributária (cClassTrib)</label><input name="ibscbs_cclasstrib" maxlength="6" value="${p.ibscbs_cclasstrib || ""}" style="${estiloInput}" /></div>
        <div><label style="${estiloLabel}">Alíquota IBS UF (%)</label><input name="ibs_pibsuf" type="number" step="0.01" value="${Number(p.ibs_pibsuf || 0).toFixed(2)}" style="${estiloInput} text-align:right;" /></div>
        <div><label style="${estiloLabel}">Alíquota CBS (%)</label><input name="cbs_pcbs" type="number" step="0.01" value="${Number(p.cbs_pcbs || 0).toFixed(2)}" style="${estiloInput} text-align:right;" /></div>
      </div>

      <div style="margin-top:16px; display:flex; justify-content:flex-end; gap:10px; border-top:1px solid #cbd5e1; padding-top:12px;">
        <button type="button" onclick="window.retProdutos.abrirLista()" class="btn-pdv" style="height:36px; width:110px; color:#cc0000;">Cancelar</button>
        <button type="submit" class="btn-pdv" style="height:36px; width:160px; color:#006600; font-size:13px;">SALVAR PRODUTO</button>
      </div>
    </form>
  `;

  trocarAbaProduto(1);

  document.getElementById("form-produto-retaguarda").addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const payload = Object.fromEntries(formData.entries());
    payload.ind_monofasico = parseInt(payload.ind_monofasico || "0", 10);

    try {
      const url = produtoId ? `${getApiRetaguarda()}/${produtoId}` : getApiRetaguarda();
      const method = produtoId ? "PUT" : "POST";
      const resp = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const res = await resp.json();
      if (!resp.ok) throw new Error(res.detail || "Erro ao salvar produto.");

      alert(res.mensagem);
      await abrirCadastroProdutos();
    } catch (err) {
      alert("Erro ao salvar: " + err.message);
    }
});
}
export function trocarAbaProduto(numAba) {
    [1, 2, 3].forEach((n) => {
    const pane = document.getElementById(`tab-pane-${n}`);
    const btn = document.getElementById(`tab-btn-${n}`);
    if (pane) pane.classList.toggle("hidden", n !== numAba);
    if (btn) btn.style.background = n === numAba ? "#ffff99" : "";
  });
}
// Expõe no escopo global para os botões e o menu lateral da Retaguarda
window.retProdutos = {
    abrirLista: abrirCadastroProdutos,
    buscar: buscarProdutosRetaguarda,
    filtrar: filtrarProdutosRetaguarda,
    abrirFormulario: abrirFormularioProduto,
    excluir: excluirProdutoRetaguarda,
    trocarAba: trocarAbaProduto
};