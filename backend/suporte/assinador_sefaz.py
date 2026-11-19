import hashlib
from lxml import etree
from signxml import XMLSigner, methods
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption

NS_NFE = "http://" + "www.portalfiscal.inf.br" + "/nfe"

def carregar_certificado_pfx(caminho_pfx, senha_pfx):
    """Lê o arquivo .pfx (Certificado A1) e extrai a chave privada e o certificado PEM."""
    with open(caminho_pfx, "rb") as f:
        pfx_data = f.read()
    
    private_key, certificate, _ = pkcs12.load_key_and_certificates(
        pfx_data, senha_pfx.encode("utf-8")
    )
    
    chave_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption()
    )
    cert_pem = certificate.public_bytes(Encoding.PEM)
    return chave_pem, cert_pem

def assinar_xml_nfe(xml_str, caminho_pfx, senha_pfx):
    """
    Assina a tag <infNFe> seguindo o padrão exigido pela SEFAZ:
    - Enveloped Signature
    - Canonicalization C14N 1.0
    - RSA-SHA1 (Padrão atual do Manual de Orientação do Contribuinte - MOC)
    """
    chave_pem, cert_pem = carregar_certificado_pfx(caminho_pfx, senha_pfx)
    
    # Faz o parse removendo espaços em branco inúteis para não invalidar o DigestValue
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_str.encode("utf-8"), parser)
    
    inf_nfe = root.find(f"{{{NS_NFE}}}infNFe")
    id_uri = inf_nfe.attrib["Id"]  # Ex: 'NFe432609...'

    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha1",
        digest_algorithm="sha1",
        c14n_algorithm="http://w3.org"
    )
    
    # Remove prefixo 'ds:' das tags de assinatura (SEFAZ exige <Signature> limpo)
    signer.namespaces = {None: "http://w3.org"}
    
    xml_assinado_root = signer.sign(
        root,
        key=chave_pem,
        cert=cert_pem,
        reference_uri=f"#{id_uri}"
    )

    # Garante que <infNFeSupl> (QR Code da NFC-e) fique APÓS a tag <Signature>
    supl = xml_assinado_root.find(f"{{{NS_NFE}}}infNFeSupl")
    if supl is not None:
        xml_assinado_root.remove(supl)
        xml_assinado_root.append(supl)

    return etree.tostring(xml_assinado_root, encoding="unicode")
# URLs oficiais de QR Code NFC-e (Exemplos RS e SC; podem ser movidas para config no banco)
URLS_QRCODE = {
    "43": {  # Rio Grande do Sul (RS)
        "1": "https://sefaz.rs.gov.br",
        "2": "https://sefaz.rs.gov.br",
        "consulta_1": "www.sefaz.rs.gov.br/nfce/consulta",
        "consulta_2": "www.sefaz.rs.gov.br/nfce/consulta",
    },
    "42": {  # Santa Catarina (SC)
        "1": "https://sef.sc.gov.br",
        "2": "https://sef.sc.gov.br",
        "consulta_1": "sat.sef.sc.gov.br/nfce/consulta",
        "consulta_2": "hom.sat.sef.sc.gov.br/nfce/consulta",
    }
}

def gerar_qrcode_nfce(nfe, emit, xml_assinado_str):
    """
    Gera as strings <qrCode> e <urlChave> para NFC-e (Modelo 65) - Layout 2.00.
    Deve ser chamado APÓS assinar o XML, pois em contingência usa o DigestValue.
    """
    uf = str(nfe["cuf"])
    tpamb = str(nfe["tpamb"])
    tpemis = str(nfe["tpemis"])
    chnfe = nfe["chnfe"]
    
    # Remove zeros à esquerda do ID do CSC (Ex: '000001' -> '1')
    id_csc = str(int(emit["csc_id"]))
    csc_token = emit["csc_token"].strip()

    if tpemis == "1":
        # Emissão Online: chNFe|2|tpAmb|idCSC
        parametros = f"{chnfe}|2|{tpamb}|{id_csc}"
    else:
        # Emissão em Contingência Offline (tpEmis = 9):
        # chNFe|2|tpAmb|diaEmissao|vNF|digValHex|idCSC
        dia_emissao = nfe["dhemi"][8:10]  # Ex: '2026-11-19...' -> '19'
        vnf = f"{float(nfe['vnf']):.2f}"
        
        # Extrai o DigestValue da assinatura e converte para Hexadecimal
        root = etree.fromstring(xml_assinado_str.encode("utf-8"))
        dig_val_b64 = root.find(".//{http://w3.org}DigestValue").text
        dig_val_hex = dig_val_b64.encode("utf-8").hex()
        
        parametros = f"{chnfe}|2|{tpamb}|{dia_emissao}|{vnf}|{dig_val_hex}|{id_csc}"

    # Calcula o Hash SHA-1 em maiúsculo concatenando o CSC Token
    hash_qrcode = hashlib.sha1((parametros + csc_token).encode("utf-8")).hexdigest().upper()

    urls_uf = URLS_QRCODE.get(uf, URLS_QRCODE["43"])
    url_base = urls_uf[tpamb]
    url_chave = urls_uf[f"consulta_{tpamb}"]
    
    url_qrcode_completa = f"{url_base}?p={parametros}|{hash_qrcode}"
    return url_qrcode_completa, url_chave
