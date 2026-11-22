// ==========================================================================
// RETAGUARDA/IMPORTA-NFE.JS - Importação de XML de Compra (Arquivo ou Pasta)
// ==========================================================================
import { formatarMoeda } from "../state.js";

function getUrlImportacao() {
  return typeof API_URL !== "undefined"
    ? `${API_URL}/retaguarda/importa-nfe/upload`
    : "http://localhost:8000/api/v1/retaguarda/importa-nfe/upload";
}

let arquivosSelecionados = [];

export function abrirImportaNFe() {
  arquivosSelecionados = [];
  const container = document.getElementById("view-modulo-retaguarda");
  if (!container) return;

  container.innerHTML = `
    <div style="border-bottom:2px solid #cbd5e1; padding-bottom:10px; margin-bottom:14px;">
      <h3 style="color:var(--cor-secundaria); font-size:18px; margin:0;">IMPORTAÇÃO DE NF-e DE COMPRA (XML)</h3>
      <span style="font-size:11px; color:#475569;">Entrada automática de estoque, conversão Caixa/Unidade e tributação (ICMS / PIS / COFINS / IBS / CBS)</span>
    </div>

    <div class="bevel-panel" style="padding:14px; display:flex; flex-direction:column; gap:12px; margin-bottom:14px;">
      <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
        <!-- Inputs ocultos para Arquivo(s) e Pasta -->
        <input id="inp-xml-arquivos" type="file" accept=".xml" multiple class="hidden" />
        <input id="inp-xml-pasta" type="file" webkitdirectory directory multiple class="hidden" />

        <button type="button" onclick="document.getElementById('inp-xml-arquivos').click()" class="btn-pdv" style="height:38px; padding:0 16px; font-size:12px;">
          📄 Selecionar Arquivo(s) XML
        </button>

        <button type="button" onclick="document.getElementById('inp-xml-pasta').click()" class="btn-pdv" style="height:38px; padding:0 16px; font-size:12px;">
          📁 Selecionar Pasta Inteira
        </button>

        <div style="display:flex; align-items:center; gap:6px; margin-left:auto;">
          <label for="inp-margem-lucro" style="font-size:12px; font-weight:bold; color:var(--cor-primaria);">Margem Lucro (%):</label>
          <input id="inp-margem-lucro" type="number" step="1" value="40"
                 style="width:80px; height:36px; text-align:right; padding:0 8px; font-size:15px; font-weight:bold; background:#ffff99; border:1px inset #808080;" />
        </div>

        <button id="btn-processar-xmls" type="button" onclick="window.retImportaNFe.processar()" class="btn-pdv"
                style="height:38px; padding:0 20px; font-size:13px; color:#006600;" disabled>
          ▶ PROCESSAR IMPORTAÇÃO
        </button>
      </div>

      <div id="lbl-status-selecao-xml" style="font-size:12px; font-weight:bold; color:#334155;">
        Nenhum arquivo XML selecionado.
      </div>
    </div>

    <!-- Resumo e Tabela de Resultados -->
    <div id="box-resumo-importacao" class="hidden" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; margin-bottom:12px;">
      <div class="bevel-panel" style="padding:8px; text-align:center;"><span style="font-size:11px; font-weight:bold;">IMPORTADAS</span><div id="res-imp-ok" style="font-size:20px; font-weight:900; color:#16a34a;">0</div></div>
      <div class="bevel-panel" style="padding:8px; text-align:center;"><span style="font-size:11px; font-weight:bold;">JÁ IMPORTADAS</span><div id="res-imp-ja" style="font-size:20px; font-weight:900; color:#0284c7;">0</div></div>
      <div class="bevel-panel" style="padding:8px; text-align:center;"><span style="font-size:11px; font-weight:bold;">IGNORADAS</span><div id="res-imp-ign" style="font-size:20px; font-weight:900; color:#b45309;">0</div></div>
      <div class="bevel-panel" style="padding:8px; text-align:center;"><span style="font-size:11px; font-weight:bold;">ERROS</span><div id="res-imp-err" style="font-size:20px; font-weight:900; color:#cc0000;">0</div></div>
    </div>

    <div style="border:2px inset #808080; max-height:calc(100vh - 330px); overflow-y:auto; background:#fff;">
      <table class="tabela-produtos">
        <thead>
          <tr>
            <th>Arquivo XML</th>
            <th style="width:75px;">Nº Nota</th>
            <th>Fornecedor</th>
            <th style="width:100px; text-align:right;">Valor (R$)</th>
            <th style="width:115px; text-align:center;">Status</th>
            <th>Detalhes / Produtos</th>
          </tr>
        </thead>
        <tbody id="tbody-resultado-importacao">
          <tr><td colspan="6" style="text-align:center; padding:24px; color:#666;">Selecione uma nota ou pasta para iniciar a importação.</td></tr>
        </tbody>
      </table>
    </div>
  `;

  const onArquivosEscolhidos = (e) => {
    const todos = Array.from(e.target.files || []);
    arquivosSelecionados = todos.filter((f) => f.name.toLowerCase().endsWith(".xml"));
    document.getElementById("lbl-status-selecao-xml").innerText =
      arquivosSelecionados.length > 0
        ? `${arquivosSelecionados.length} arquivo(s) .XML pronto(s) para importar.`
        : "Nenhum arquivo .XML encontrado na seleção.";
    document.getElementById("btn-processar-xmls").disabled = arquivosSelecionados.length === 0;
  };

  document.getElementById("inp-xml-arquivos").addEventListener("change", onArquivosEscolhidos);
  document.getElementById("inp-xml-pasta").addEventListener("change", onArquivosEscolhidos);
}

