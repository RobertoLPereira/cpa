from typing import Optional

from sqlmodel import Session
from backend.core.database_mysql import obter_conexao

def decompor_codigo_scanner(codigo_lido: str):
    """
    Decompõe o código escaneado no PDV.
    Se for padrão de balança (inicia com 2 e tem 13 dígitos), quebra em ID e Valor.
    Se for um ID curto (menor que 7 caracteres), assume item pesável digitado.
    """
    codigo_str = str(codigo_lido).strip()
    
    if len(codigo_str) == 13 and codigo_str.startswith("2"):
        id_produto = str(int(codigo_str[1:6]))
        valor_embutido = float(codigo_str[6:11]) / 100.0
        return True, id_produto, valor_embutido
        
    if len(codigo_str) < 7:
        return True, codigo_str, None
        
    return False, codigo_str, None

def calcular_item_cupom(session: Session,codigo_lido: str, aliq_base_ibs: float = 0.01, aliq_base_cbs: float = 0.09, qtd_caixa: Optional[float] = None, preco_caixa: Optional[float] = None):
    """
    Realiza a busca atômica na tabela mestre de produtos e calcula a carga
    tributária efetiva baseando-se unicamente nas flags e alíquotas do banco.
    Adequado para marcadores de posição do MySQL (%s).
    """
    eh_balanca, id_busca, valor_etiqueta = decompor_codigo_scanner(codigo_lido)
    
    conn = obter_conexao()
    cursor = conn.cursor()
    
    # Marcador alterado de '?' para '%s' (Padrão MySQL)
    cursor.execute("""
        SELECT nome_produto, ncm, cst_iva_dual, cclass_trib, ind_monofasico, ibpt_fed, ibpt_est, preco_venda
        FROM produtos
        WHERE id_produto = %s;
    """, (id_busca,))
    
    produto = cursor.fetchone()
    conn.close()
    
    # Validação de Item não localizado no cadastro mestre
    if not produto:
        return {
            "status": "REJEITADO",
            "id_produto": id_busca,
            "motivo": f"Código {id_busca} não localizado na Tabela Mestre de Produtos."
        }
        
    # Desempacota os dados da linha da tabela mestre
    nome = produto["nome_produto"]
    ncm = produto["ncm"]
    cst = produto["cst_iva_dual"] if produto["cst_iva_dual"] is not None else "000"
    cclass_trib = produto["cclass_trib"] if produto["cclass_trib"] is not None else "000001"
    ind_mono = produto["ind_monofasico"] if produto["ind_monofasico"] is not None else 0
    
    # Adicionada a conversão explícita para float() para evitar conflito no MySQL
    ibpt_fed = float(produto["ibpt_fed"]) if produto["ibpt_fed"] is not None else 0.0
    ibpt_est = float(produto["ibpt_est"]) if produto["ibpt_est"] is not None else 0.0
    
    preco_venda_cadastro = float(produto["preco_venda"]) if produto["preco_venda"] else 0.0
    
    eh_contingencia_ativa = (qtd_caixa is not None and qtd_caixa > 0 and preco_caixa is not None and preco_caixa > 0)

    # Bloqueia faturamento se o preço for zero E não houver preço de contingência enviado pelo caixa
    if preco_venda_cadastro == 0.0 and valor_etiqueta is None and not eh_contingencia_ativa:
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
        valor_final_item = round(quantidade_peso * preco_venda_final, 2)
        unidade = "UN"
    elif eh_balanca:
        preco_venda_final = preco_venda_cadastro
        if valor_etiqueta is not None:
            valor_final_item = valor_etiqueta
            quantidade_peso = valor_final_item / preco_venda_final if preco_venda_final > 0 else 0.0
        else:
            quantidade_peso = 1.000
            valor_final_item = preco_venda_final * quantidade_peso
        unidade = "KG"
    else:
        preco_venda_final = preco_venda_cadastro
        valor_final_item = preco_venda_final
        quantidade_peso = 1.0
        unidade = "UN"

    if ind_mono == 1:
        aliq_efetiva_ibs = 0.0
        aliq_efetiva_cbs = 0.0
        regime_nome = "Monofásico (Saída com 0%)"
    else:
        aliq_efetiva_ibs = aliq_base_ibs
        aliq_efetiva_cbs = aliq_base_cbs
        regime_nome = "Tributação Regular Integral"

    v_ibs = valor_final_item * aliq_efetiva_ibs
    v_cbs = valor_final_item * aliq_efetiva_cbs
    
    v_ibpt_fed = valor_final_item * (ibpt_fed / 100.0)
    v_ibpt_est = valor_final_item * (ibpt_est / 100.0)

    return {
        "status": "APROVADO",
        "id_produto": id_busca,
        "nome_produto": nome,
        "ncm": ncm,
        "uCom": unidade,
        "qCom": round(quantidade_peso, 3),
        "vUnCom": round(preco_venda_final, 2),
        "vProd": round(valor_final_item, 2),
        "regime": regime_nome,
        "forcou_contingencia": eh_contingencia_ativa,
        "IBSCBS": {
            "CST": str(cst).zfill(3),
            "cClassTrib": str(cclass_trib).zfill(6),
            "vBC": round(valor_final_item, 2),
            "vIBS": round(v_ibs, 2),
            "pIBS": f"{(aliq_efetiva_ibs*100):.4f}",
            "vCBS": round(v_cbs, 2),
            "pCBS": f"{(aliq_efetiva_cbs*100):.4f}"
        },
        "ibpt": {
            "pFed": ibpt_fed,
            "pEst": ibpt_est,
            "vFed": round(v_ibpt_fed, 2),
            "vEst": round(v_ibpt_est, 2)
        }
    }

