// ==========================================================================
// RETAGUARDA/USUARIOS.JS - CRUD Gerado Automaticamente
// ==========================================================================

function getEndpoint() {
  return typeof API_URL !== "undefined"
    ? `${API_URL}/retaguarda/usuarios`
    : "http://localhost:8000/api/v1/retaguarda/usuarios";
}

let timerBusca = null;

export async function abrirListaUsuarios() {
  const container = document.getElementById("view-modulo-retaguarda");
  if (!container) return;

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #cbd5e1; padding-bottom:10px; margin-bottom:12px;">
      <h3 style="color:var(--cor-secundaria); font-size:18px; margin:0;">CADASTRO DE USUARIOS</h3>
      <button onclick="window.retUsuarios.abrirForm(null)" class="btn-pdv" style="height:36px; padding:0 16px; color:#006600;">
        + NOVO REGISTRO
      </button>
    </div>

    <div style="display:flex; gap:8px; margin-bottom:10px;">
      <input id="ret-busca-usuarios" type="text" placeholder="Digite 3+ caracteres para pesquisar..."
             style="flex:1; height:32px; padding:0 10px; border:2px inset #808080; background:#ffff99; font-weight:bold;" />
      <button onclick="window.retUsuarios.buscar()" class="btn-pdv" style="height:32px; padding:0 14px;">Pesquisar</button>
    </div>

    <div style="border:2px inset #808080; max-height:calc(100vh - 245px); overflow-y:auto; background:#fff;">
      <table class="tabela-produtos">
        <thead>
          <tr>
            <th>USUA_NOME</th>
            <th>USUA_CLIENTE</th>
            <th>USUA_GRUPO_GERAL</th>
            <th>USUA_GRUPO_PDV</th>
            <th>USUA_SENHA</th>
            <th>DATA_CADASTRO</th>
            <th style="width:110px; text-align:center;">AÇÕES</th>
          </tr>
        </thead>
        <tbody id="ret-tbody-usuarios"></tbody>
      </table>
    </div>
  `;

  const inp = document.getElementById("ret-busca-usuarios");
  inp.addEventListener("input", (e) => {
    clearTimeout(timerBusca);
    const t = e.target.value.trim();
    if (t.length >= 3 || t.length === 0) {
      timerBusca = setTimeout(() => buscarUsuarios(), 250);
    }
  });

  await buscarUsuarios();
}

export async function buscarUsuarios() {
  const termo = document.getElementById("ret-busca-usuarios")?.value || "";
  const tbody = document.getElementById("ret-tbody-usuarios");
  if (!tbody) return;

  try {
    const resp = await fetch(`${getEndpoint()}?q=${encodeURIComponent(termo)}`);
    const data = await resp.json();
    const lista = data.registros || [];

    if (lista.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px;">Nenhum registro encontrado.</td></tr>`;
      return;
    }

    tbody.innerHTML = lista.map((r) => `
      <tr>
        <td>${r.usua_nome ?? ''}</td>
          <td>${r.usua_cliente ?? ''}</td>
          <td>${r.usua_grupo_geral ?? ''}</td>
          <td>${r.usua_grupo_pdv ?? ''}</td>
          <td>${r.usua_senha ?? ''}</td>
          <td>${r.data_cadastro ?? ''}</td>
        <td style="text-align:center;">
          <button onclick="window.retUsuarios.abrirForm('${r.id_usuario}')" class="btn-pdv" style="padding:2px 6px;">Editar</button>
          <button onclick="window.retUsuarios.excluir('${r.id_usuario}')" class="btn-pdv" style="padding:2px 6px; color:#cc0000;">X</button>
        </td>
      </tr>
    `).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#cc0000;">${e.message}</td></tr>`;
  }
}

