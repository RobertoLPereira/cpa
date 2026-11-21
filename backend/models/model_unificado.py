import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import Column, Numeric, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

def gerar_uuid() -> str:
    return str(uuid.uuid4())

def agora_iso() -> str:
    fuso_br = timezone(timedelta(hours=-3))
    return datetime.now(fuso_br).strftime('%Y-%m-%dT%H:%M:%S%z')[:-2] + ':00'

# =====================================================================
# 1. SCHEMAS PYDANTIC (ENTRADA DA API DO CAIXA)
# =====================================================================

class ItemCarrinhoInput(BaseModel):
    codigo: str
    quantidade: Decimal
    preco_contingencia: Decimal = Decimal("0.00")

class CarrinhoInput(BaseModel):
    itens_carrinho: List[ItemCarrinhoInput]

class PagamentoInput(BaseModel):
    tpag: str = "01"          # 01=Dinheiro, 03=Crédito, 04=Débito, 17=PIX
    vpag: Decimal
    vtroco: Decimal = Decimal("0.00")
    tband: Optional[str] = None
    caut: Optional[str] = None

class FinalizarVendaInput(BaseModel):
    terminal_id: str = "CAIXA-01"
    modelo: str = "65"        # '65'=NFC-e, '55'=NF-e
    serie: str = "1"
    cpf_cnpj_destinatario: Optional[str] = None
    nome_destinatario: Optional[str] = None
    itens_carrinho: List[ItemCarrinhoInput]
    pagamentos: List[PagamentoInput]

# =====================================================================
# 2. CADASTROS BASE (ESPELHO XML <emit>, <dest>, <prod>)
# =====================================================================

class Emitente(SQLModel, table=True):
    __tablename__ = "emitente"
    id: str = Field(default_factory=gerar_uuid, primary_key=True, max_length=36)
    cnpj: str = Field(unique=True, max_length=14)
    xnome: str = Field(max_length=60)
    xfant: Optional[str] = Field(default=None, max_length=60)
    xlgr: str = Field(max_length=60)
    nro: str = Field(max_length=60)
    xbairro: str = Field(max_length=60)
    cmun: str = Field(max_length=7)
    xmun: str = Field(max_length=60)
    uf: str = Field(max_length=2)
    cep: str = Field(max_length=8)
    fone: Optional[str] = Field(default=None, max_length=14)
    ie: str = Field(max_length=14)
    crt: str = Field(default="1", max_length=1)
    csc_id: Optional[str] = Field(default=None, max_length=6)
    csc_token: Optional[str] = Field(default=None, max_length=36)
    atualizado_em: str = Field(default_factory=agora_iso, max_length=25)

class Destinatario(SQLModel, table=True):
    __tablename__ = "destinatario"
    id: str = Field(default_factory=gerar_uuid, primary_key=True, max_length=36)
    cnpj_cpf: str = Field(unique=True, max_length=14)
    xnome: str = Field(max_length=60)
    xlgr: Optional[str] = Field(default=None, max_length=60)
    nro: Optional[str] = Field(default=None, max_length=60)
    xbairro: Optional[str] = Field(default=None, max_length=60)
    cmun: Optional[str] = Field(default=None, max_length=7)
    xmun: Optional[str] = Field(default=None, max_length=60)
    uf: Optional[str] = Field(default=None, max_length=2)
    cep: Optional[str] = Field(default=None, max_length=8)
    cpais: str = Field(default="1058", max_length=4)
    xpais: str = Field(default="Brasil", max_length=60)
    fone: Optional[str] = Field(default=None, max_length=14)
    indiedest: str = Field(default="9", max_length=1)
    ie: Optional[str] = Field(default=None, max_length=14)
    sincronizado: int = Field(default=1)
    atualizado_em: str = Field(default_factory=agora_iso, max_length=25)

class Produto(SQLModel, table=True):
    __tablename__ = "produto"
    id: str = Field(default_factory=gerar_uuid, primary_key=True, max_length=36)
    cprod: str = Field(unique=True, max_length=60)
    cean: Optional[str] = Field(default=None, index=True, max_length=14)
    xprod: str = Field(max_length=120)
    ncm: str = Field(max_length=8)
    cest: Optional[str] = Field(default=None, max_length=7)
    cbenef: Optional[str] = Field(default=None, max_length=10)
    cfop_padrao: str = Field(default="5102", max_length=4)
    ucom: str = Field(default="UN", max_length=6)
    vuncom: Decimal = Field(sa_column=Column(Numeric(15, 10), nullable=False, default=Decimal("0")))
    ceantrib: Optional[str] = Field(default=None, max_length=14)
    utrib: str = Field(default="UN", max_length=6)
    vuntrib: Decimal = Field(sa_column=Column(Numeric(15, 10), nullable=False, default=Decimal("0")))
    
    # Estoque e Conversão
    fator_conversao: Decimal = Field(sa_column=Column(Numeric(15, 4), default=Decimal("1.0000")))
    estoque_atual: Decimal = Field(sa_column=Column(Numeric(15, 4), default=Decimal("0.0000")))
    
    # Tributação Padrão
    icms_orig: str = Field(default="0", max_length=1)
    icms_cst: str = Field(default="102", max_length=3)
    icms_picms: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0")))
    pis_cst: str = Field(default="07", max_length=2)
    pis_ppis: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0")))
    cofins_cst: str = Field(default="07", max_length=2)
    cofins_pcofins: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0")))
    
    # Reforma Tributária (IBS / CBS) & IBPT
    ibscbs_cst: str = Field(default="000", max_length=3)
    ibscbs_cclasstrib: str = Field(default="000001", max_length=6)
    ibs_pibsuf: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0.1000")))
    cbs_pcbs: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0.9000")))
    ind_monofasico: int = Field(default=0)
    ibpt_fed: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0")))
    ibpt_est: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0")))
    atualizado_em: str = Field(default_factory=agora_iso, max_length=25)
