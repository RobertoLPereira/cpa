from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Column, DateTime, Numeric, String, text
from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy.orm import relationship

# 1. TABELA: LOJA (Refletindo o dump real)
class Loja(SQLModel, table=True):
    __tablename__: str = "loja"

    id_loja: int = Field(primary_key=True)
    nome_razao: Optional[str] = Field(default=None, max_length=150)
    fantasia: Optional[str] = Field(default=None, max_length=150)
    cnpj_cpf: Optional[str] = Field(default=None, max_length=20)
    inscr_estadual: Optional[str] = Field(default=None, max_length=20)
    logradouro: Optional[str] = Field(default=None, max_length=150)
    numero: Optional[str] = Field(default=None, max_length=20)
    bairro: Optional[str] = Field(default=None, max_length=100)
    cidade: Optional[str] = Field(default=None, max_length=100)
    uf: Optional[str] = Field(default=None, max_length=2)
    cep: Optional[str] = Field(default=None, max_length=10)
    codigo_municipio: Optional[str] = Field(default=None, max_length=7)

# 3. TABELA: VENDA
class Venda(SQLModel, table=True):
    __tablename__: str = "venda"

    id: Optional[int] = Field(default=None, primary_key=True)
    numero: Optional[int] = Field(default=None)
    data_venda: Optional[datetime] = Field(default=None)
    subtotal: Decimal = Field(sa_column=Column(Numeric(10, 2), default=Decimal("0.00")))
    desconto: Decimal = Field(sa_column=Column(Numeric(10, 2), default=Decimal("0.00")))
    total: Decimal = Field(sa_column=Column(Numeric(10, 2), default=Decimal("0.00")))
    status: Optional[str] = Field(default=None, max_length=20)
    chave_acesso: Optional[str] = Field(default=None, max_length=44)
    status_nfce: Optional[str] = Field(default=None, max_length=20)

# 4. TABELA: VENDA_ITEM
class VendaItem(SQLModel, table=True):
    __tablename__: str = "venda_item"

    id: Optional[int] = Field(default=None, primary_key=True)
    venda_id: Optional[int] = Field(default=None, foreign_key="venda.id")
    id_produto: Optional[str] = Field(default=None, foreign_key="produtos.id_produto", max_length=30)
    descricao: Optional[str] = Field(default=None, max_length=255)
    quantidade: Decimal = Field(sa_column=Column(Numeric(10, 3), default=Decimal("0.000")))
    valor_unitario: Decimal = Field(sa_column=Column(Numeric(10, 2), default=Decimal("0.00")))
    subtotal: Decimal = Field(sa_column=Column(Numeric(10, 2), default=Decimal("0.00")))
    desconto: Decimal = Field(sa_column=Column(Numeric(15, 4), default=Decimal("0.0000")))
    
    # Tributação Legada
    ncm: Optional[str] = Field(default=None, max_length=20)
    cest: Optional[str] = Field(default=None, max_length=20)
    cfop: Optional[str] = Field(default=None, max_length=10)
    
    # Campos da Reforma Tributária (IBS / CBS)
    ibs_cbs_cst: Optional[str] = Field(default=None, max_length=10)
    ibs_cbs_class_trib: Optional[str] = Field(default=None, max_length=20)
    ibs_cbs_base_calculo: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(15, 4)))
    ibs_uf_aliq: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(15, 4)))
    ibs_uf_valor: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(15, 4)))
    ibs_mun_aliq: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(15, 4)))
    ibs_mun_valor: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(15, 4)))
    cbs_aliq: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(15, 4)))
    cbs_valor: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(15, 4)))
    ibs_valor_total: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(15, 4)))

