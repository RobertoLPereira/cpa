from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import inspect
from sqlmodel import Session

from backend.apis.mysql.orm.database_unificado import get_session

MAPA_TIPOS_SQLMODEL = {
    "INTEGER": "int",
    "BIGINT": "int",
    "SMALLINT": "int",
    "TINYINT": "int",
    "VARCHAR": "str",
    "CHAR": "str",
    "TEXT": "str",
    "LONGTEXT": "str",
    "DECIMAL": "Decimal",
    "NUMERIC": "Decimal",
    "FLOAT": "float",
    "REAL": "float",
    "DATETIME": "datetime",
    "TIMESTAMP": "datetime",
    "DATE": "date",
    "BOOLEAN": "bool"
}

gerador_router = APIRouter(prefix="/api/v1/dev", tags=["Gerador - Suporte"])


def _ordenar_tabelas_por_dependencia(insp, tabelas: list[str]) -> list[str]:
    """Ordena as tabelas colocando as tabelas-pai antes das filhas (ordenação topológica)."""
    dependencias = {}
    for tab in tabelas:
        pais = set()
        for fk in insp.get_foreign_keys(tab):
            ref = fk.get("referred_table")
            if ref and ref != tab and ref in tabelas:
                pais.add(ref)
        dependencias[tab] = pais

    ordenadas = []
    visitadas = set()

    def visitar(tab: str):
        if tab in visitadas:
            return
        visitadas.add(tab)
        for pai in sorted(dependencias.get(tab, [])):
            visitar(pai)
        ordenadas.append(tab)

    for tab in sorted(tabelas):
        visitar(tab)

    return ordenadas


def _montar_classe_sqlmodel(insp, nome_tabela: str) -> str:
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
    linhas = [
        f"class {nome_classe}(SQLModel, table=True):",
        f'    __tablename__ = "{nome_tabela}"'
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
            args_field.append("default=None")
            args_field.append("primary_key=True")
        elif tipo_py == "Decimal":
            prec = getattr(col["type"], "precision", 15) or 15
            scale = getattr(col["type"], "scale", 2) or 2
            args_field.append('default=Decimal("0.00")')
            args_field.append(f"max_digits={prec}")
            args_field.append(f"decimal_places={scale}")
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


@gerador_router.get("/gerar-modelo/{nome_tabela}", response_class=PlainTextResponse)
def gerar_modelo_unico(nome_tabela: str, session: Session = Depends(get_session)):
    try:
        insp = inspect(session.get_bind())
        if not insp.has_table(nome_tabela):
            raise HTTPException(status_code=404, detail=f"Tabela '{nome_tabela}' não encontrada no banco.")
        return _montar_classe_sqlmodel(insp, nome_tabela)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@gerador_router.get("/gerar-todos-modelos", response_class=PlainTextResponse)
def gerar_todos_modelos_sqlmodel(session: Session = Depends(get_session)):
    try:
        insp = inspect(session.get_bind())
        tabelas_validas = [
            t for t in insp.get_table_names()
            if not t.startswith("sqlite_")
        ]
        tabelas_ordenadas = _ordenar_tabelas_por_dependencia(insp, tabelas_validas)

        cabecalho = [
            "from datetime import datetime, date",
            "from decimal import Decimal",
            "from typing import Optional",
            "from sqlmodel import SQLModel, Field",
            "",
            ""
        ]

        blocos_classes = [
            _montar_classe_sqlmodel(insp, tabela)
            for tabela in tabelas_ordenadas
        ]

        return "\n".join(cabecalho) + "\n\n\n".join(blocos_classes) + "\n"
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