# =====================================================================
# 3. DOCUMENTO FISCAL E CONTROLE DE NUMERAÇÃO
# =====================================================================

class NfeNumeracao(SQLModel, table=True):
    __tablename__ = "nfe_numeracao"
    __table_args__ = (UniqueConstraint("emitente_id", "modelo", "serie", "tpamb"),)

    id: str = Field(default_factory=gerar_uuid, primary_key=True, max_length=36)
    emitente_id: str = Field(foreign_key="emitente.id", max_length=36)
    terminal_id: str = Field(max_length=50)
    modelo: str = Field(max_length=2)
    serie: str = Field(max_length=3)
    tpamb: str = Field(default="2", max_length=1)
    ultimo_nnf: int = Field(default=0)
    em_contingencia: int = Field(default=0)
    dh_inicio_contingencia: Optional[str] = Field(default=None, max_length=25)
    justificativa_contingencia: Optional[str] = Field(default=None, max_length=255)
    atualizado_em: str = Field(default_factory=agora_iso, max_length=25)

class Nfe(SQLModel, table=True):
    __tablename__ = "nfe"
    id: str = Field(default_factory=gerar_uuid, primary_key=True, max_length=36)
    emitente_id: str = Field(foreign_key="emitente.id", max_length=36)
    destinatario_id: Optional[str] = Field(default=None, foreign_key="destinatario.id", max_length=36)
    
    status_sefaz: str = Field(default="PENDENTE", max_length=20)
    sincronizado: int = Field(default=0, index=True)

    chnfe: Optional[str] = Field(default=None, unique=True, max_length=44)
    versao: str = Field(default="4.00", max_length=4)
    cuf: str = Field(max_length=2)
    cnf: str = Field(max_length=8)
    natop: str = Field(default="VENDA DE MERCADORIA", max_length=60)
    modelo: str = Field(default="65", max_length=2)
    serie: str = Field(default="1", max_length=3)
    nnf: int
    dhemi: str = Field(default_factory=agora_iso, max_length=25)
    dhsaient: Optional[str] = Field(default=None, max_length=25)
    tpnf: str = Field(default="1", max_length=1)
    iddest: str = Field(default="1", max_length=1)
    cmunfg: str = Field(max_length=7)
    tpimp: str = Field(default="4", max_length=1)
    tpemis: str = Field(default="1", max_length=1)
    dhcont: Optional[str] = Field(default=None, max_length=25)
    xjust: Optional[str] = Field(default=None, max_length=255)
    cdv: str = Field(default="0", max_length=1)
    tpamb: str = Field(default="2", max_length=1)
    finnfe: str = Field(default="1", max_length=1)
    indfinal: str = Field(default="1", max_length=1)
    indpres: str = Field(default="1", max_length=1)
    procemi: str = Field(default="0", max_length=1)
    verproc: str = Field(default="PDV_REFORMA_1.0", max_length=20)

    # Totais
    vbc: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    vicms: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    vprod: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    vdesc: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    vpis: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    vcofins: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    vnf: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))

    # Totais IBS / CBS
    vbcibscbs: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    vibsuf: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    vibsmun: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    vibs: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    vcbs: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))

    modfrete: str = Field(default="9", max_length=1)
    infcpl: Optional[str] = Field(default=None, sa_column=Column(Text))
    qrcode: Optional[str] = Field(default=None, sa_column=Column(Text))
    urlchave: Optional[str] = Field(default=None, max_length=255)
    cstat: Optional[str] = Field(default=None, max_length=3)
    xmotivo: Optional[str] = Field(default=None, max_length=255)
    nprot: Optional[str] = Field(default=None, max_length=15)
    dhrecbto: Optional[str] = Field(default=None, max_length=25)
    xml_completo: Optional[str] = Field(default=None, sa_column=Column(Text))

