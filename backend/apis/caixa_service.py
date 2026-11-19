import random
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlmodel import Session, select, or_

from backend.models.model_unificado import (
    Emitente, Destinatario, Produto, NfeNumeracao,
    Nfe, NfeItem, NfeItemImposto, NfePagamento,
    ItemCarrinhoInput, FinalizarVendaInput, agora_iso
)

def simular_item_cupom(session: Session, item_in: ItemCarrinhoInput) -> Dict[str, Any]:
    """
    Consulta o produto pelo EAN (cean) ou Código Interno (cprod).
    Se estiver com preço zerado no legado e o caixa enviou preco_contingencia,
    atualiza o cadastro do produto automaticamente.
    """
    cod = item_in.codigo.strip()
    cod_com_zeros = cod.zfill(18) if cod.isdigit() else cod
    produto = session.exec(
        select(Produto).where(
            or_(Produto.cean == cod, Produto.cprod == cod, Produto.cprod == cod_com_zeros)
        )
    ).first()


    if not produto:
        return {
            "status": "REJEITADO",
            "id_produto": cod,
            "nome_produto": "NAO CADASTRADO",
            "motivo": f"Codigo {cod} nao localizado no cadastro."
        }

    preco_cad = Decimal(str(produto.vuncom or "0"))
    preco_cx = Decimal(str(item_in.preco_contingencia or "0"))
    qtd = Decimal(str(item_in.quantidade or "1"))

    # Regra do legado: Se o cadastro está zerado e não veio preço manual, bloqueia e pede preço no F1
    if preco_cad <= Decimal("0.00") and preco_cx <= Decimal("0.00"):
        return {
            "status": "BLOQUEADO",
            "id_produto": produto.cprod,
            "nome_produto": produto.xprod,
            "motivo": f"Produto '{produto.xprod}' esta com PRECO ZERADO."
        }

    forcou_preco = False
    if preco_cad <= Decimal("0.00") and preco_cx > Decimal("0.00"):
        preco_final = preco_cx
        produto.vuncom = preco_cx
        produto.vuntrib = preco_cx
        produto.atualizado_em = agora_iso()
        session.add(produto)
        session.commit()
        forcou_preco = True
    else:
        preco_final = preco_cx if preco_cx > Decimal("0.00") else preco_cad

    v_prod = (qtd * preco_final).quantize(Decimal("1.00"))

    # Cálculo Reforma Tributária (IBS / CBS)
    if produto.ind_monofasico == 1:
        p_ibs = Decimal("0.0000")
        p_cbs = Decimal("0.0000")
        regime = "Monofasico (0%)"
    else:
        p_ibs = Decimal(str(produto.ibs_pibsuf or "0.1000"))
        p_cbs = Decimal(str(produto.cbs_pcbs or "0.9000"))
        regime = "Tributacao Regular"

    v_ibs = (v_prod * (p_ibs / Decimal("100.00"))).quantize(Decimal("1.00"))
    v_cbs = (v_prod * (p_cbs / Decimal("100.00"))).quantize(Decimal("1.00"))

    # Cálculo IBPT aproximado
    p_fed = Decimal(str(produto.ibpt_fed or "0"))
    p_est = Decimal(str(produto.ibpt_est or "0"))
    v_fed = (v_prod * (p_fed / Decimal("100.00"))).quantize(Decimal("1.00"))
    v_est = (v_prod * (p_est / Decimal("100.00"))).quantize(Decimal("1.00"))

    return {
        "status": "APROVADO",
        "produto_uuid": produto.id,
        "id_produto": produto.cprod,
        "cean": produto.cean,
        "nome_produto": produto.xprod,
        "ncm": produto.ncm,
        "cest": produto.cest,
        "cfop": produto.cfop_padrao,
        "uCom": produto.ucom,
        "qCom": qtd,
        "vUnCom": preco_final.quantize(Decimal("1.00")),
        "vProd": v_prod,
        "regime": regime,
        "forcou_contingencia": forcou_preco,
        "icms": {
            "orig": produto.icms_orig,
            "cst": produto.icms_cst,
            "picms": Decimal(str(produto.icms_picms or "0"))
        },
        "pis": {"cst": produto.pis_cst, "ppis": Decimal(str(produto.pis_ppis or "0"))},
        "cofins": {"cst": produto.cofins_cst, "pcofins": Decimal(str(produto.cofins_pcofins or "0"))},
        "IBSCBS": {
            "CST": str(produto.ibscbs_cst or "000").zfill(3),
            "cClassTrib": str(produto.ibscbs_cclasstrib or "000001").zfill(6),
            "vBC": v_prod,
            "pIBS": p_ibs,
            "vIBS": v_ibs,
            "pCBS": p_cbs,
            "vCBS": v_cbs
        },
        "ibpt": {"vFed": v_fed, "vEst": v_est}
    }

