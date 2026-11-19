import uuid
import tempfile
import requests
from lxml import etree
from backend.suporte.assinador_sefaz import carregar_certificado_pfx

NS_NFE = "http://" + "www.portalfiscal.inf.br" + "/nfe"
NS_SOAP = "http://w3.org"
NS_WSDL = "http://portalfiscal.inf.br/wsdl/NFeAutorizacao4"

# Endpoints oficiais NFeAutorizacao4 (RS e SVRS - atende SC, PR, etc.)
ENDPOINTS_SEFAZ = {
    # Rio Grande do Sul (cUF = 43)
    ("43", "55", "1"): "https://sefazrs.rs.gov.br",
    ("43", "55", "2"): "https://sefazrs.rs.gov.br",
    ("43", "65", "1"): "https://sefazrs.rs.gov.br",
    ("43", "65", "2"): "https://sefazrs.rs.gov.br",

    # Santa Catarina (cUF = 42 -> Utiliza SVRS)
    ("42", "55", "1"): "https://svrs.rs.gov.br",
    ("42", "55", "2"): "https://svrs.rs.gov.br",
    ("42", "65", "1"): "https://svrs.rs.gov.br",
    ("42", "65", "2"): "https://svrs.rs.gov.br",
}

def montar_envelope_soap(xml_nfe_assinado):
    """
    Envelopa a <NFe> assinada dentro de <enviNFe> (Síncrono: indSinc=1)
    e dentro do envelope SOAP 1.2 exigido pela SEFAZ 4.00.
    """
    id_lote = str(uuid.uuid4().int)[:15]
    
    # Remove declaração <?xml ...?> interna antes de embutir no lote
    xml_limpo = xml_nfe_assinado.replace('<?xml version="1.0" encoding="UTF-8"?>', '').strip()
    xml_limpo = xml_limpo.replace("<?xml version='1.0' encoding='UTF-8'?>", "").strip()

    envelope = (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<soap12:Envelope xmlns:xsi="http://w3.org" '
        f'xmlns:xsd="http://w3.org" '
        f'xmlns:soap12="{NS_SOAP}">'
        f'<soap12:Body>'
        f'<nfeDadosMsg xmlns="{NS_WSDL}">'
        f'<enviNFe xmlns="{NS_NFE}" versao="4.00">'
        f'<idLote>{id_lote}</idLote>'
        f'<indSinc>1</indSinc>'
        f'{xml_limpo}'
        f'</enviNFe>'
        f'</nfeDadosMsg>'
        f'</soap12:Body>'
        f'</soap12:Envelope>'
    )
    return envelope
def montar_nfe_proc(xml_nfe_assinado, prot_nfe_element):
    """
    Une a <NFe> assinada com o <protNFe> autorizado pela SEFAZ,
    gerando o XML final válido juridicamente (<nfeProc>).
    """
    nfe_proc = etree.Element(f"{{{NS_NFE}}}nfeProc", versao="4.00", nsmap={None: NS_NFE})
    nfe_el = etree.fromstring(xml_nfe_assinado.encode("utf-8"))
    nfe_proc.append(nfe_el)
    nfe_proc.append(prot_nfe_element)
    return etree.tostring(nfe_proc, encoding="unicode")

def transmitir_nfe_sefaz(xml_assinado, cuf, modelo, tpamb, caminho_pfx, senha_pfx):
    """
    Envia o lote síncrono (indSinc=1) para a SEFAZ usando Certificado A1.
    Retorna um dicionário padronizado para atualizar o banco de dados do PDV.
    """
    url = ENDPOINTS_SEFAZ.get((str(cuf), str(modelo), str(tpamb)))
    if not url:
        raise ValueError(f"Endpoint não configurado para UF={cuf}, Mod={modelo}, Amb={tpamb}")

    envelope_soap = montar_envelope_soap(xml_assinado)
    chave_pem, cert_pem = carregar_certificado_pfx(caminho_pfx, senha_pfx)

    headers = {
        "Content-Type": f'application/soap+xml; charset=utf-8; action="{NS_WSDL}/nfeAutorizacaoLote"'
    }

    # Cria arquivos temporários seguros para o mTLS do requests
    with tempfile.NamedTemporaryFile(delete=True) as f_cert, tempfile.NamedTemporaryFile(delete=True) as f_key:
        f_cert.write(cert_pem)
        f_cert.flush()
        f_key.write(chave_pem)
        f_key.flush()

        try:
            resp = requests.post(
                url,
                data=envelope_soap.encode("utf-8"),
                headers=headers,
                cert=(f_cert.name, f_key.name),
                timeout=15
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            # Falha de rede / timeout -> PDV pode acionar contingência offline (se Mod 65)
            return {
                "sucesso": False,
                "erro_rede": True,
                "cstat": None,
                "xmotivo": f"Falha de comunicação com a SEFAZ: {str(e)}",
                "nprot": None,
                "dhrecbto": None,
                "xml_autorizado": None
            }

    # Faz o parse do XML de retorno da SEFAZ (<retEnviNFe>)
    root_resp = etree.fromstring(resp.content)
    ns = {"nfe": NS_NFE}

    # Verifica primeiro o status do lote (<retEnviNFe>/<cStat>)
    cstat_lote = root_resp.findtext(".//nfe:retEnviNFe/nfe:cStat", namespaces=ns)
    xmotivo_lote = root_resp.findtext(".//nfe:retEnviNFe/nfe:xMotivo", namespaces=ns)

    # No modo síncrono (indSinc=1), cStat 104 = Lote processado
    prot_nfe = root_resp.find(".//nfe:protNFe", namespaces=ns)
    if prot_nfe is not None:
        inf_prot = prot_nfe.find("nfe:infProt", namespaces=ns)
        cstat = inf_prot.findtext("nfe:cStat", namespaces=ns)
        xmotivo = inf_prot.findtext("nfe:xMotivo", namespaces=ns)
        nprot = inf_prot.findtext("nfe:nProt", namespaces=ns)
        dhrecbto = inf_prot.findtext("nfe:dhRecbto", namespaces=ns)

        # cStat 100 = Autorizado o uso da NF-e | cStat 150 = Autorizado fora de prazo
        if cstat in ("100", "150"):
            xml_proc = montar_nfe_proc(xml_assinado, prot_nfe)
            return {
                "sucesso": True,
                "erro_rede": False,
                "cstat": cstat,
                "xmotivo": xmotivo,
                "nprot": nprot,
                "dhrecbto": dhrecbto,
                "xml_autorizado": xml_proc
            }
        else:
            # Nota rejeitada por regra fiscal (ex: NCM inválido, CFOP incorreto, etc.)
            return {
                "sucesso": False,
                "erro_rede": False,
                "cstat": cstat,
                "xmotivo": xmotivo,
                "nprot": None,
                "dhrecbto": dhrecbto,
                "xml_autorizado": None
            }

    # Caso o lote em si tenha sido rejeitado antes de processar a nota
    return {
        "sucesso": False,
        "erro_rede": False,
        "cstat": cstat_lote,
        "xmotivo": xmotivo_lote,
        "nprot": None,
        "dhrecbto": None,
        "xml_autorizado": None
    }
