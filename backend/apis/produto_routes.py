import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import SQLModel, Field, Session, select

from backend.apis.mysql.orm.database_unificado import get_session
from backend.models.produto.produto_model import Produto

produtos_router = APIRouter(prefix="/api/v1/retaguarda/produtos", tags=["Retaguarda"])

@produtos_router.get("")
def listar_produtos(
    q: str = "",
    filtro: str = "TODOS",  # TODOS | SEM_PRECO | SEM_IBSCBS
    session: Session = Depends(get_session)
):
    try:
        stmt = select(Produto)

        if q.strip():
            termo = f"%{q.strip()}%"
            stmt = stmt.where(
                (Produto.xprod.ilike(termo)) |
                (Produto.cprod.ilike(termo)) |
                (Produto.cean.ilike(termo)) |
                (Produto.ncm.ilike(termo))
            )

        if filtro == "SEM_PRECO":
            stmt = stmt.where(Produto.vuncom <= Decimal("0.00"))
        elif filtro == "SEM_IBSCBS":
            stmt = stmt.where((Produto.ibscbs_cst == None) | (Produto.ibscbs_cst == ""))

        produtos = session.exec(stmt.order_by(Produto.xprod).limit(100)).all()
        return {"produtos": produtos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@produtos_router.get("/{produto_id}")
def obter_produto(produto_id: str, session: Session = Depends(get_session)):
    prod = session.get(Produto, produto_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return prod


@produtos_router.post("")
def criar_produto(dados: Produto, session: Session = Depends(get_session)):
    try:
        existente = session.exec(select(Produto).where(Produto.cprod == dados.cprod.strip())).first()
        if existente:
            raise HTTPException(status_code=400, detail=f"Já existe um produto com o código '{dados.cprod}'.")

        dados.id = str(uuid.uuid4())
        dados.cprod = dados.cprod.strip()
        dados.xprod = dados.xprod.strip().upper()
        dados.cean = (dados.cean or "").strip() or "SEM GTIN"
        dados.ceantrib = (dados.ceantrib or "").strip() or dados.cean
        dados.utrib = (dados.utrib or "").strip() or dados.ucom
        if Decimal(str(dados.vuntrib or "0")) <= Decimal("0"):
            dados.vuntrib = dados.vuncom
        dados.atualizado_em = datetime.now().isoformat()

        session.add(dados)
        session.commit()
        session.refresh(dados)
        return {"mensagem": "Produto cadastrado com sucesso!", "produto": dados}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@produtos_router.put("/{produto_id}")
def atualizar_produto(produto_id: str, dados: Produto, session: Session = Depends(get_session)):
    prod = session.get(Produto, produto_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    try:
        campos = dados.model_dump(exclude={"id", "atualizado_em"})
        for chave, valor in campos.items():
            setattr(prod, chave, valor)

        prod.xprod = prod.xprod.strip().upper()
        prod.cean = (prod.cean or "").strip() or "SEM GTIN"
        prod.ceantrib = (prod.ceantrib or "").strip() or prod.cean
        prod.utrib = (prod.utrib or "").strip() or prod.ucom
        prod.atualizado_em = datetime.now().isoformat()

        session.add(prod)
        session.commit()
        session.refresh(prod)
        return {"mensagem": "Produto atualizado com sucesso!", "produto": prod}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@produtos_router.delete("/{produto_id}")
def excluir_produto(produto_id: str, session: Session = Depends(get_session)):
    prod = session.get(Produto, produto_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    try:
        session.delete(prod)
        session.commit()
        return {"mensagem": "Produto excluído com sucesso!"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
