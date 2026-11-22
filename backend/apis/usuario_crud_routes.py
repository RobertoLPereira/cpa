import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import SQLModel, Field, Session, select

from backend.apis.mysql.orm.database_unificado import get_session
from backend.models.usuarios.usuario_model import Usuarios

usuarios_router = APIRouter(prefix="/api/v1/retaguarda/usuarios", tags=["Retaguarda - Usuarios"])


@usuarios_router.get("")
def listar_usuarios(q: str = "", session: Session = Depends(get_session)):
    try:
        stmt = select(Usuarios)
        if q.strip():
            termo = f"%{q.strip()}%"
            stmt = stmt.where(
                (Usuarios.usua_nome.ilike(termo)) |
                (Usuarios.usua_grupo_geral.ilike(termo)) |
                (Usuarios.usua_grupo_pdv.ilike(termo)) |
                (Usuarios.usua_senha.ilike(termo))
            )
        registros = session.exec(stmt.order_by(Usuarios.usua_nome).limit(100)).all()
        return {"registros": registros}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@usuarios_router.get("/{item_id}")
def obter_usuarios(item_id: int, session: Session = Depends(get_session)):
    reg = session.get(Usuarios, item_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    return reg


@usuarios_router.post("")
def criar_usuarios(dados: Usuarios, session: Session = Depends(get_session)):
    try:
        dados.id_usuario = None
        session.add(dados)
        session.commit()
        session.refresh(dados)
        return {"mensagem": "Registro cadastrado com sucesso!", "registro": dados}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@usuarios_router.put("/{item_id}")
def atualizar_usuarios(item_id: int, dados: Usuarios, session: Session = Depends(get_session)):
    reg = session.get(Usuarios, item_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    try:
        for chave, valor in dados.model_dump(exclude={"id_usuario"}).items():
            setattr(reg, chave, valor)
        session.add(reg)
        session.commit()
        session.refresh(reg)
        return {"mensagem": "Registro atualizado com sucesso!", "registro": reg}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@usuarios_router.delete("/{item_id}")
def excluir_usuarios(item_id: int, session: Session = Depends(get_session)):
    reg = session.get(Usuarios, item_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    try:
        session.delete(reg)
        session.commit()
        return {"mensagem": "Registro excluído com sucesso!"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))