class MovimentacaoPerdasEstoque(SQLModel, table=True):
    __tablename__: str = "movimentacao_perdas_estoque"

    id: Optional[int] = Field(default=None, primary_key=True)
    id_produto: str = Field(foreign_key="produtos.id_produto", max_length=20, nullable=False)
    quantidade_perdida: Decimal = Field(sa_column=Column(Numeric(15, 4), nullable=False))
    motivo_perda: str = Field(max_length=255, nullable=False)
    valor_estorno_ibs: Decimal = Field(sa_column=Column(Numeric(15, 4), default=Decimal("0.0000")))
    valor_estorno_cbs: Decimal = Field(sa_column=Column(Numeric(15, 4), default=Decimal("0.0000")))
    data_movimento: datetime = Field(
        sa_column=Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    )

class Caixa(SQLModel, table=True):
    __tablename__: str = "caixa"

    id: Optional[int] = Field(default=None, primary_key=True)
    pdv_id: Optional[int] = Field(default=None)
    numero_caixa: Optional[int] = Field(default=None)
    usuario_id: Optional[int] = Field(default=None)
    data_abertura: Optional[datetime] = Field(default=None)
    data_fechamento: Optional[datetime] = Field(default=None)
    
    # Precisão monetária blindada com Decimal
    valor_abertura: Decimal = Field(sa_column=Column(Numeric(10, 2), default=Decimal("0.00")))
    valor_fechamento: Decimal = Field(sa_column=Column(Numeric(10, 2), default=Decimal("0.00")))
    valor_sangria: Decimal = Field(sa_column=Column(Numeric(10, 2), default=Decimal("0.00")))
    valor_suprimento: Decimal = Field(sa_column=Column(Numeric(10, 2), default=Decimal("0.00")))
    diferenca: Decimal = Field(sa_column=Column(Numeric(10, 2), default=Decimal("0.00")))
    
    status: Optional[str] = Field(default="ABERTO", max_length=20) # ABERTO, FECHADO
    observacao: Optional[str] = Field(default=None, max_length=255)

    # Relacionamento nativo com as movimentações do caixa
    movimentacoes: List["CaixaMovimento"] = Relationship(
        back_populates="caixa", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class CaixaMovimento(SQLModel, table=True):
    __tablename__: str = "caixa_movimento"

    id: Optional[int] = Field(default=None, primary_key=True)
    caixa_id: Optional[int] = Field(default=None, foreign_key="caixa.id")
    tipo: Optional[str] = Field(default=None, max_length=20) # SUPRIMENTO, SANGRIA, VENDA
    valor: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False, default=Decimal("0.00")))
    observacao: Optional[str] = Field(default=None, max_length=255)
    data_movimento: datetime = Field(
        sa_column=Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    )

    caixa: Caixa = Relationship(back_populates="movimentacoes")

class OaasControleSync(SQLModel, table=True):
    __tablename__: str = "oaas_controle_sync"

    id: Optional[int] = Field(default=None, primary_key=True)
    tabela_afetada: str = Field(max_length=50, nullable=False, description="'produtos' ou 'venda'")
    registro_id: str = Field(max_length=50, nullable=False, description="ID do produto ou da venda")
    status: str = Field(default="P", max_length=1, index=True, description="'P'endente, 'S'incronizado")
    data_modificacao: datetime = Field(
        sa_column=Column(
            DateTime, 
            server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), 
            nullable=False
        )
    )
# Certifique-se de que este bloco exato está colado no final do seu models.py
class AuditoriaProdutosFalhas(SQLModel, table=True):
    __tablename__: str = "auditoria_produtos_falhas"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    id_produto: str = Field(max_length=20, nullable=False)
    falha: str = Field(max_length=255, nullable=False)
    data_log: datetime = Field(
        sa_column=Column(
            DateTime, 
            server_default=text("CURRENT_TIMESTAMP"), 
            nullable=False
        )
    )
from sqlalchemy import Column, Numeric, String, DateTime, text
from typing import Optional, List
from sqlmodel import Field, Relationship, SQLModel

