import xml.etree.ElementTree as ET

NS_NFE = "http://" + "www.portalfiscal.inf.br" + "/nfe"

def fmt_2(val):
    return f"{float(val or 0):.2f}"

def fmt_4(val):
    return f"{float(val or 0):.4f}"

def fmt_10(val):
    return f"{float(val or 0):.10f}"

def add_el(parent, tag, text=None):
    if text is None:
        return None
    el = ET.SubElement(parent, tag)
    el.text = str(text)
    return el

def calcular_dv_chave(chave_43):
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    for i, digito in enumerate(reversed(chave_43)):
        soma += int(digito) * pesos[i % 8]
    resto = soma % 11
    dv = 11 - resto
    return '0' if dv >= 10 else str(dv)

def gerar_chave_acesso(nfe, emit):
    if nfe['chnfe'] and len(nfe['chnfe']) == 44:
        return nfe['chnfe'], nfe['cdv']
    
    aamm = nfe['dhemi'][2:4] + nfe['dhemi'][5:7]
    cnpj = emit['cnpj'].zfill(14)
    mod = str(nfe['modelo']).zfill(2)
    serie = str(nfe['serie']).zfill(3)
    nnf = str(nfe['nnf']).zfill(9)
    tpemis = str(nfe['tpemis'])
    cnf = str(nfe['cnf']).zfill(8)
    
    chave_43 = f"{nfe['cuf']}{aamm}{cnpj}{mod}{serie}{nnf}{tpemis}{cnf}"
    cdv = calcular_dv_chave(chave_43)
    return chave_43 + cdv, cdv

def montar_cabecalho(inf_nfe, nfe, emit, dest, cdv):
    # Grupo <ide>
    ide = ET.SubElement(inf_nfe, "ide")
    add_el(ide, "cUF", nfe['cuf'])
    add_el(ide, "cNF", str(nfe['cnf']).zfill(8))
    add_el(ide, "natOp", nfe['natop'])
    add_el(ide, "mod", nfe['modelo'])
    add_el(ide, "serie", nfe['serie'])
    add_el(ide, "nNF", nfe['nnf'])
    add_el(ide, "dhEmi", nfe['dhemi'])
    if nfe['modelo'] == '55' and nfe['dhsaient']:
        add_el(ide, "dhSaiEnt", nfe['dhsaient'])
    add_el(ide, "tpNF", nfe['tpnf'])
    add_el(ide, "idDest", nfe['iddest'])
    add_el(ide, "cMunFG", nfe['cmunfg'])
    add_el(ide, "tpImp", nfe['tpimp'])
    add_el(ide, "tpEmis", nfe['tpemis'])
    if nfe['tpemis'] == '9':
        add_el(ide, "dhCont", nfe['dhcont'])
        add_el(ide, "xJust", nfe['xjust'])
    add_el(ide, "cDV", cdv)
    add_el(ide, "tpAmb", nfe['tpamb'])
    add_el(ide, "finNFe", nfe['finnfe'])
    add_el(ide, "indFinal", nfe['indfinal'])
    add_el(ide, "indPres", nfe['indpres'])
    add_el(ide, "procEmi", nfe['procemi'] or "0")
    add_el(ide, "verProc", nfe['verproc'] or "PDV_PYTHON_1.0")

    # Grupo <emit>
    el_emit = ET.SubElement(inf_nfe, "emit")
    add_el(el_emit, "CNPJ", emit['cnpj'])
    add_el(el_emit, "xNome", emit['xnome'])
    if emit['xfant']:
        add_el(el_emit, "xFant", emit['xfant'])
    
    ender_emit = ET.SubElement(el_emit, "enderEmit")
    add_el(ender_emit, "xLgr", emit['xlgr'])
    add_el(ender_emit, "nro", emit['nro'])
    add_el(ender_emit, "xBairro", emit['xbairro'])
    add_el(ender_emit, "cMun", emit['cmun'])
    add_el(ender_emit, "xMun", emit['xmun'])
    add_el(ender_emit, "UF", emit['uf'])
    add_el(ender_emit, "CEP", emit['cep'])
    add_el(ender_emit, "cPais", "1058")
    add_el(ender_emit, "xPais", "Brasil")
    if emit['fone']:
        add_el(ender_emit, "fone", emit['fone'])
    add_el(el_emit, "IE", emit['ie'])
    add_el(el_emit, "CRT", emit['crt'])

    # Grupo <dest>
    if dest:
        el_dest = ET.SubElement(inf_nfe, "dest")
        doc = dest['cnpj_cpf']
        add_el(el_dest, "CNPJ" if len(doc) == 14 else "CPF", doc)
        
        nome_dest = "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL" if nfe['tpamb'] == '2' else dest['xnome']
        add_el(el_dest, "xNome", nome_dest)

        if nfe['modelo'] == '55' or dest['xlgr']:
            ender_dest = ET.SubElement(el_dest, "enderDest")
            add_el(ender_dest, "xLgr", dest['xlgr'])
            add_el(ender_dest, "nro", dest['nro'])
            add_el(ender_dest, "xBairro", dest['xbairro'])
            add_el(ender_dest, "cMun", dest['cmun'])
            add_el(ender_dest, "xMun", dest['xmun'])
            add_el(ender_dest, "UF", dest['uf'])
            add_el(ender_dest, "CEP", dest['cep'])
            add_el(ender_dest, "cPais", dest['cpais'] or "1058")
            add_el(ender_dest, "xPais", dest['xpais'] or "Brasil")
            if dest['fone']:
                add_el(ender_dest, "fone", dest['fone'])

        add_el(el_dest, "indIEDest", dest['indiedest'])
        if dest['ie'] and dest['indiedest'] == '1':
            add_el(el_dest, "IE", dest['ie'])
