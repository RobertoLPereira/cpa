# src/com/br/rlp/servicos/autenticacao.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class UsuarioAutenticado:
    usuario_id: int
    nome: str
    perfil: str          # 'CAIXA', 'ADMIN', 'SUPORTE'
    modelo_nfe: str      # '55' ou '65'
    alterar_quantidade: bool

class ServicoAutenticacao:
    """Gerencia a validação de acessos e permissões de nível de usuário."""
    def __init__(self, db_connection):
        self.db = db_connection

    def autenticar(self, empresa_id: int, usuario_login: str, senha_digitada: str) -> Optional[UsuarioAutenticado]:
        sql = """
            SELECT codigo, nome, senha, modelonfe, nivel, alterar_qtde 
            FROM login 
            WHERE empresa = %s AND usuario = %s
        """
        with self.db.cursor() as cursor:
            cursor.execute(sql, (empresa_id, usuario_login))
            row = cursor.fetchone()

        if not row or row['senha'] != senha_digitada:
            return None

        # MAPEAMENTO DE PERFIL: Substitui o 'nivel' do Java
        # Se o nível for 'A' (Admin), direciona para a retaguarda, caso contrário vai para o PDV
        nivel_java = str(row['nivel']).upper()
        if nivel_java == "A":
            perfil = "ADMIN"
        elif nivel_java == "S":
            perfil = "SUPORTE"
        else:
            perfil = "CAIXA"

        return UsuarioAutenticado(
            usuario_id=row['codigo'],
            nome=row['nome'],
            perfil=perfil,
            modelo_nfe=row['modelonfe'],
            alterar_quantidade=(row['alterar_qtde'] == "S")
        )