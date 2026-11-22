from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import Column, Numeric, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

class Usuarios(SQLModel, table=True):
    __tablename__ = "usuarios"
    __table_args__ = {"extend_existing": True}

    id_usuario: Optional[int] = Field(default=None, primary_key=True)
    usua_nome: Optional[str] = Field(default=None)
    usua_cliente: Optional[int] = Field(default=None)
    usua_grupo_geral: Optional[str] = Field(default=None)
    usua_grupo_pdv: Optional[str] = Field(default=None)
    usua_senha: Optional[str] = Field(default=None)
    data_cadastro: Optional[datetime] = Field(default_factory=datetime.now)
    ult_gravacao: Optional[datetime] = Field(default_factory=datetime.now)
    lembrete: Optional[str] = Field(default=None)
    dias_validade: Optional[int] = Field(default=None)
    validade_senha: Optional[datetime] = Field(default_factory=datetime.now)
    usua_foto: Optional[str] = Field(default=None)
    usua_obs: Optional[str] = Field(default=None)
    situacao: Optional[str] = Field(default=None)
    usua_config1: Optional[str] = Field(default=None)
    modelonfe: Optional[str] = Field(default=None)
    nivel: Optional[str] = Field(default=None)
    alterar_qtde: Optional[str] = Field(default=None)
