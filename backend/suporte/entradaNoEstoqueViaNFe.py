import xml.etree.ElementTree as ET
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta

NS = {'nfe': "http://" + "www.portalfiscal.inf.br" + "/nfe"}

def get_text(element, path, default=None):
    if element is None:
        return default
    found = element.find(path, NS)
    return found.text.strip() if found is not None and found.text else default

def agora_iso():
    fuso_br = timezone(timedelta(hours=-3))
    return datetime.now(fuso_br).strftime('%Y-%m-%dT%H:%M:%S%z')[:-2] + ':00'

def definir_cfop_venda(cfop_compra, icms_cst):
    if cfop_compra in ('5401', '5403', '5405', '6401', '6403') or icms_cst in ('60', '500'):
        return '5405'
    return '5102'

def salvar_ou_atualizar_produto(cursor, dados_prod, qtd_somar_estoque, agora):
    """Insere ou atualiza um registro na tabela produto pelo cprod ou cean."""
    cursor.execute(
        "SELECT id, estoque_atual FROM produto WHERE cprod = ? OR (cean IS NOT NULL AND cean = ?)",
        (dados_prod['cprod'], dados_prod['cean'])
    )
    row = cursor.fetchone()

    if row:
        prod_id = row[0]
        novo_estoque = float(row[1] or 0) + qtd_somar_estoque
        cursor.execute("""
            UPDATE produto SET
                xprod = ?, ncm = ?, cest = ?, cfop_padrao = ?,
                ucom = ?, vuncom = ?, utrib = ?, vuntrib = ?,
                fator_conversao = ?, estoque_atual = ?, atualizado_em = ?
            WHERE id = ?
        """, (
            dados_prod['xprod'], dados_prod['ncm'], dados_prod['cest'], dados_prod['cfop_venda'],
            dados_prod['unidade'], dados_prod['preco_venda'], dados_prod['unidade'], dados_prod['preco_venda'],
            dados_prod['fator_conversao'], novo_estoque, agora, prod_id
        ))
        print(f"[ATUALIZADO] {dados_prod['xprod'][:32]} | EAN: {dados_prod['cean']} | +{qtd_somar_estoque} {dados_prod['unidade']}")
    else:
        prod_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO produto (
                id, cprod, cean, xprod, ncm, cest, cbenef, cfop_padrao,
                ucom, vuncom, ceantrib, utrib, vuntrib,
                fator_conversao, estoque_atual,
                icms_orig, icms_cst, icms_picms,
                pis_cst, pis_ppis, cofins_cst, cofins_pcofins,
                ibscbs_cst, ibscbs_cclasstrib, ibs_pibsuf, cbs_pcbs,
                atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prod_id, dados_prod['cprod'], dados_prod['cean'], dados_prod['xprod'],
            dados_prod['ncm'], dados_prod['cest'], dados_prod['cbenef'], dados_prod['cfop_venda'],
            dados_prod['unidade'], dados_prod['preco_venda'], dados_prod['cean'],
            dados_prod['unidade'], dados_prod['preco_venda'],
            dados_prod['fator_conversao'], qtd_somar_estoque,
            dados_prod['icms_orig'], dados_prod['icms_cst'], dados_prod['icms_picms'],
            dados_prod['pis_cst'], dados_prod['pis_ppis'],
            dados_prod['cofins_cst'], dados_prod['cofins_pcofins'],
            dados_prod['ibscbs_cst'], dados_prod['ibscbs_cclasstrib'],
            dados_prod['ibs_pibsuf'], dados_prod['cbs_pcbs'],
            agora
        ))
        print(f"[NOVO] {dados_prod['xprod'][:32]} | EAN: {dados_prod['cean']} | Preco: R$ {dados_prod['preco_venda']:.2f}")
