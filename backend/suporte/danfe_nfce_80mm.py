import io
import xml.etree.ElementTree as ET
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

NS = {'nfe': 'http://portalfiscal.inf.br'}

PAGAMENTOS_DESC = {
    '01': 'Dinheiro',
    '02': 'Cheque',
    '03': 'Cartao de Credito',
    '04': 'Cartao de Debito',
    '05': 'Credito Loja',
    '10': 'Vale Alimentacao',
    '11': 'Vale Refeicao',
    '15': 'Boleto Bancario',
    '17': 'PIX',
    '90': 'Sem Pagamento',
    '99': 'Outros'
}

def _txt(el, path, default=''):
    if el is None:
        return default
    node = el.find(path, NS)
    return node.text.strip() if node is not None and node.text else default

def _fmt_chave(chave):
    """Formata os 44 dígitos em blocos de 4 separados por espaço."""
    return ' '.join(chave[i:i+4] for i in range(0, len(chave), 4))

def _gerar_imagem_qrcode(url_qrcode):
    qr = qrcode.QRCode(version=1, box_size=4, border=1)
    qr.add_data(url_qrcode)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return ImageReader(buf)

def _draw_center(c, y, texto, font="Helvetica", size=7):
    c.setFont(font, size)
    c.drawCentredString(40 * mm, y, texto)
    return y - (size + 2.5)

def _draw_line(c, y):
    c.setDash(1, 2)
    c.line(3 * mm, y + 2, 77 * mm, y + 2)
    c.setDash()
    return y - 4