class NfeItem(SQLModel, table=True):
    __tablename__ = "nfe_item"
    id: str = Field(default_factory=gerar_uuid, primary_key=True, max_length=36)
    nfe_id: str = Field(foreign_key="nfe.id", max_length=36)
    produto_id: str = Field(foreign_key="produto.id", max_length=36)
    nitem: int
    cprod: str = Field(max_length=60)
    cean: Optional[str] = Field(default=None, max_length=14)
    xprod: str = Field(max_length=120)
    ncm: str = Field(max_length=8)
    cest: Optional[str] = Field(default=None, max_length=7)
    cfop: str = Field(max_length=4)
    ucom: str = Field(max_length=6)
    qcom: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    vuncom: Decimal = Field(sa_column=Column(Numeric(15, 10)))
    vprod: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    ceantrib: Optional[str] = Field(default=None, max_length=14)
    utrib: str = Field(max_length=6)
    qtrib: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    vuntrib: Decimal = Field(sa_column=Column(Numeric(15, 10)))
    indtot: str = Field(default="1", max_length=1)
    vitem: Decimal = Field(sa_column=Column(Numeric(15, 2)))

class NfeItemImposto(SQLModel, table=True):
    __tablename__ = "nfe_item_imposto"
    id: str = Field(default_factory=gerar_uuid, primary_key=True, max_length=36)
    nfe_item_id: str = Field(foreign_key="nfe_item.id", unique=True, max_length=36)
    
    icms_orig: str = Field(default="0", max_length=1)
    icms_cst: str = Field(default="102", max_length=3)
    icms_vbc: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    icms_picms: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0.0000")))
    icms_vicms: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))

    pis_cst: str = Field(default="07", max_length=2)
    pis_vbc: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    pis_ppis: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0.0000")))
    pis_vpis: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))

    cofins_cst: str = Field(default="07", max_length=2)
    cofins_vbc: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    cofins_pcofins: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0.0000")))
    cofins_vcofins: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))

    ibscbs_cst: str = Field(default="000", max_length=3)
    ibscbs_cclasstrib: str = Field(default="000001", max_length=6)
    ibscbs_vbc: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    ibs_pibsuf: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0.0000")))
    ibs_vibsuf: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    ibs_pibsmun: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0.0000")))
    ibs_vibsmun: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    ibs_vibs: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    cbs_pcbs: Decimal = Field(sa_column=Column(Numeric(7, 4), default=Decimal("0.0000")))
    cbs_vcbs: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))

class NfePagamento(SQLModel, table=True):
    __tablename__ = "nfe_pagamento"
    id: str = Field(default_factory=gerar_uuid, primary_key=True, max_length=36)
    nfe_id: str = Field(foreign_key="nfe.id", max_length=36)
    indpag: str = Field(default="0", max_length=1)
    tpag: str = Field(default="01", max_length=2)
    vpag: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    vtroco: Decimal = Field(sa_column=Column(Numeric(15, 2), default=Decimal("0.00")))
    tpintegra: Optional[str] = Field(default=None, max_length=1)
    cnpj_credenciadora: Optional[str] = Field(default=None, max_length=14)
    tband: Optional[str] = Field(default=None, max_length=2)
    caut: Optional[str] = Field(default=None, max_length=20)

from sqlalchemy import LargeBinary

class Usuario(SQLModel, table=True):
    __tablename__ = "usuarios"

    id_usuario: Optional[int] = Field(default=None, primary_key=True)
    usua_nome: Optional[str] = Field(default=None, max_length=50, index=True)
    usua_cliente: Optional[int] = Field(default=None)
    usua_grupo_geral: Optional[str] = Field(default=None, max_length=20)
    usua_grupo_pdv: Optional[str] = Field(default=None, max_length=20)
    usua_senha: Optional[str] = Field(default=None, max_length=20)
    data_cadastro: Optional[datetime] = Field(default_factory=datetime.now)
    ult_gravacao: Optional[datetime] = Field(default_factory=datetime.now)
    lembrete: Optional[str] = Field(default=None, max_length=100)
    dias_validade: Optional[int] = Field(default=None)
    validade_senha: Optional[datetime] = Field(default=None)
    usua_foto: Optional[bytes] = Field(default=None, sa_column=Column(LargeBinary))
    usua_obs: Optional[bytes] = Field(default=None, sa_column=Column(LargeBinary))
    situacao: Optional[str] = Field(default="A", max_length=1) # 'A'=Ativo, 'I'=Inativo
    usua_config1: Optional[bytes] = Field(default=None, sa_column=Column(LargeBinary))
    modelonfe: Optional[str] = Field(default="65", max_length=2)
    nivel: Optional[str] = Field(default="1", max_length=1)
    alterar_qtde: Optional[str] = Field(default="S", max_length=1)

class LoginInput(BaseModel):
    usua_nome: str
    grupo: str
    usua_senha: str

class Suprimento(SQLModel, table=True):
    __tablename__ = "suprimento"
    id: Optional[int] = Field(default=None, primary_key=True)
    terminal_id: str = Field(index=True)
    operador: str
    gerente_autorizador: Optional[str] = None
    data_suprimento: datetime = Field(default_factory=datetime.now)
    valor: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)

class Sangria(SQLModel, table=True):
    __tablename__ = "sangria"
    id: Optional[int] = Field(default=None, primary_key=True)
    terminal_id: str = Field(index=True)
    operador: str
    gerente_autorizador: Optional[str] = None
    data_sangria: datetime = Field(default_factory=datetime.now)
    valor: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)

class MovCaixaPayload(SQLModel):
    terminal_id: str
    operador: str
    gerente_autorizador: Optional[str] = None
    valor: Decimal