def gravar_venda_fiscal(session: Session, dados: FinalizarVendaInput, itens_calc: List[Dict[str, Any]]) -> str:
    """
    Grava nfe, nfe_item, nfe_item_imposto, nfe_pagamento,
    incrementa nfe_numeracao e baixa o estoque em uma única transação.
    """
    emitente = session.exec(select(Emitente)).first()
    if not emitente:
        raise ValueError("Emitente (loja) nao cadastrado no banco.")

    # 1. Trata Destinatário (F4 - CPF/CNPJ na nota)
    dest_id = None
    if dados.cpf_cnpj_destinatario:
        doc = "".join(filter(str.isdigit, dados.cpf_cnpj_destinatario))
        if doc:
            dest = session.exec(select(Destinatario).where(Destinatario.cnpj_cpf == doc)).first()
            if not dest:
                dest = Destinatario(
                    cnpj_cpf=doc,
                    xnome=(dados.nome_destinatario or "CONSUMIDOR").upper()[:60],
                    indiedest="9",
                    sincronizado=0
                )
                session.add(dest)
                session.flush()
            dest_id = dest.id

    # 2. Reserva próximo número da série na tabela nfe_numeracao
    num_ctrl = session.exec(
        select(NfeNumeracao).where(
            NfeNumeracao.emitente_id == emitente.id,
            NfeNumeracao.modelo == dados.modelo,
            NfeNumeracao.serie == dados.serie
        )
    ).first()

    if not num_ctrl:
        num_ctrl = NfeNumeracao(
            emitente_id=emitente.id,
            terminal_id=dados.terminal_id,
            modelo=dados.modelo,
            serie=dados.serie,
            tpamb="2", # Inicia em Homologação por segurança
            ultimo_nnf=0
        )
        session.add(num_ctrl)
        session.flush()

    num_ctrl.ultimo_nnf += 1
    num_ctrl.atualizado_em = agora_iso()
    session.add(num_ctrl)

    # 3. Calcula Totais Consolidados
    v_prod_tot = sum(i["vProd"] for i in itens_calc)
    v_ibs_tot = sum(i["IBSCBS"]["vIBS"] for i in itens_calc)
    v_cbs_tot = sum(i["IBSCBS"]["vCBS"] for i in itens_calc)
    v_ibpt_tot = sum(i["ibpt"]["vFed"] + i["ibpt"]["vEst"] for i in itens_calc)

    cuf_map = {"RS": "43", "SC": "42", "PR": "41", "SP": "35", "MG": "31"}
    cuf = cuf_map.get(emitente.uf.upper(), "42")
    cnf = str(random.randint(10000000, 99999999))

    nova_nfe = Nfe(
        emitente_id=emitente.id,
        destinatario_id=dest_id,
        status_sefaz="PENDENTE",
        sincronizado=0,
        cuf=cuf,
        cnf=cnf,
        natop="VENDA DE MERCADORIA",
        modelo=dados.modelo,
        serie=dados.serie,
        nnf=num_ctrl.ultimo_nnf,
        cmunfg=emitente.cmun,
        tpimp="4" if dados.modelo == "65" else "1",
        tpamb=num_ctrl.tpamb,
        vprod=v_prod_tot,
        vnf=v_prod_tot,
        vbcibscbs=v_prod_tot,
        vibsuf=v_ibs_tot,
        vibs=v_ibs_tot,
        vcbs=v_cbs_tot,
        infcpl=f"Val Aprox Tributos R$ {v_ibpt_tot:.2f} Fonte IBPT"
    )
    session.add(nova_nfe)
    session.flush()

    # 4. Grava Itens, Impostos e Baixa Estoque
    for idx, item in enumerate(itens_calc, start=1):
        nfe_item = NfeItem(
            nfe_id=nova_nfe.id,
            produto_id=item["produto_uuid"],
            nitem=idx,
            cprod=item["id_produto"],
            cean=item["cean"],
            xprod=item["nome_produto"],
            ncm=item["ncm"],
            cest=item["cest"],
            cfop=item["cfop"],
            ucom=item["uCom"],
            qcom=item["qCom"],
            vuncom=item["vUnCom"],
            vprod=item["vProd"],
            ceantrib=item["cean"],
            utrib=item["uCom"],
            qtrib=item["qCom"],
            vuntrib=item["vUnCom"],
            vitem=item["vProd"]
        )
        session.add(nfe_item)
        session.flush()

        imp = NfeItemImposto(
            nfe_item_id=nfe_item.id,
            icms_orig=item["icms"]["orig"],
            icms_cst=item["icms"]["cst"],
            pis_cst=item["pis"]["cst"],
            cofins_cst=item["cofins"]["cst"],
            ibscbs_cst=item["IBSCBS"]["CST"],
            ibscbs_cclasstrib=item["IBSCBS"]["cClassTrib"],
            ibscbs_vbc=item["IBSCBS"]["vBC"],
            ibs_pibsuf=item["IBSCBS"]["pIBS"],
            ibs_vibsuf=item["IBSCBS"]["vIBS"],
            ibs_vibs=item["IBSCBS"]["vIBS"],
            cbs_pcbs=item["IBSCBS"]["pCBS"],
            cbs_vcbs=item["IBSCBS"]["vCBS"]
        )
        session.add(imp)

        # Baixa o estoque na tabela mestre
        prod_db = session.get(Produto, item["produto_uuid"])
        if prod_db:
            fator = Decimal(str(prod_db.fator_conversao or "1"))
            qtd_baixar = item["qCom"] * fator
            cprod_base = prod_db.cprod.replace("-CX", "").replace("-CD", "")
            prod_estoque = session.exec(select(Produto).where(Produto.cprod == cprod_base)).first() or prod_db
            prod_estoque.estoque_atual = Decimal(str(prod_estoque.estoque_atual or "0")) - qtd_baixar
            prod_estoque.atualizado_em = agora_iso()
            session.add(prod_estoque)

    # 5. Grava Pagamentos
    for pag in dados.pagamentos:
        session.add(NfePagamento(
            nfe_id=nova_nfe.id,
            tpag=pag.tpag,
            vpag=pag.vpag,
            vtroco=pag.vtroco,
            tband=pag.tband,
            caut=pag.caut
        ))

    session.commit()
    return nova_nfe.id