class ProdutosTributos(SQLModel, table=True):
    __tablename__: str = "produtos_tributos"

    id: Optional[int] = Field(default=None, primary_key=True)
    produto_id: str = Field(foreign_key="produtos.id_produto", max_length=20, nullable=False, index=True)
    uf: str = Field(default="RS", max_length=2)
    tipo_operacao: str = Field(default="SAIDA", max_length=20)
    
    # Parâmetros Legados e IVA Dual mapeados estritamente com Decimal
    cfop: Optional[str] = Field(default=None, max_length=10)
    ibs_cbs_cst: Optional[str] = Field(default=None, max_length=10)
    ibs_cbs_class_trib: Optional[str] = Field(default=None, max_length=20)
    
    ibs_uf_aliq: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4)))
    ibs_uf_reducao: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4)))
    ibs_uf_aliq_efetiva: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4)))
    
    ibs_mun_aliq: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4)))
    ibs_mun_reducao: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4)))
    ibs_mun_aliq_efetiva: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4)))
    
    cbs_aliq: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4)))
    cbs_reducao: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4)))
    cbs_aliq_efetiva: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 4)))
    
    ativo: int = Field(default=1)

    # Relacionamento Reverso inverso
    produto: "Produtos" = Relationship(sa_relationship=relationship("backend.apis.mysql.orm.models.Produtos",back_populates="tributos_lista"
    ))


# DENTRO DA SUA CLASSE 'Produtos' ATUAL, INJETE ESTA LINHA:
class Produtos(SQLModel, table=True):
    __tablename__: str = "produtos"    
    
    id_produto: str = Field(primary_key=True, max_length=20)  # Chave primária original (VARCHAR)
    nome_produto: str = Field(max_length=200, nullable=False)
    nome_reduzido: Optional[str] = Field(default=None, max_length=80)
    unm: Optional[str] = Field(default=None, max_length=3)
    
    # Precisão Decimal comercial
    preco_custo: Decimal = Field(sa_column=Column(Numeric(15, 4), nullable=False, default=Decimal("0.0000")))
    preco_venda: Decimal = Field(sa_column=Column(Numeric(15, 4), nullable=False, default=Decimal("0.0000")))
    preco_venda_min: Decimal = Field(sa_column=Column(Numeric(15, 4), nullable=False, default=Decimal("0.0000")))
    estoque_atual: Decimal = Field(sa_column=Column(Numeric(15, 4), nullable=False, default=Decimal("0.0000")))
    estoque_minimo: Decimal = Field(sa_column=Column(Numeric(15, 4), nullable=False, default=Decimal("0.0000")))
    estoque_maximo: Decimal = Field(sa_column=Column(Numeric(15, 4), nullable=False, default=Decimal("0.0000")))

    # Estrutura Fiscal Legada e Injeções do IVA Dual
    cest: Optional[str] = Field(default=None, max_length=10)
    ncm: Optional[str] = Field(default=None, max_length=10)
    #cfop_padrao: Optional[str] = Field(default=None, sa_column=Column("cfop", String(10)))
    cst_icms: Optional[str] = Field(default=None, max_length=4)
    csosn: Optional[str] = Field(default=None, max_length=4)
    
    cst_iva_dual: Optional[str] = Field(default=None, max_length=4)
    cclass_trib: Optional[str] = Field(default=None, max_length=6)
    ind_monofasico: int = Field(default=0)
    ibpt_fed: Decimal = Field(sa_column=Column(Numeric(15, 4), default=Decimal("0.0000")))
    ibpt_est: Decimal = Field(sa_column=Column(Numeric(15, 4), default=Decimal("0.0000")))

    controla_estoque: str = Field(default="S", max_length=1)
    situacao: str = Field(default="A", max_length=1)
    data_cadastro: datetime = Field(sa_column=Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False))
    data_alteracao: datetime = Field(sa_column=Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False))
    
    # Relacionamento nativo de um produto para suas regras tributárias estaduais
    tributos_lista: List[ProdutosTributos] = Relationship(back_populates="produto")
