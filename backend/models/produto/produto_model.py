from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import Column, Numeric, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

class Produto(SQLModel, table=True):
    __tablename__ = "produto"
    __table_args__ = {"extend_existing": True}

    id: Optional[str] = Field(default=None, primary_key=True)
    cprod: str = Field(index=True)
    cean: Optional[str] = Field(default=None)
    xprod: str
    ncm: str
    cest: Optional[str] = Field(default=None)
    cbenef: Optional[str] = Field(default=None)
    cfop_padrao: str
    ucom: str
    vuncom: Decimal = Field(default=Decimal("0.00"), max_digits=15, decimal_places=10)
    ceantrib: Optional[str] = Field(default=None)
    utrib: str
    vuntrib: Decimal = Field(default=Decimal("0.00"), max_digits=15, decimal_places=10)
    icms_orig: Optional[str] = Field(default=None)
    icms_cst: Optional[str] = Field(default=None)
    icms_picms: Optional[Decimal] = Field(default=Decimal("0.00"), max_digits=7, decimal_places=4)
    pis_cst: Optional[str] = Field(default=None)
    pis_ppis: Optional[Decimal] = Field(default=Decimal("0.00"), max_digits=7, decimal_places=4)
    cofins_cst: Optional[str] = Field(default=None)
    cofins_pcofins: Optional[Decimal] = Field(default=Decimal("0.00"), max_digits=7, decimal_places=4)
    ibscbs_cst: Optional[str] = Field(default=None)
    ibscbs_cclasstrib: Optional[str] = Field(default=None)
    ibs_pibsuf: Optional[Decimal] = Field(default=Decimal("0.00"), max_digits=7, decimal_places=4)
    cbs_pcbs: Optional[Decimal] = Field(default=Decimal("0.00"), max_digits=7, decimal_places=4)
    atualizado_em: str = Field(default_factory=lambda: datetime.now().isoformat(), index=True)
    fator_conversao: Decimal = Field(default=Decimal("1.0000"), max_digits=15, decimal_places=4)
    estoque_atual: Decimal = Field(default=Decimal("0.0000"), max_digits=15, decimal_places=4)
    ind_monofasico: int = Field(default=0)
    ibpt_fed: Decimal = Field(default=Decimal("0.00"), max_digits=7, decimal_places=4)
    ibpt_est: Decimal = Field(default=Decimal("0.00"), max_digits=7, decimal_places=4)
