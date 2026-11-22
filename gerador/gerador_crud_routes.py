from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import inspect
from sqlmodel import Session

from backend.apis.mysql.orm.database_unificado import get_session

MAPA_TIPOS_SQLMODEL = {
    "INTEGER": "int", "BIGINT": "int", "SMALLINT": "int", "TINYINT": "int",
    "VARCHAR": "str", "CHAR": "str", "TEXT": "str", "LONGTEXT": "str",
    "DECIMAL": "Decimal", "NUMERIC": "Decimal", "FLOAT": "float", "REAL": "float",
    "DATETIME": "datetime", "TIMESTAMP": "datetime", "DATE": "date", "BOOLEAN": "bool"
}

gerador_crud_router = APIRouter(prefix="/api/v1/dev", tags=["Gerador - Suporte"])


def _inspecionar_tabela(insp, nome_tabela: str):
    if not insp.has_table(nome_tabela):
        raise HTTPException(status_code=404, detail=f"Tabela '{nome_tabela}' não encontrada no banco.")

    colunas = insp.get_columns(nome_tabela)
    pk_cols = set(insp.get_pk_constraint(nome_tabela).get("constrained_columns", []))
    indices = set()
    for idx in insp.get_indexes(nome_tabela):
        indices.update(idx.get("column_names", []))

    fks = {}
    for fk in insp.get_foreign_keys(nome_tabela):
        cols_locais = fk.get("constrained_columns", [])
        tabela_ref = fk.get("referred_table")
        cols_ref = fk.get("referred_columns", [])
        if tabela_ref and len(cols_locais) == len(cols_ref):
            for col_local, col_ref in zip(cols_locais, cols_ref):
                fks[col_local] = f"{tabela_ref}.{col_ref}"

    nome_classe = "".join(parte.capitalize() for parte in nome_tabela.split("_"))
    return colunas, pk_cols, indices, fks, nome_classe


def _montar_classe_sqlmodel(insp, nome_tabela: str) -> str:
    colunas, pk_cols, indices, fks, nome_classe = _inspecionar_tabela(insp, nome_tabela)
    linhas = [
        f"class {nome_classe}(SQLModel, table=True):",
        f'    __tablename__ = "{nome_tabela}"',
        '    __table_args__ = {"extend_existing": True}',
        ""
    ]

    for col in colunas:
        nome_col = col["name"]
        tipo_sql = str(col["type"]).upper().split("(")[0].strip()
        tipo_py = MAPA_TIPOS_SQLMODEL.get(tipo_sql, "str")
        nullable = col.get("nullable", True)
        eh_pk = nome_col in pk_cols
        eh_idx = nome_col in indices
        fk_destino = fks.get(nome_col)

        tipo_anotacao = f"Optional[{tipo_py}]" if (nullable or eh_pk) else tipo_py
        args_field = []

        if eh_pk:
            args_field.extend(["default=None", "primary_key=True"])
        elif tipo_py == "Decimal":
            prec = getattr(col["type"], "precision", 15) or 15
            scale = getattr(col["type"], "scale", 2) or 2
            args_field.extend(['default=Decimal("0.00")', f"max_digits={prec}", f"decimal_places={scale}"])
        elif tipo_py == "datetime":
            args_field.append("default_factory=datetime.now")
        elif nullable:
            args_field.append("default=None")

        if fk_destino:
            args_field.append(f'foreign_key="{fk_destino}"')
        if eh_idx and not eh_pk:
            args_field.append("index=True")

        if args_field:
            linhas.append(f"    {nome_col}: {tipo_anotacao} = Field({', '.join(args_field)})")
        else:
            linhas.append(f"    {nome_col}: {tipo_anotacao}")

    return "\n".join(linhas)


