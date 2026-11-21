from datetime import datetime
from http.client import HTTPException

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select
from backend.apis.mysql.orm.database_unificado import get_session
from backend.models.model_unificado import Emitente, LoginInput, NfeNumeracao, Produto, Usuario
from backend.apis.mysql.orm.config import settings

usuario_router = APIRouter(prefix="/api/v1/auth", tags=["Autenticação"])
@usuario_router.post("/login")
def autenticar_operador(dados: LoginInput, session: Session = Depends(get_session)):
    nome_in = dados.usua_nome.strip()
    grupo_in = dados.grupo.strip()
    senha_in = dados.usua_senha.strip()

    # 1. Validação do Nome do Usuário (case-insensitive)
    usuario = session.exec(
        select(Usuario).where(func.upper(Usuario.usua_nome) == nome_in.upper(),
                func.upper(Usuario.usua_grupo_geral) == grupo_in.upper())
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail={
                "campo": "usua_nome",
                "mensagem": f"Usuário '{nome_in}' não foi encontrado no cadastro."
            }
        )

    # 2. Validação da Situação do Cadastro (Bloqueado / Inativo)
    if usuario.situacao and usuario.situacao.upper() != "A":
        raise HTTPException(
            status_code=403,
            detail={
                "campo": "situacao",
                "mensagem": f"O usuário '{usuario.usua_nome}' está INATIVO ou BLOQUEADO (Situação: {usuario.situacao})."
            }
        )

    # 3. Validação do Grupo (confere contra usua_grupo_pdv ou usua_grupo_geral)
    grupo_pdv = (usuario.usua_grupo_pdv or "").strip().upper()
    grupo_geral = (usuario.usua_grupo_geral or "").strip().upper()

    if grupo_in.upper() not in (grupo_pdv, grupo_geral):
        raise HTTPException(
            status_code=401,
            detail={
                "campo": "grupo",
                "mensagem": f"O grupo '{grupo_in}' não confere com o grupo '{grupo_geral}' vinculado ao usuário '{usuario.usua_nome}'."
            }
        )

    # 4. Validação da Senha
    if (usuario.usua_senha or "") != senha_in:
        dica = f" (Lembrete: {usuario.lembrete})" if usuario.lembrete else ""
        raise HTTPException(
            status_code=401,
            detail={
                "campo": "usua_senha",
                "mensagem": f"Senha incorreta para o usuário '{usuario.usua_nome}'.{dica}"
            }
        )

    # 5. Validação da Validade da Senha (se configurada)
    if usuario.validade_senha and usuario.validade_senha < datetime.now():
        raise HTTPException(
            status_code=403,
            detail={
                "campo": "validade_senha",
                "mensagem": f"A senha do usuário '{usuario.usua_nome}' expirou em {usuario.validade_senha.strftime('%d/%m/%Y')}. Solicite renovação."
            }
        )
        # 6. Trava de Prontidão do Banco para Grupo CAIXA
    if grupo_in.upper() == "CAIXA":
        tem_emitente = session.exec(select(Emitente)).first()
        tem_produto = session.exec(select(Produto)).first()
        tem_numeracao = session.exec(select(NfeNumeracao)).first()

        pendencias = []
        if not tem_emitente:
            pendencias.append("Cadastro do Emitente (Loja)")
        if not tem_produto:
            pendencias.append("Catálogo de Produtos")
        if not tem_numeracao:
            pendencias.append("Controle de Numeração/Séries")

        if pendencias:
            lista_str = ", ".join(pendencias)
            raise HTTPException(
                status_code=403,
                detail={
                    "campo": "grupo",
                    "mensagem": (
                        f"Acesso negado ao grupo CAIXA: o sistema ainda não foi inicializado. "
                        f"Pendências: {lista_str}. Solicite ao Administrador ou Suporte para configurar na Retaguarda."
                    )
                }
            )

    # Sucesso: Retorna dados e permissões do operador para a sessão do PDV
    return {
        "status": "sucesso",
        "mensagem": f"Acesso liberado! Bem-vindo(a), {usuario.usua_nome}.",
        "operador": {
            "id_usuario": usuario.id_usuario,
            "usua_nome": usuario.usua_nome,
            "grupo_pdv": usuario.usua_grupo_pdv,
            "grupo_geral": usuario.usua_grupo_geral,
            "nivel": usuario.nivel,
            "modelonfe": usuario.modelonfe or "65",
            "alterar_qtde": usuario.alterar_qtde or "S"
        }
    }

@usuario_router.get("/config-login")
def obter_config_login(session: Session = Depends(get_session)):
    """Retorna a loja na tabela emitente (se inicializada) e os terminais do .env."""
    emit = session.exec(select(Emitente)).first()
    total_cx = settings.TOTAL_CAIXAS_LOJA or 5

    terminais = [
        {"codigo": f"CAIXA-{str(i).zfill(2)}", "serie": str(i), "label": f"Caixa {str(i).zfill(2)} (PDV)"}
        for i in range(1, total_cx + 1)
    ]
    terminais.append({"codigo": "RETAGUARDA", "serie": "100", "label": "Terminal Retaguarda / Gerência"})

    return {
        "inicializado": emit is not None,
        "emitente": {
            "id": emit.id,
            "cnpj": emit.cnpj,
            "razao": emit.xnome
        } if emit else None,
        "terminais": terminais
    }
