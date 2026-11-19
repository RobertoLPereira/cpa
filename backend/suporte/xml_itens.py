import xml.etree.ElementTree as ET
from backend.suporte.xml_helpers import add_el, fmt_2, fmt_4, fmt_10

def montar_itens(inf_nfe, itens, modelo, crt='1', tpamb='2'):
    for idx, item in enumerate(itens, start=1):
        det = ET.SubElement(inf_nfe, "det", {"nItem": str(item['nitem'])})
        prod = ET.SubElement(det, "prod")
        add_el(prod, "cProd", item['cprod'])
        add_el(prod, "cEAN", item['cean'] or "SEM GTIN")
        
        # Regra SEFAZ: Em homologação (tpAmb=2), o 1º item exige este texto literal
        if str(tpamb) == '2' and idx == 1:
            desc_produto = "NOTA FISCAL EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
        else:
            desc_produto = item['xprod']
            
        add_el(prod, "xProd", desc_produto)
        add_el(prod, "NCM", item['ncm'])
        if item['cest']:
            add_el(prod, "CEST", item['cest'])
        if item['cbenef']:
            add_el(prod, "cBenef", item['cbenef'])
        add_el(prod, "CFOP", item['cfop'])
        add_el(prod, "uCom", item['ucom'])
        add_el(prod, "qCom", fmt_4(item['qcom']))
        add_el(prod, "vUnCom", fmt_10(item['vuncom']))
        add_el(prod, "vProd", fmt_2(item['vprod']))
        if item['vdesc'] and float(item['vdesc']) > 0:
            add_el(prod, "vDesc", fmt_2(item['vdesc']))
        if item['voutro'] and float(item['voutro']) > 0:
            add_el(prod, "vOutro", fmt_2(item['voutro']))
        add_el(prod, "cEANTrib", item['ceantrib'] or "SEM GTIN")
        add_el(prod, "uTrib", item['utrib'])
        add_el(prod, "qTrib", fmt_4(item['qtrib']))
        add_el(prod, "vUnTrib", fmt_10(item['vuntrib']))
        add_el(prod, "indTot", item['indtot'] or "1")

        if item['nlote']:
            rastro = ET.SubElement(prod, "rastro")
            add_el(rastro, "nLote", item['nlote'])
            add_el(rastro, "qLote", fmt_4(item['qlote']))
            add_el(rastro, "dFab", item['dfab'])
            add_el(rastro, "dVal", item['dval'])

        montar_impostos_item(det, item, modelo, crt)

        if item['infadprod']:
            add_el(det, "infAdProd", item['infadprod'])

