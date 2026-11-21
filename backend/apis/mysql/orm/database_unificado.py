import os
from pathlib import Path
import sys
import pymysql
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel, Session, create_engine
from .config import settings

# 1. Caminho absoluto do SQLite: ao lado do .exe em produção ou na raiz D:\cpa em desenvolvimento
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parents[4]  # orm -> mysql -> apis -> backend -> raiz (cpa)

SQLITE_PATH = BASE_DIR / "pdv_cpa.db"
SQLITE_URL = f"sqlite:///{SQLITE_PATH}"

# 2. Engines (MySQL central via .env + SQLite contingência local)
engine_mysql = create_engine(
    settings.DATABASE_URL_MYSQL,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=settings.DEBUG
)

engine_sqlite = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    echo=settings.DEBUG
)

# Alias 'engine' para manter compatibilidade com scripts legados que importam 'engine'
engine = engine_sqlite

@event.listens_for(engine_sqlite, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

def mysql_online() -> bool:
    """Testa em 2 segundos se o servidor MySQL configurado no .env está acessível."""
    try:
        url = make_url(settings.DATABASE_URL_MYSQL)
        conn = pymysql.connect(
            host=url.host or "localhost",
            user=url.username,
            password=url.password or "",
            port=url.port or 3306,
            connect_timeout=2
        )
        conn.close()
        return True
    except Exception:
        return False

def get_active_engine():
    return engine_mysql if mysql_online() else engine_sqlite

def inicializar_bancos() -> None:
    """Cria exclusivamente as tabelas oficiais do PDV no MySQL e no SQLite."""
    from backend.apis.mysql.orm.models import (
        Caixa, CaixaMovimento, MovimentacaoPerdasEstoque, AuditoriaProdutosFalhas
    )
    from backend.models.model_unificado import (
                Emitente, Destinatario, Produto,
                NfeNumeracao, Nfe, NfeItem, NfeItemImposto, NfePagamento            
            )
    tabelas_oficiais = [
        Emitente.__table__,
        Destinatario.__table__,
        Produto.__table__,
        NfeNumeracao.__table__,
        Nfe.__table__,
        NfeItem.__table__,
        NfeItemImposto.__table__,
        NfePagamento.__table__,
        
    ]

    if mysql_online():
        try:
            url = make_url(settings.DATABASE_URL_MYSQL)
            conn = pymysql.connect(
                host=url.host or "localhost",
                user=url.username,
                password=url.password or "",
                port=url.port or 3306
            )
            cur = conn.cursor()
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{url.database}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            conn.close()
            SQLModel.metadata.create_all(engine_mysql, tables=tabelas_oficiais)
        except Exception as e:
            print(f"[AVISO] Falha ao inicializar MySQL (operando em SQLite): {e}")

    SQLModel.metadata.create_all(engine_sqlite, tables=tabelas_oficiais)

# Alias para manter compatibilidade caso algum arquivo chame init_db()
init_db = inicializar_bancos

def get_session():
    """Entrega sessão ativa (MySQL se online, SQLite se em contingência)."""
    active_engine = get_active_engine()
    with Session(active_engine) as session:
        yield session
