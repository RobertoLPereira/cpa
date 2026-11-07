from typing import List, Optional

from pydantic import BaseModel


class ItemMMySQL(BaseModel):
    id_produto: str
    nome_produto: str
    ncm: str
    preco_venda: float
    estoque_atual: float
    situacao: str = "A"


class ItemCarrinhoInput(BaseModel):
    codigo: str
    quantidade: float
    preco_contingencia: float

class CarrinhoInput(BaseModel):
    itens_carrinho: List[ItemCarrinhoInput] # Substitui a antiga lista de strings simples

class ItemPerda(BaseModel):
    id_produto: str
    quantidade_perdida: float
    motivo_perda: str

class ItemVendaXML(BaseModel):
    id_produto: str
    valor_venda: float

class NotaInput(BaseModel):
    numero_nota: int
    id_loja: int = 2
    indPres: str = "1"
    cMunFGIBS: Optional[str] = None
    produtos: List[ItemVendaXML]