def montar_impostos_item(det, item, modelo, crt='1'):
    imposto = ET.SubElement(det, "imposto")
    
    # 1. ICMS (Mapeia automaticamente CST de compra para CSOSN se CRT == '1' Simples Nacional)
    icms = ET.SubElement(imposto, "ICMS")
    cst_raw = str(item['icms_cst'] or '102')
    
    if str(crt) == '1':
        # Se veio CST 60 (ST) na compra ou CFOP 5405 -> CSOSN 500; senão -> CSOSN 102
        if cst_raw in ('60', '500') or str(item['cfop']) == '5405':
            cst = '500'
        elif cst_raw in ('102', '103', '300', '400'):
            cst = cst_raw
        else:
            cst = '102'
    else:
        cst = cst_raw
    
    if cst == '00':
        icms00 = ET.SubElement(icms, "ICMS00")
        add_el(icms00, "orig", item['icms_orig'] or '0')
        add_el(icms00, "CST", "00")
        add_el(icms00, "modBC", item['icms_modbc'] or '3')
        add_el(icms00, "vBC", fmt_2(item['icms_vbc']))
        add_el(icms00, "pICMS", fmt_4(item['icms_picms']))
        add_el(icms00, "vICMS", fmt_2(item['icms_vicms']))
    elif cst == '51':
        icms51 = ET.SubElement(icms, "ICMS51")
        add_el(icms51, "orig", item['icms_orig'] or '0')
        add_el(icms51, "CST", "51")
        add_el(icms51, "modBC", item['icms_modbc'] or '3')
        add_el(icms51, "pRedBC", fmt_4(item['icms_predbc']))
        add_el(icms51, "vBC", fmt_2(item['icms_vbc']))
        add_el(icms51, "pICMS", fmt_4(item['icms_picms']))
        add_el(icms51, "vICMSOp", fmt_2(item['icms_vicmsop']))
        add_el(icms51, "pDif", fmt_4(item['icms_pdif']))
        add_el(icms51, "vICMSDif", fmt_2(item['icms_vicmsdif']))
        add_el(icms51, "vICMS", fmt_2(item['icms_vicms']))
    elif cst in ('102', '103', '300', '400'):
        icmssn102 = ET.SubElement(icms, "ICMSSN102")
        add_el(icmssn102, "orig", item['icms_orig'] or '0')
        add_el(icmssn102, "CSOSN", cst)
    elif cst == '500':
        icmssn500 = ET.SubElement(icms, "ICMSSN500")
        add_el(icmssn500, "orig", item['icms_orig'] or '0')
        add_el(icmssn500, "CSOSN", "500")

    # 2. IPI (Apenas Mod 55)
    if modelo == '55' and item['ipi_cst']:
        ipi = ET.SubElement(imposto, "IPI")
        add_el(ipi, "cEnq", item['ipi_cenq'] or "999")
        if item['ipi_cst'] in ('00', '49', '50', '99'):
            ipitrib = ET.SubElement(ipi, "IPITrib")
            add_el(ipitrib, "CST", item['ipi_cst'])
            add_el(ipitrib, "vBC", fmt_2(item['ipi_vbc']))
            add_el(ipitrib, "pIPI", fmt_4(item['ipi_pipi']))
            add_el(ipitrib, "vIPI", fmt_2(item['ipi_vipi']))
        else:
            ipint = ET.SubElement(ipi, "IPINT")
            add_el(ipint, "CST", item['ipi_cst'])

    # 3. PIS e 4. COFINS
    pis = ET.SubElement(imposto, "PIS")
    pis_cst = str(item['pis_cst'] or '07')
    if pis_cst in ('01', '02'):
        pisaliq = ET.SubElement(pis, "PISAliq")
        add_el(pisaliq, "CST", pis_cst)
        add_el(pisaliq, "vBC", fmt_2(item['pis_vbc']))
        add_el(pisaliq, "pPIS", fmt_4(item['pis_ppis']))
        add_el(pisaliq, "vPIS", fmt_2(item['pis_vpis']))
    else:
        pisnt = ET.SubElement(pis, "PISNT")
        add_el(pisnt, "CST", pis_cst)

    cofins = ET.SubElement(imposto, "COFINS")
    cof_cst = str(item['cofins_cst'] or '07')
    if cof_cst in ('01', '02'):
        cofaliq = ET.SubElement(cofins, "COFINSAliq")
        add_el(cofaliq, "CST", cof_cst)
        add_el(cofaliq, "vBC", fmt_2(item['cofins_vbc']))
        add_el(cofaliq, "pCOFINS", fmt_4(item['cofins_pcofins']))
        add_el(cofaliq, "vCOFINS", fmt_2(item['cofins_vcofins']))
    else:
        cofnt = ET.SubElement(cofins, "COFINSNT")
        add_el(cofnt, "CST", cof_cst)

    # 5. IBS / CBS (Reforma Tributária)
    if item['ibscbs_cst']:
        ibscbs = ET.SubElement(imposto, "IBSCBS")
        add_el(ibscbs, "CST", item['ibscbs_cst'])
        add_el(ibscbs, "cClassTrib", item['ibscbs_cclasstrib'])
        gibscbs = ET.SubElement(ibscbs, "gIBSCBS")
        add_el(gibscbs, "vBC", fmt_2(item['ibscbs_vbc']))
        
        gibsuf = ET.SubElement(gibscbs, "gIBSUF")
        add_el(gibsuf, "pIBSUF", fmt_4(item['ibs_pibsuf']))
        add_el(gibsuf, "vIBSUF", fmt_2(item['ibs_vibsuf']))
        
        gibsmun = ET.SubElement(gibscbs, "gIBSMun")
        add_el(gibsmun, "pIBSMun", fmt_4(item['ibs_pibsmun']))
        add_el(gibsmun, "vIBSMun", fmt_2(item['ibs_vibsmun']))
        
        add_el(gibscbs, "vIBS", fmt_2(item['ibs_vibs']))
        
        gcbs = ET.SubElement(gibscbs, "gCBS")
        add_el(gcbs, "pCBS", fmt_4(item['cbs_pcbs']))
        add_el(gcbs, "vCBS", fmt_2(item['cbs_vcbs']))