export async function abrirFormUsuarios(itemId = null) {
  let reg = {};
  if (itemId) {
    const resp = await fetch(`${getEndpoint()}/${itemId}`);
    if (resp.ok) reg = await resp.json();
  }

  const container = document.getElementById("view-modulo-retaguarda");
  const estiloInput = "width:100%; height:30px; padding:0 6px; border:1px inset #808080; font-weight:bold;";
  const estiloLabel = "display:block; font-size:11px; font-weight:bold; color:var(--cor-primaria); margin-bottom:2px;";

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #cbd5e1; padding-bottom:8px; margin-bottom:12px;">
      <h3 style="color:var(--cor-secundaria); margin:0;">${itemId ? "EDITAR" : "NOVO"} - USUARIOS</h3>
      <button onclick="window.retUsuarios.abrirLista()" class="btn-pdv" style="height:32px; padding:0 14px;">← Voltar</button>
    </div>

    <form id="form-ret-usuarios" class="bevel-panel" style="padding:14px;">
      <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:12px;">
        <div><label style="${estiloLabel}">USUA_NOME</label><input name="usua_nome" type="text" value="${reg.usua_nome ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">USUA_CLIENTE</label><input name="usua_cliente" type="number" step="1" value="${reg.usua_cliente ?? 0}"  style="${estiloInput}  text-align:right;" /></div>
        <div><label style="${estiloLabel}">USUA_GRUPO_GERAL</label><input name="usua_grupo_geral" type="text" value="${reg.usua_grupo_geral ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">USUA_GRUPO_PDV</label><input name="usua_grupo_pdv" type="text" value="${reg.usua_grupo_pdv ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">USUA_SENHA</label><input name="usua_senha" type="text" value="${reg.usua_senha ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">DATA_CADASTRO</label><input name="data_cadastro" type="text" value="${reg.data_cadastro ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">ULT_GRAVACAO</label><input name="ult_gravacao" type="text" value="${reg.ult_gravacao ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">LEMBRETE</label><input name="lembrete" type="text" value="${reg.lembrete ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">DIAS_VALIDADE</label><input name="dias_validade" type="number" step="1" value="${reg.dias_validade ?? 0}"  style="${estiloInput}  text-align:right;" /></div>
        <div><label style="${estiloLabel}">VALIDADE_SENHA</label><input name="validade_senha" type="text" value="${reg.validade_senha ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">USUA_FOTO</label><input name="usua_foto" type="text" value="${reg.usua_foto ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">USUA_OBS</label><input name="usua_obs" type="text" value="${reg.usua_obs ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">SITUACAO</label><input name="situacao" type="text" value="${reg.situacao ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">USUA_CONFIG1</label><input name="usua_config1" type="text" value="${reg.usua_config1 ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">MODELONFE</label><input name="modelonfe" type="text" value="${reg.modelonfe ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">NIVEL</label><input name="nivel" type="text" value="${reg.nivel ?? ''}"  style="${estiloInput} " /></div>
        <div><label style="${estiloLabel}">ALTERAR_QTDE</label><input name="alterar_qtde" type="text" value="${reg.alterar_qtde ?? ''}"  style="${estiloInput} " /></div>
      </div>
      <div style="margin-top:16px; display:flex; justify-content:flex-end; gap:10px; border-top:1px solid #cbd5e1; padding-top:12px;">
        <button type="button" onclick="window.retUsuarios.abrirLista()" class="btn-pdv" style="height:36px; width:110px; color:#cc0000;">Cancelar</button>
        <button type="submit" class="btn-pdv" style="height:36px; width:150px; color:#006600;">SALVAR</button>
      </div>
    </form>
  `;

  document.getElementById("form-ret-usuarios").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = Object.fromEntries(new FormData(e.target).entries());
    const url = itemId ? `${getEndpoint()}/${itemId}` : getEndpoint();
    const method = itemId ? "PUT" : "POST";

    const resp = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const res = await resp.json();
    if (!resp.ok) return alert("Erro: " + (res.detail || "Falha ao salvar."));

    alert(res.mensagem);
    await abrirListaUsuarios();
  });
}

export async function excluirUsuarios(itemId) {
  if (!confirm("Confirma a exclusão deste registro?")) return;
  const resp = await fetch(`${getEndpoint()}/${itemId}`, { method: "DELETE" });
  const res = await resp.json();
  if (!resp.ok) return alert("Erro: " + (res.detail || "Falha ao excluir."));
  alert(res.mensagem);
  await buscarUsuarios();
}

window.retUsuarios = {
  abrirLista: abrirListaUsuarios,
  buscar: buscarUsuarios,
  abrirForm: abrirFormUsuarios,
  excluir: excluirUsuarios
};