def gerar_danfe_nfce_80mm(xml_str, arquivo_saida="danfe_nfce.pdf"):
    """
    Gera o PDF do DANFE NFC-e (80mm) diretamente a partir do XML assinado/autorizado.
    Trata automaticamente layout Online (tpEmis=1) e Contingência Offline (tpEmis=9).
    """
    root = ET.fromstring(xml_str.encode('utf-8'))
    inf_nfe = root.find('.//nfe:infNFe', NS)
    ide = inf_nfe.find('nfe:ide', NS)
    emit = inf_nfe.find('nfe:emit', NS)
    ender = emit.find('nfe:enderEmit', NS)
    dest = inf_nfe.find('nfe:dest', NS)
    itens = inf_nfe.findall('nfe:det', NS)
    tot = inf_nfe.find('.//nfe:total/nfe:ICMSTot', NS)
    pags = inf_nfe.findall('.//nfe:pag/nfe:detPag', NS)
    v_troco = _txt(inf_nfe, './/nfe:pag/nfe:vTroco', '0.00')
    
    supl = root.find('.//nfe:infNFeSupl', NS)
    prot = root.find('.//nfe:protNFe/nfe:infProt', NS)

    chnfe = inf_nfe.attrib.get('Id', '').replace('NFe', '')
    tpemis = _txt(ide, 'nfe:tpEmis', '1')
    tpamb = _txt(ide, 'nfe:tpAmb', '1')

    # Calcula altura dinâmica do papel (Base 155mm + 8mm por item + extra se contingência)
    altura_mm = 160 + (len(itens) * 8) + (25 if tpemis == '9' else 0)
    largura_mm = 80

    c = canvas.Canvas(arquivo_saida, pagesize=(largura_mm * mm, altura_mm * mm))
    y = (altura_mm - 5) * mm

    # 1. CABEÇALHO DO EMITENTE
    cnpj = _txt(emit, 'nfe:CNPJ')
    cnpj_fmt = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    y = _draw_center(c, y, f"CNPJ: {cnpj_fmt}  IE: {_txt(emit, 'nfe:IE')}", "Helvetica-Bold", 7)
    y = _draw_center(c, y, _txt(emit, 'nfe:xNome')[:44], "Helvetica-Bold", 7.5)
    
    end_str = f"{_txt(ender, 'nfe:xLgr')}, {_txt(ender, 'nfe:nro')} - {_txt(ender, 'nfe:xBairro')}"
    y = _draw_center(c, y, end_str[:48], "Helvetica", 6.5)
    y = _draw_center(c, y, f"{_txt(ender, 'nfe:xMun')} - {_txt(ender, 'nfe:UF')}", "Helvetica", 6.5)
    y = _draw_line(c, y)

    y = _draw_center(c, y, "Documento Auxiliar da Nota Fiscal de Consumidor Eletronica", "Helvetica-Bold", 6.5)
    if tpamb == '2':
        y = _draw_center(c, y, "EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL", "Helvetica-Bold", 6.5)

    # ALERTA OBRIGATÓRIO DE CONTINGÊNCIA OFFLINE (tpEmis = 9)
    if tpemis == '9':
        y = _draw_line(c, y)
        y = _draw_center(c, y, "EMITIDA EM CONTINGENCIA", "Helvetica-Bold", 8.5)
        y = _draw_center(c, y, "Pendente de autorizacao", "Helvetica-Bold", 7)

    y = _draw_line(c, y)

    # 2. TABELA DE ITENS
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(3 * mm, y, "COD   DESCRICAO")
    c.drawRightString(77 * mm, y, "QTD  UN  VL.UN   VL.TOTAL")
    y -= 9

    c.setFont("Helvetica", 6.5)
    for det in itens:
        prod = det.find('nfe:prod', NS)
        cod = _txt(prod, 'nfe:cProd')[-6:]
        desc = _txt(prod, 'nfe:xProd')[:34]
        qtd = f"{float(_txt(prod, 'nfe:qCom', '0')):.2f}"
        un = _txt(prod, 'nfe:uCom')
        vun = f"{float(_txt(prod, 'nfe:vUnCom', '0')):.2f}"
        vprod = f"{float(_txt(prod, 'nfe:vProd', '0')):.2f}"

        c.drawString(3 * mm, y, f"{cod} {desc}")
        y -= 8
        c.drawRightString(77 * mm, y, f"{qtd}  {un}  x  {vun}   {vprod}")
        y -= 9

    y = _draw_line(c, y)

    # 3. TOTAIS E FORMAS DE PAGAMENTO
    def _linha_valor(label, valor, bold=False):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 7.5 if bold else 7)
        c.drawString(3 * mm, y, label)
        c.drawRightString(77 * mm, y, f"R$ {float(valor):.2f}")
        y -= 9.5

    c.setFont("Helvetica", 7)
    c.drawString(3 * mm, y, "Qtde. total de itens")
    c.drawRightString(77 * mm, y, str(len(itens)))
    y -= 9

    _linha_valor("Valor total", _txt(tot, 'nfe:vProd', '0'))
    if float(_txt(tot, 'nfe:vDesc', '0')) > 0:
        _linha_valor("Desconto", _txt(tot, 'nfe:vDesc', '0'))
    _linha_valor("VALOR A PAGAR", _txt(tot, 'nfe:vNF', '0'), bold=True)

    y -= 2
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(3 * mm, y, "FORMA DE PAGAMENTO")
    c.drawRightString(77 * mm, y, "VALOR PAGO")
    y -= 8.5

    for p in pags:
        tpag = _txt(p, 'nfe:tPag', '99')
        vpag = _txt(p, 'nfe:vPag', '0')
        _linha_valor(PAGAMENTOS_DESC.get(tpag, 'Outros'), vpag)

    if float(v_troco) > 0:
        _linha_valor("Troco", v_troco)

    y = _draw_line(c, y)

    # 4. CONSULTA CHAVE DE ACESSO E CONSUMIDOR
    y = _draw_center(c, y, "Consulte pela Chave de Acesso em", "Helvetica", 6.5)
    y = _draw_center(c, y, _txt(supl, 'nfe:urlChave', 'www.sefaz.rs.gov.br/nfce/consulta'), "Helvetica-Bold", 6.5)
    y = _draw_center(c, y, _fmt_chave(chnfe), "Helvetica", 6.5)
    y = _draw_line(c, y)

    if dest is not None:
        doc_dest = _txt(dest, 'nfe:CPF') or _txt(dest, 'nfe:CNPJ')
        y = _draw_center(c, y, f"CONSUMIDOR - CPF/CNPJ: {doc_dest}", "Helvetica-Bold", 6.5)
        if _txt(dest, 'nfe:xNome'):
            y = _draw_center(c, y, _txt(dest, 'nfe:xNome')[:42], "Helvetica", 6.5)
    else:
        y = _draw_center(c, y, "CONSUMIDOR NAO IDENTIFICADO", "Helvetica-Bold", 6.5)

    y = _draw_line(c, y)

    # 5. DADOS DA NOTA, PROTOCOLO E QR CODE
    nnf = _txt(ide, 'nfe:nNF').zfill(9)
    serie = _txt(ide, 'nfe:serie').zfill(3)
    dhemi = _txt(ide, 'nfe:dhEmi')
    data_fmt = f"{dhemi[8:10]}/{dhemi[5:7]}/{dhemi[:4]} {dhemi[11:19]}"
    y = _draw_center(c, y, f"NFC-e n. {nnf}  Serie {serie}  {data_fmt}", "Helvetica-Bold", 6.5)

    if prot is not None:
        nprot = _txt(prot, 'nfe:nProt')
        dhrec = _txt(prot, 'nfe:dhRecbto')
        rec_fmt = f"{dhrec[8:10]}/{dhrec[5:7]}/{dhrec[:4]} {dhrec[11:19]}"
        y = _draw_center(c, y, f"Protocolo de Autorizacao: {nprot}", "Helvetica", 6.5)
        y = _draw_center(c, y, f"Data de Autorizacao: {rec_fmt}", "Helvetica", 6.5)

    # Desenha a imagem do QR Code centralizada (35mm x 35mm)
    url_qr = _txt(supl, 'nfe:qrCode')
    if url_qr:
        qr_img = _gerar_imagem_qrcode(url_qr)
        qr_size = 34 * mm
        c.drawImage(qr_img, (40 * mm) - (qr_size / 2), y - qr_size - 2, width=qr_size, height=qr_size)
        y -= (qr_size + 6)

    if tpemis == '9':
        y = _draw_center(c, y, "EMITIDA EM CONTINGENCIA - Via Consumidor", "Helvetica-Bold", 7)

    c.save()
    return arquivo_saida
