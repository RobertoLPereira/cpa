from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple, List, Dict, Any
import xml.etree.ElementTree as ET
from xml.dom import minidom
from sqlmodel import Session, select
from sqlalchemy.orm import contains_eager
# Garanta que o import está vindo do arquivo oficial unificado:
from backend.apis.mysql.orm.models import Produtos, ProdutosTributos, VendaItem, AuditoriaProdutosFalhas

def decompor_codigo_scanner(codigo_lido: str) -> Tuple[bool, str, Optional[Decimal]]:
    """Decompõe o código escaneado no PDV para balanças ou IDs curtos."""
    codigo_str = str(codigo_lido).strip()
    
    if len(codigo_str) == 13 and codigo_str.startswith("2"):
        id_produto = str(int(codigo_str[1:6]))
        valor_embutido = Decimal(codigo_str[6:11]) / Decimal("100.00")
        return True, id_produto, valor_embutido
        
    if len(codigo_str) < 7:
        return True, codigo_str, None
        
    return False, codigo_str, None


def calcular_item_cupom(
    session: Session,
    codigo_lido: str,
    aliq_base_ibs: Decimal = Decimal("0.01"),
    aliq_base_cbs: Decimal = Decimal("0.09"),
    qtd_caixa: Optional[Decimal] = None,
    preco_caixa: Optional[Decimal] = None
) -> Dict[str, Any]:
    """Calcula os totais e tributação (IBS/CBS) de um item do cupom usando SQLModel."""
    eh_balanca, id_busca, valor_etiqueta = decompor_codigo_scanner(codigo_lido)
    
    # Busca o produto de forma orientada a objetos
    #produto = session.exec(select(Produtos).where(Produtos.id_produto == id_busca)).first()
    query = (
        select(Produtos)
        # 1. Faz o JOIN explícito utilizando a tabela produtos_tributos
        .join(ProdutosTributos, Produtos.id_produto == ProdutosTributos.produto_id)
        .where(Produtos.id_produto == id_busca)
        .where(ProdutosTributos.uf == "RS")              # Filtro parametrizável da UF do PDV
        .where(ProdutosTributos.tipo_operacao == "SAIDA") # Venda comercial
        .where(ProdutosTributos.ativo == 1)               # Regra vigente
        
        # 2. Informa ao SQLAlchemy para aproveitar esse JOIN e não gerar subconsultas secundárias
        .options(contains_eager(Produtos.tributos_lista))
    )

    produto = session.exec(query).first()
    
    if not produto:
        return {
            "status": "REJEITADO",
            "id_produto": id_busca,
            "motivo": f"Código {id_busca} não localizado na Tabela Mestre de Produtos."
        }
    # 2. Captura a primeira regra fiscal válida retornada pelo JOIN (produtos_tributos_1)
    if produto.tributos_lista:
        regra_fiscal = produto.tributos_lista[0]
        
        # Captura dinâmica do CFOP vindo diretamente do JOIN (produtos_tributos_1.cfop)
        cfop_final = regra_fiscal.cfop if regra_fiscal.cfop else "5102"
        
        # Sobrescreve as alíquotas e CSTs para usar os dados da tabela produtos_tributos
        cst = regra_fiscal.ibs_cbs_cst if regra_fiscal.ibs_cbs_cst is not None else "000"
        cclass_trib = regra_fiscal.ibs_cbs_class_trib if regra_fiscal.ibs_cbs_class_trib is not None else "000001"
        aliq_ibs_uf = regra_fiscal.ibs_uf_aliq_efetiva if regra_fiscal.ibs_uf_aliq_efetiva is not None else Decimal("0.0000")
        aliq_cbs = regra_fiscal.cbs_aliq_efetiva if regra_fiscal.cbs_aliq_efetiva is not None else Decimal("0.0000")
    else:
        # Fallback de contingência caso o produto não possua amarração na tabela tributos
        cfop_final = "5102"  # Venda padrão interna
        cst = produto.cst_iva_dual if produto.cst_iva_dual is not None else "000"
        cclass_trib = produto.cclass_trib if produto.cclass_trib is not None else "000001"
        aliq_ibs_uf = produto.ibpt_fed if produto.ibpt_fed is not None else Decimal("0.0000")
        aliq_cbs = Decimal("0.0000")

    nome = produto.nome_produto
    ncm = produto.ncm
    cst = produto.cst_iva_dual if produto.cst_iva_dual is not None else "000"
    cclass_trib = produto.cclass_trib if produto.cclass_trib is not None else "000001"
    ind_mono = produto.ind_monofasico
    
    ibpt_fed = produto.ibpt_fed if produto.ibpt_fed is not None else Decimal("0.0000")
    ibpt_est = produto.ibpt_est if produto.ibpt_est is not None else Decimal("0.0000")
    preco_venda_cadastro = produto.preco_venda
    
    eh_contingencia_ativa = (qtd_caixa is not None and qtd_caixa > 0 and preco_caixa is not None and preco_caixa > 0)

    # Bloqueia se o preço for zero E não houver preço de contingência enviado pelo caixa
    if preco_venda_cadastro == Decimal("0.0000") and valor_etiqueta is None and not eh_contingencia_ativa:
        return {
            "status": "BLOQUEADO",
            "id_produto": id_busca,
            "nome_produto": nome,
            "motivo": f"Produto '{nome}' está com PREÇO ZERADO no cadastro mestre."
        }

    # Definição matemática do valor final e quantidade baseada no canal de venda
    if eh_contingencia_ativa:
        preco_venda_final = preco_caixa
        quantidade_peso = qtd_caixa
        valor_final_item = (quantidade_peso * preco_venda_final).quantize(Decimal("1.00"))
        unidade = "UN"
    elif eh_balanca:
        preco_venda_final = preco_venda_cadastro
        if valor_etiqueta is not None:
            valor_final_item = valor_etiqueta
            quantidade_peso = (valor_final_item / preco_venda_final).quantize(Decimal("1.000")) if preco_venda_final > 0 else Decimal("0.000")
        else:
            quantidade_peso = Decimal("1.000")
            valor_final_item = (preco_venda_final * quantidade_peso).quantize(Decimal("1.00"))
        unidade = "KG"
    else:
        preco_venda_final = preco_venda_cadastro
        valor_final_item = preco_venda_final.quantize(Decimal("1.00"))
        quantidade_peso = Decimal("1.000")
        unidade = "UN"

    if ind_mono == 1:
        aliq_efetiva_ibs = Decimal("0.00")
        aliq_efetiva_cbs = Decimal("0.00")
        regime_nome = "Monofásico (Saída com 0%)"
    else:
        aliq_efetiva_ibs = aliq_base_ibs
        aliq_efetiva_cbs = aliq_base_cbs
        regime_nome = "Tributação Regular Integral"

    v_ibs = (valor_final_item * aliq_efetiva_ibs).quantize(Decimal("1.00"))
    v_cbs = (valor_final_item * aliq_efetiva_cbs).quantize(Decimal("1.00"))
    
    v_ibpt_fed = (valor_final_item * (ibpt_fed / Decimal("100.00"))).quantize(Decimal("1.00"))
    v_ibpt_est = (valor_final_item * (ibpt_est / Decimal("100.00"))).quantize(Decimal("1.00"))

    return {
        "status": "APROVADO",
        "id_produto": id_busca,
        "nome_produto": nome,
        "ncm": ncm,
        "uCom": unidade,
        "qCom": quantidade_peso,
        "vUnCom": preco_venda_final,
        "vProd": valor_final_item,
        "regime": regime_nome,
        "forcou_contingencia": eh_contingencia_ativa,
        "IBSCBS": {
            "CST": str(cst).zfill(3),
            "cClassTrib": str(cclass_trib).zfill(6),
            "vBC": valor_final_item,
            "vIBS": v_ibs,
            "pIBS": aliq_efetiva_ibs,
            "vCBS": v_cbs,
            "pCBS": aliq_efetiva_cbs
        },
        "ibpt": {
            "pFed": ibpt_fed,
            "pEst": ibpt_est,
            "vFed": v_ibpt_fed,
            "vEst": v_ibpt_est
        }
    }