@gerador_crud_router.get("/gerar-crud-python/{nome_tabela}", response_class=PlainTextResponse)
def gerar_crud_python(nome_tabela: str, session: Session = Depends(get_session)):
    """Gera o arquivo {nome_tabela}_router.py completo para o FastAPI."""
    insp = inspect(session.get_bind())
    colunas, pk_cols, _, _, nome_classe = _inspecionar_tabela(insp, nome_tabela)
    classe_sqlmodel = _montar_classe_sqlmodel(insp, nome_tabela)

    pk_col = next(iter(pk_cols), "id")
    pk_info = next((c for c in colunas if c["name"] == pk_col), colunas)
    pk_eh_str = MAPA_TIPOS_SQLMODEL.get(str(pk_info["type"]).upper().split("(")[0].strip(), "str") == "str"

    cols_texto = [
        c["name"] for c in colunas
        if MAPA_TIPOS_SQLMODEL.get(str(c["type"]).upper().split("(")[0].strip(), "str") == "str"
        and c["name"] != pk_col
    ]
    filtros_busca = " |\n                ".join(f"({nome_classe}.{c}.ilike(termo))" for c in cols_texto[:4])
    bloco_busca = f"""if q.strip():
            termo = f"%{{q.strip()}}%"
            stmt = stmt.where(
                {filtros_busca}
            )""" if filtros_busca else "pass"

    col_ordenacao = cols_texto[0] if cols_texto else pk_col

    gerar_id_post = f"dados.{pk_col} = str(uuid.uuid4())" if pk_eh_str else f"dados.{pk_col} = None"
    tipo_param_id = "str" if pk_eh_str else "int"

    return f'''import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import SQLModel, Field, Session, select

from backend.apis.mysql.orm.database_unificado import get_session


{classe_sqlmodel}


{nome_tabela}_router = APIRouter(prefix="/api/v1/retaguarda/{nome_tabela}", tags=["Retaguarda - {nome_classe}"])


@{nome_tabela}_router.get("")
def listar_{nome_tabela}(q: str = "", session: Session = Depends(get_session)):
    try:
        stmt = select({nome_classe})
        {bloco_busca}
        registros = session.exec(stmt.order_by({nome_classe}.{col_ordenacao}).limit(100)).all()
        return {{"registros": registros}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@{nome_tabela}_router.get("/{{item_id}}")
def obter_{nome_tabela}(item_id: {tipo_param_id}, session: Session = Depends(get_session)):
    reg = session.get({nome_classe}, item_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    return reg


@{nome_tabela}_router.post("")
def criar_{nome_tabela}(dados: {nome_classe}, session: Session = Depends(get_session)):
    try:
        {gerar_id_post}
        session.add(dados)
        session.commit()
        session.refresh(dados)
        return {{"mensagem": "Registro cadastrado com sucesso!", "registro": dados}}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@{nome_tabela}_router.put("/{{item_id}}")
def atualizar_{nome_tabela}(item_id: {tipo_param_id}, dados: {nome_classe}, session: Session = Depends(get_session)):
    reg = session.get({nome_classe}, item_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    try:
        for chave, valor in dados.model_dump(exclude={{"{pk_col}"}}).items():
            setattr(reg, chave, valor)
        session.add(reg)
        session.commit()
        session.refresh(reg)
        return {{"mensagem": "Registro atualizado com sucesso!", "registro": reg}}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@{nome_tabela}_router.delete("/{{item_id}}")
def excluir_{nome_tabela}(item_id: {tipo_param_id}, session: Session = Depends(get_session)):
    reg = session.get({nome_classe}, item_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    try:
        session.delete(reg)
        session.commit()
        return {{"mensagem": "Registro excluído com sucesso!"}}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
'''
@gerador_crud_router.get("/gerar-crud-js/{nome_tabela}", response_class=PlainTextResponse)
def gerar_crud_js(nome_tabela: str, session: Session = Depends(get_session)):
    """Gera o módulo frontend js/retaguarda/{nome_tabela}.js pronto para usar."""
    insp = inspect(session.get_bind())
    colunas, pk_cols, _, _, nome_classe = _inspecionar_tabela(insp, nome_tabela)
    pk_col = next(iter(pk_cols), "id")

    cols_visiveis = [c for c in colunas if c["name"] != pk_col]
    cols_tabela = cols_visiveis[:6]

    ths = "\n            ".join(f"<th>{c['name'].upper()}</th>" for c in cols_tabela)
    tds = "\n          ".join(f"<td>${{r.{c['name']} ?? ''}}</td>" for c in cols_tabela)

    inputs_form = []
    for c in cols_visiveis:
        nome_c = c["name"]
        tipo_sql = str(c["type"]).upper().split("(")[0].strip()
        tipo_py = MAPA_TIPOS_SQLMODEL.get(tipo_sql, "str")
        req = "" if c.get("nullable", True) else "required"
        bg = "background:#ffff99;" if req else ""

        if tipo_py in ("int", "Decimal", "float"):
            step = "1" if tipo_py == "int" else "0.01"
            inp = f'<input name="{nome_c}" type="number" step="{step}" value="${{reg.{nome_c} ?? 0}}" {req} style="${{estiloInput}} {bg} text-align:right;" />'
        else:
            inp = f'<input name="{nome_c}" type="text" value="${{reg.{nome_c} ?? \'\'}}" {req} style="${{estiloInput}} {bg}" />'

        inputs_form.append(f'<div><label style="${{estiloLabel}}">{nome_c.upper()}{"*" if req else ""}</label>{inp}</div>')

    campos_html = "\n        ".join(inputs_form)

    return f'''// ==========================================================================
// RETAGUARDA/{nome_tabela.upper()}.JS - CRUD Gerado Automaticamente
//1. Gera o Backend: Acesse http://localhost:8000/api/v1/dev/gerar-crud-python/destinatario (ou emitente, usuarios, etc.) → salve como destinatario_router.py e registre app.include_router(destinatario_router).
//2. Gera o Frontend: Acesse http://localhost:8000/api/v1/dev/gerar-crud-js/destinatario → salve em js/retaguarda/destinatario.js e importe em js/main.js.
//3. Conecta o Menu: No auth_retaguarda.js, chame onclick="window.retDestinatario.abrirLista()".
// ==========================================================================

function getEndpoint() {{
  return typeof API_URL !== "undefined"
    ? `${{API_URL}}/retaguarda/{nome_tabela}`
    : "http://localhost:8000/api/v1/retaguarda/{nome_tabela}";
}}

let timerBusca = null;

export async function abrirLista{nome_classe}() {{
  const container = document.getElementById("view-modulo-retaguarda");
  if (!container) return;

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #cbd5e1; padding-bottom:10px; margin-bottom:12px;">
      <h3 style="color:var(--cor-secundaria); font-size:18px; margin:0;">CADASTRO DE {nome_tabela.upper()}</h3>
      <button onclick="window.ret{nome_classe}.abrirForm(null)" class="btn-pdv" style="height:36px; padding:0 16px; color:#006600;">
        + NOVO REGISTRO
      </button>
    </div>

    <div style="display:flex; gap:8px; margin-bottom:10px;">
      <input id="ret-busca-{nome_tabela}" type="text" placeholder="Digite 3+ caracteres para pesquisar..."
             style="flex:1; height:32px; padding:0 10px; border:2px inset #808080; background:#ffff99; font-weight:bold;" />
      <button onclick="window.ret{nome_classe}.buscar()" class="btn-pdv" style="height:32px; padding:0 14px;">Pesquisar</button>
    </div>

    <div style="border:2px inset #808080; max-height:calc(100vh - 245px); overflow-y:auto; background:#fff;">
      <table class="tabela-produtos">
        <thead>
          <tr>
            {ths}
            <th style="width:110px; text-align:center;">AÇÕES</th>
          </tr>
        </thead>
        <tbody id="ret-tbody-{nome_tabela}"></tbody>
      </table>
    </div>
  `;

  const inp = document.getElementById("ret-busca-{nome_tabela}");
  inp.addEventListener("input", (e) => {{
    clearTimeout(timerBusca);
    const t = e.target.value.trim();
    if (t.length >= 3 || t.length === 0) {{
      timerBusca = setTimeout(() => buscar{nome_classe}(), 250);
    }}
  }});

  await buscar{nome_classe}();
}}

export async function buscar{nome_classe}() {{
  const termo = document.getElementById("ret-busca-{nome_tabela}")?.value || "";
  const tbody = document.getElementById("ret-tbody-{nome_tabela}");
  if (!tbody) return;

  try {{
    const resp = await fetch(`${{getEndpoint()}}?q=${{encodeURIComponent(termo)}}`);
    const data = await resp.json();
    const lista = data.registros || [];

    if (lista.length === 0) {{
      tbody.innerHTML = `<tr><td colspan="{len(cols_tabela) + 1}" style="text-align:center; padding:20px;">Nenhum registro encontrado.</td></tr>`;
      return;
    }}

    tbody.innerHTML = lista.map((r) => `
      <tr>
        {tds}
        <td style="text-align:center;">
          <button onclick="window.ret{nome_classe}.abrirForm('${{r.{pk_col}}}')" class="btn-pdv" style="padding:2px 6px;">Editar</button>
          <button onclick="window.ret{nome_classe}.excluir('${{r.{pk_col}}}')" class="btn-pdv" style="padding:2px 6px; color:#cc0000;">X</button>
        </td>
      </tr>
    `).join("");
  }} catch (e) {{
    tbody.innerHTML = `<tr><td colspan="{len(cols_tabela) + 1}" style="text-align:center; color:#cc0000;">${{e.message}}</td></tr>`;
  }}
}}

export async function abrirForm{nome_classe}(itemId = null) {{
  let reg = {{}};
  if (itemId) {{
    const resp = await fetch(`${{getEndpoint()}}/${{itemId}}`);
    if (resp.ok) reg = await resp.json();
  }}

  const container = document.getElementById("view-modulo-retaguarda");
  const estiloInput = "width:100%; height:30px; padding:0 6px; border:1px inset #808080; font-weight:bold;";
  const estiloLabel = "display:block; font-size:11px; font-weight:bold; color:var(--cor-primaria); margin-bottom:2px;";

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #cbd5e1; padding-bottom:8px; margin-bottom:12px;">
      <h3 style="color:var(--cor-secundaria); margin:0;">${{itemId ? "EDITAR" : "NOVO"}} - {nome_tabela.upper()}</h3>
      <button onclick="window.ret{nome_classe}.abrirLista()" class="btn-pdv" style="height:32px; padding:0 14px;">← Voltar</button>
    </div>

    <form id="form-ret-{nome_tabela}" class="bevel-panel" style="padding:14px;">
      <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:12px;">
        {campos_html}
      </div>
      <div style="margin-top:16px; display:flex; justify-content:flex-end; gap:10px; border-top:1px solid #cbd5e1; padding-top:12px;">
        <button type="button" onclick="window.ret{nome_classe}.abrirLista()" class="btn-pdv" style="height:36px; width:110px; color:#cc0000;">Cancelar</button>
        <button type="submit" class="btn-pdv" style="height:36px; width:150px; color:#006600;">SALVAR</button>
      </div>
    </form>
  `;

  document.getElementById("form-ret-{nome_tabela}").addEventListener("submit", async (e) => {{
    e.preventDefault();
    const payload = Object.fromEntries(new FormData(e.target).entries());
    const url = itemId ? `${{getEndpoint()}}/${{itemId}}` : getEndpoint();
    const method = itemId ? "PUT" : "POST";

    const resp = await fetch(url, {{
      method,
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(payload)
    }});
    const res = await resp.json();
    if (!resp.ok) return alert("Erro: " + (res.detail || "Falha ao salvar."));

    alert(res.mensagem);
    await abrirLista{nome_classe}();
  }});
}}

export async function excluir{nome_classe}(itemId) {{
  if (!confirm("Confirma a exclusão deste registro?")) return;
  const resp = await fetch(`${{getEndpoint()}}/${{itemId}}`, {{ method: "DELETE" }});
  const res = await resp.json();
  if (!resp.ok) return alert("Erro: " + (res.detail || "Falha ao excluir."));
  alert(res.mensagem);
  await buscar{nome_classe}();
}}

window.ret{nome_classe} = {{
  abrirLista: abrirLista{nome_classe},
  buscar: buscar{nome_classe},
  abrirForm: abrirForm{nome_classe},
  excluir: excluir{nome_classe}
}};
'''