def importar_xml_compra_e_estoque(caminho_xml, db_path='pdv_cpa.db', margem_lucro=1.40):
    tree = ET.parse(caminho_xml)
    root = tree.getroot()
    inf_nfe = root.find('.//nfe:infNFe', NS)

    if inf_nfe is None:
        print(f"[ERRO] Tag <infNFe> nao encontrada em {caminho_xml}")
        return

    chnfe_atual = inf_nfe.attrib.get('Id', '').replace('NFe', '')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    agora = agora_iso()

    try:
        # 0. Trava contra duplicidade de nota
        cursor.execute("SELECT id FROM nfe WHERE chnfe = ?", (chnfe_atual,))
        if cursor.fetchone():
            print(f"[AVISO] A NF-e {chnfe_atual} ja foi importada anteriormente.")
            return

        # 1. Cadastra ou recupera Emitente (Loja) -> CORREÇÃO DO ERRO DA TUPLA AQUI (row_emit[0])
        dest = inf_nfe.find('nfe:dest', NS)
        ender_dest = dest.find('nfe:enderDest', NS)
        cnpj_loja = get_text(dest, 'nfe:CNPJ') or get_text(dest, 'nfe:CPF')

        cursor.execute("SELECT id FROM emitente WHERE cnpj = ?", (cnpj_loja,))
        row_emit = cursor.fetchone()

        if row_emit:
            emitente_id = row_emit[0]  # <-- Extrai a string do UUID de dentro da tupla!
        else:
            emitente_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO emitente (
                    id, cnpj, xnome, xfant, xlgr, nro, xbairro, cmun, xmun, uf, cep, fone, ie, crt, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                emitente_id, cnpj_loja, get_text(dest, 'nfe:xNome'), get_text(dest, 'nfe:xNome'),
                get_text(ender_dest, 'nfe:xLgr'), get_text(ender_dest, 'nfe:nro'),
                get_text(ender_dest, 'nfe:xBairro'), get_text(ender_dest, 'nfe:cMun'),
                get_text(ender_dest, 'nfe:xMun'), get_text(ender_dest, 'nfe:UF'),
                get_text(ender_dest, 'nfe:CEP'), get_text(ender_dest, 'nfe:fone'),
                get_text(dest, 'nfe:IE'), '1', agora
            ))

        # 2. Processa Itens
        for det in inf_nfe.findall('nfe:det', NS):
            prod = det.find('nfe:prod', NS)
            imposto = det.find('nfe:imposto', NS)

            cprod_forn = get_text(prod, 'nfe:cProd')
            xprod = get_text(prod, 'nfe:xProd')
            ncm = get_text(prod, 'nfe:NCM')
            cest = get_text(prod, 'nfe:CEST')
            cbenef = get_text(prod, 'nfe:cBenef')
            cfop_compra = get_text(prod, 'nfe:CFOP')

            u_com = get_text(prod, 'nfe:uCom', '').upper()
            u_trib = get_text(prod, 'nfe:uTrib', '').upper()
            c_ean = get_text(prod, 'nfe:cEAN')
            c_ean_trib = get_text(prod, 'nfe:cEANTrib')

            ean_cx = c_ean if c_ean and c_ean != 'SEM GTIN' else None
            ean_un = c_ean_trib if c_ean_trib and c_ean_trib != 'SEM GTIN' else None

            q_com = float(get_text(prod, 'nfe:qCom', '1'))
            q_trib = float(get_text(prod, 'nfe:qTrib', '1'))
            v_prod_total = float(get_text(prod, 'nfe:vProd', '0'))

            # Extração Tributária
            icms_node = imposto.find('.//nfe:ICMS/*', NS)
            icms_orig = get_text(icms_node, 'nfe:orig', '0')
            icms_cst = get_text(icms_node, 'nfe:CST') or get_text(icms_node, 'nfe:CSOSN')
            icms_picms = float(get_text(icms_node, 'nfe:pICMS', '0'))

            pis_node = imposto.find('.//nfe:PIS/*', NS)
            pis_cst = get_text(pis_node, 'nfe:CST', '01')
            pis_ppis = float(get_text(pis_node, 'nfe:pPIS', '0'))

            cofins_node = imposto.find('.//nfe:COFINS/*', NS)
            cofins_cst = get_text(cofins_node, 'nfe:CST', '01')
            cofins_pcofins = float(get_text(cofins_node, 'nfe:pCOFINS', '0'))

            ibscbs_node = imposto.find('nfe:IBSCBS', NS)
            ibscbs_cst = get_text(ibscbs_node, 'nfe:CST', '000')
            ibscbs_cclasstrib = get_text(ibscbs_node, 'nfe:cClassTrib', '000001')
            ibs_pibsuf = float(get_text(ibscbs_node, './/nfe:pIBSUF', '0'))
            cbs_pcbs = float(get_text(ibscbs_node, './/nfe:pCBS', '0'))

            cfop_venda = definir_cfop_venda(cfop_compra, icms_cst)

            base_tributos = {
                'ncm': ncm, 'cest': cest, 'cbenef': cbenef, 'cfop_venda': cfop_venda,
                'icms_orig': icms_orig, 'icms_cst': icms_cst, 'icms_picms': icms_picms,
                'pis_cst': pis_cst, 'pis_ppis': pis_ppis,
                'cofins_cst': cofins_cst, 'cofins_pcofins': cofins_pcofins,
                'ibscbs_cst': ibscbs_cst, 'ibscbs_cclasstrib': ibscbs_cclasstrib,
                'ibs_pibsuf': ibs_pibsuf, 'cbs_pcbs': cbs_pcbs
            }

            fator_conv = round(q_trib / q_com, 4) if q_com > 0 else 1.0
            qtd_total_un = q_com * fator_conv

            # REGRA DUPLA: Se uCom for CX ou CD e os EANs forem diferentes, cadastra UN + CX
            if u_com in ('CX', 'CD') and ean_cx and ean_un and ean_cx != ean_un:
                # 1) Cadastro da UNIDADE AVULSA (usa cEANTrib e recebe o saldo físico em unidades)
                custo_un = v_prod_total / qtd_total_un if qtd_total_un > 0 else 0.0
                preco_un = round(custo_un * margem_lucro, 2)
                prod_un = {
                    **base_tributos,
                    'cprod': cprod_forn,
                    'cean': ean_un,
                    'xprod': xprod[:120],
                    'unidade': u_trib if u_trib not in ('CX', 'CD') else 'UN',
                    'preco_venda': preco_un,
                    'fator_conversao': 1.0
                }
                salvar_ou_atualizar_produto(cursor, prod_un, qtd_total_un, agora)

                # 2) Cadastro da CAIXA / DISPLAY FECHADO (usa cEAN, preço da caixa inteira e fator de conversão)
                custo_cx = v_prod_total / q_com if q_com > 0 else 0.0
                preco_cx = round(custo_cx * margem_lucro, 2)
                prod_cx = {
                    **base_tributos,
                    'cprod': f"{cprod_forn}-{u_com}",
                    'cean': ean_cx,
                    'xprod': f"{xprod[:110]} ({u_com})",
                    'unidade': u_com,
                    'preco_venda': preco_cx,
                    'fator_conversao': fator_conv
                }
                # Estoque 0 no registro da caixa para não duplicar o inventário físico (baixa via fator_conversao)
                salvar_ou_atualizar_produto(cursor, prod_cx, 0.0, agora)

            else:
                # REGRA PADRÃO: Registro único
                ean_final = ean_un if (u_com in ('CX', 'CD') and ean_un) else (ean_cx or ean_un)
                unidade_final = u_trib if (u_com in ('CX', 'CD') and u_trib) else u_com
                custo_unit = v_prod_total / qtd_total_un if qtd_total_un > 0 else 0.0
                preco_unit = round(custo_unit * margem_lucro, 2)

                prod_unico = {
                    **base_tributos,
                    'cprod': cprod_forn,
                    'cean': ean_final,
                    'xprod': xprod[:120],
                    'unidade': unidade_final,
                    'preco_venda': preco_unit,
                    'fator_conversao': fator_conv
                }
                salvar_ou_atualizar_produto(cursor, prod_unico, qtd_total_un, agora)

        # 3. Grava Cabeçalho da Nota de Entrada (tpnf = '0')
        ide = inf_nfe.find('nfe:ide', NS)
        icms_tot = inf_nfe.find('.//nfe:total/nfe:ICMSTot', NS)

        cursor.execute("""
            INSERT INTO nfe (
                id, emitente_id, status_sefaz, sincronizado, chnfe, cuf, cnf, natop,
                modelo, serie, nnf, dhemi, tpnf, iddest, cmunfg, tpimp, tpemis, cdv, tpamb,
                vprod, vnf, modfrete
            ) VALUES (?, ?, 'AUTORIZADA', 0, ?, ?, ?, ?, ?, ?, ?, ?, '0', ?, ?, ?, ?, ?, ?, ?, ?, '0')
        """, (
            str(uuid.uuid4()), emitente_id, chnfe_atual,
            get_text(ide, 'nfe:cUF'), get_text(ide, 'nfe:cNF'), get_text(ide, 'nfe:natOp'),
            get_text(ide, 'nfe:mod'), get_text(ide, 'nfe:serie'), int(get_text(ide, 'nfe:nNF')),
            get_text(ide, 'nfe:dhEmi'), get_text(ide, 'nfe:idDest'), get_text(ide, 'nfe:cMunFG'),
            get_text(ide, 'nfe:tpImp'), get_text(ide, 'nfe:tpEmis'), get_text(ide, 'nfe:cDV'),
            get_text(ide, 'nfe:tpAmb'), float(get_text(icms_tot, 'nfe:vProd', '0')),
            float(get_text(icms_tot, 'nfe:vNF', '0'))
        ))

        conn.commit()
        print("\nImportacao concluida com sucesso!")

    except Exception as e:
        conn.rollback()
        print(f"Erro durante a importacao: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    arquivo = r'C:\Users\teste\Downloads\CPA_RADAR_03540677000100_PRODUCAO\03540677000100\2026\09\35260910285622000329550030000666601408603398.xml'
    importar_xml_compra_e_estoque(arquivo, db_path='pdv_cpa.db', margem_lucro=1.40)