def dar_baixa_estoque_lote(session: Session, itens_venda: list) -> None:
    """
    Executa a baixa física de inventário na tabela mestre pós-venda.
    Garante o cast de tipos para evitar conflitos entre Float e Decimal.
    """
    for item in itens_venda:
        id_prod = item["id_produto"]
        # Garante que a quantidade vendida seja Decimal
        qtd_vendida = Decimal(str(item["qCom"]))
        
        produto = session.exec(select(Produtos).where(Produtos.id_produto == id_prod)).first()
        if produto:
            # Correção do Erro: Força o estoque atual do banco a virar Decimal antes da subtração
            estoque_banco = Decimal(str(produto.estoque_atual or "0.0000"))
            print(f"qtd vendida {qtd_vendida}")
            # Executa a matemática limpa
            produto.estoque_atual = estoque_banco - qtd_vendida
            session.add(produto)
            
    session.commit()

def generar_string_xml_ibscbs(item: Dict[str, Any]) -> str:
    """Transforma a memória de cálculo do item em uma string XML estruturada."""
    fiscal = item["IBSCBS"]
    ibscbs_xml = ET.Element("IBSCBS")
    ET.SubElement(ibscbs_xml, "CST").text = str(fiscal["CST"])
    ET.SubElement(ibscbs_xml, "cClassTrib").text = str(fiscal["cClassTrib"])
    
    g_ibscbs = ET.SubElement(ibscbs_xml, "gIBSCBS")
    ET.SubElement(g_ibscbs, "vBC").text = f"{fiscal['vBC']:.2f}"
    
    g_ibs_uf = ET.SubElement(g_ibscbs, "gIBSUF")
    ET.SubElement(g_ibs_uf, "pIBSUF").text = f"{(fiscal['pIBS'] * 100):.4f}"
    ET.SubElement(g_ibs_uf, "vIBSUF").text = f"{fiscal['vIBS']:.2f}"
    
    g_ibs_mun = ET.SubElement(g_ibscbs, "gIBSMun")
    ET.SubElement(g_ibs_mun, "pIBSMun").text = "0.0000"
    ET.SubElement(g_ibs_mun, "vIBSMun").text = "0.00"
    
    ET.SubElement(g_ibscbs, "vIBS").text = f"{fiscal['vIBS']:.2f}"
    
    g_cbs = ET.SubElement(g_ibscbs, "gCBS")
    ET.SubElement(g_cbs, "pCBS").text = f"{(fiscal['pCBS'] * 100):.4f}"
    ET.SubElement(g_cbs, "vCBS").text = f"{fiscal['vCBS']:.2f}"
    
    rough_string = ET.tostring(ibscbs_xml, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    xml_formatado = reparsed.toprettyxml(indent="    ")
    
    linhas = xml_formatado.split("\n")
    if linhas[0].startswith("<?xml"):
        linhas = linhas[1:]
        
    return "\n".join(linhas)