def dar_baixa_estoque_lote(itens_venda: list):
    """
    Executa a baixa física de inventário na tabela mestre pós-venda.
    """
    conn = obter_conexao()
    cursor = conn.cursor()
    
    try:
        for item in itens_venda:
            id_prod = item["id_produto"]
            qtd_vendida = item["qCom"]
            
            # Marcadores alterados para '%s'
            cursor.execute("""
                UPDATE produtos
                SET estoque_atual = estoque_atual - %s
                WHERE id_produto = %s;
            """, (qtd_vendida, id_prod))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erro ao dar baixa no estoque: {e}")
    finally:
        conn.close()

import xml.etree.ElementTree as ET
from xml.dom import minidom

def generar_string_xml_ibscbs(item: dict) -> str:
    """
    Transforma a memória de cálculo JSON do item em uma string XML estruturada.
    """
    fiscal = item["IBSCBS"]
    ibscbs_xml = ET.Element("IBSCBS")
    ET.SubElement(ibscbs_xml, "CST").text = str(fiscal["CST"])
    ET.SubElement(ibscbs_xml, "cClassTrib").text = str(fiscal["cClassTrib"])
    
    g_ibscbs = ET.SubElement(ibscbs_xml, "gIBSCBS")
    ET.SubElement(g_ibscbs, "vBC").text = f"{fiscal['vBC']:.2f}"
    
    g_ibs_uf = ET.SubElement(g_ibscbs, "gIBSUF")
    ET.SubElement(g_ibs_uf, "pIBSUF").text = f"{float(fiscal['pIBS']):.4f}"
    ET.SubElement(g_ibs_uf, "vIBSUF").text = f"{fiscal['vIBS']:.2f}"
    
    g_ibs_mun = ET.SubElement(g_ibscbs, "gIBSMun")
    ET.SubElement(g_ibs_mun, "pIBSMun").text = "0.0000"
    ET.SubElement(g_ibs_mun, "vIBSMun").text = "0.00"
    
    ET.SubElement(g_ibscbs, "vIBS").text = f"{fiscal['vIBS']:.2f}"
    
    g_cbs = ET.SubElement(g_ibscbs, "gCBS")
    ET.SubElement(g_cbs, "pCBS").text = f"{float(fiscal['pCBS']):.4f}"
    ET.SubElement(g_cbs, "vCBS").text = f"{fiscal['vCBS']:.2f}"
    
    rough_string = ET.tostring(ibscbs_xml, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    xml_formatado = reparsed.toprettyxml(indent="    ")
    
    linhas = xml_formatado.split("\n")
    if linhas[0].startswith("<?xml"):
        linhas = linhas[1:]
        
    return "\n".join(linhas)

def processar_lote_perdas_estorno(lote_perdas: list):
    """
    Processa em lote a lista de produtos perdidos/vencidos com marcadores MySQL.
    """
    conn = obter_conexao()
    cursor = conn.cursor()
    
    aliq_base_ibs = 0.01
    aliq_base_cbs = 0.09
    resultado_lote = []
    
    try:
        for item in lote_perdas:
            id_prod = item["id_produto"]
            qtd_perdida = item["quantidade_perdida"]
            motivo = item["motivo_perda"]
            
            cursor.execute("""
                SELECT nome_produto, ncm, preco_venda as preco_custo, ind_monofasico 
                FROM produtos WHERE id_produto = %s;
            """, (id_prod,))
            
            produto = cursor.fetchone()
            if not produto:
                continue
                
            custo_medio = float(produto["preco_custo"] or 0.0)
            ind_mono = int(produto["ind_monofasico"] or 0)
            
            if ind_mono == 1:
                v_estorno_ibs = 0.0
                v_estorno_cbs = 0.0
                detalhe = "Item Monofásico - Isento de Estorno na Perda"
            else:
                base_calculo_estorno = custo_medio * qtd_perdida
                v_estorno_ibs = base_calculo_estorno * aliq_base_ibs
                v_estorno_cbs = base_calculo_estorno * aliq_base_cbs
                detalhe = f"Estorno calculado sobre Base R$ {base_calculo_estorno:.2f}"
                
            cursor.execute("""
                UPDATE produtos 
                SET estoque_atual = estoque_atual - %s 
                WHERE id_produto = %s;
            """, (qtd_perdida, id_prod))
            
            cursor.execute("""
                INSERT INTO movimentacao_perdas_estoque 
                (id_produto, quantidade_perdida, motivo_perda, valor_estorno_ibs, valor_estorno_cbs)
                VALUES (%s, %s, %s, %s, %s);
            """, (id_prod, qtd_perdida, motivo, v_estorno_ibs, v_estorno_cbs))
            
            resultado_lote.append({
                "id_produto": id_prod,
                "nome": produto["nome_produto"],
                "qtd_baixada": qtd_perdida,
                "motivo": motivo,
                "cClassTrib": "410030",
                "vEstornoIBS": round(v_estorno_ibs, 2),
                "vEstornoCBS": round(v_estorno_cbs, 2),
                "status": detalhe
            })
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erro ao processar perdas: {e}")
    finally:
        conn.close()
