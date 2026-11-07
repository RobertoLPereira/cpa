from sqlmodel import Session, create_engine
from .config import settings  # Importa a instância centralizada

# Injeta a URL sem variáveis mágicas ou fallbacks soltos no código
engine = create_engine(
    settings.DATABASE_URL_MYSQL,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=settings.DEBUG  # Mostra o SQL no terminal se DEBUG for True
)

def init_db() -> None:
    from sqlmodel import SQLModel
    import backend.apis.mysql.orm.models  # Garante que os modelos sejam carregados antes da criação
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