export async function processarImportacaoXMLs() {
  if (arquivosSelecionados.length === 0) return;

  const btn = document.getElementById("btn-processar-xmls");
  const tbody = document.getElementById("tbody-resultado-importacao");
  const margem = document.getElementById("inp-margem-lucro").value || "40";

  btn.disabled = true;
  btn.innerText = "⏳ IMPORTANDO...";
  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px;">Processando ${arquivosSelecionados.length} XML(s)...</td></tr>`;

  const formData = new FormData();
  formData.append("margem_percentual", margem);
  arquivosSelecionados.forEach((file) => formData.append("arquivos", file));

  try {
    const resp = await fetch(getUrlImportacao(), { method: "POST", body: formData });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Falha na importação.");

    document.getElementById("box-resumo-importacao").classList.remove("hidden");
    document.getElementById("res-imp-ok").innerText = data.resumo.IMPORTADA || 0;
    document.getElementById("res-imp-ja").innerText = data.resumo.JA_IMPORTADA || 0;
    document.getElementById("res-imp-ign").innerText = data.resumo.IGNORADO || 0;
    document.getElementById("res-imp-err").innerText = data.resumo.ERRO || 0;

    const cores = { IMPORTADA: "#16a34a", JA_IMPORTADA: "#0284c7", IGNORADO: "#b45309", ERRO: "#cc0000" };
    tbody.innerHTML = (data.resultados || []).map((r) => `
      <tr>
        <td>${r.arquivo}</td>
        <td>${r.nnf || "-"}</td>
        <td>${r.fornecedor || "-"}</td>
        <td style="text-align:right;">${r.vnf ? formatarMoeda(r.vnf) : "-"}</td>
        <td style="text-align:center; color:${cores[r.status] || "#333"};">${r.status}</td>
        <td>${r.motivo || ""}</td>
      </tr>
    `).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:#cc0000;">${e.message}</td></tr>`;
  } finally {
    btn.innerText = "▶ PROCESSAR IMPORTAÇÃO";
    btn.disabled = false;
  }
}

window.retImportaNFe = {
  abrir: abrirImportaNFe,
  processar: processarImportacaoXMLs
};