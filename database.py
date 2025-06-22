import os
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, Date, Text,
    ForeignKey, TIMESTAMP, SmallInteger, func, Index
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import create_engine
from dotenv import load_dotenv
from sqlalchemy import BigInteger

# Загружаем переменные окружения из token.env
load_dotenv(dotenv_path="token.env")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

if not all([DB_USER, DB_PASS, DB_NAME]):
    raise RuntimeError("Не заданы переменные окружения DB_USER, DB_PASS или DB_NAME")

# Формируем URL
DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Инициализация SQLAlchemy
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# Хелпер для получения сессии
def get_db():
    """
    Генератор, возвращающий сессию SQLAlchemy.
    Используйте: db = next(get_db()); ...; db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─────────────────── Модели ───────────────────
class User(Base):
    __tablename__ = 'users'
    __table_args__ = (
        Index('uq_users_call_sign', 'call_sign', unique=True),
    )

    id           = Column(Integer, primary_key=True, index=True)
    discord_id   = Column(BigInteger, unique=True, nullable=False, index=True)
    call_sign    = Column(String(64), nullable=False, unique=True, index=True)
    steam_id     = Column(String(32), nullable=True)
    curator_id   = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    black_mark   = Column(Boolean, nullable=False, default=False)

    # связи: куратор и подопечные
    curator = relationship('User', remote_side=[id], backref='mentees')

    # RP-очки: полученные и выданные
    rp_entries = relationship(
        'RPEntry',
        foreign_keys='RPEntry.user_id',
        back_populates='user',
        cascade='all, delete-orphan'
    )
    rp_issued = relationship(
        'RPEntry',
        foreign_keys='RPEntry.issued_by',
        back_populates='issuer',
        cascade='all, delete-orphan'
    )

    # Активность и допросы
    activity_reports = relationship(
        'ActivityReport', back_populates='user', cascade='all, delete-orphan'
    )
    interrogation_reports = relationship(
        'InterrogationReport', back_populates='user', cascade='all, delete-orphan'
    )

    # WARN-уровни: полученные и выданные
    warnings = relationship(
        'Warning',
        foreign_keys='Warning.user_id',
        back_populates='user',
        cascade='all, delete-orphan'
    )
    warnings_issued = relationship(
        'Warning',
        foreign_keys='Warning.issued_by',
        back_populates='issuer',
        cascade='all, delete-orphan'
    )

    # Отпуска
    vacations = relationship(
        'Vacation', back_populates='user', cascade='all, delete-orphan'
    )


class RPEntry(Base):
    __tablename__ = 'rp_entries'
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    amount     = Column(Integer, nullable=False)
    reason     = Column(Text, nullable=False)
    issued_by  = Column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'), nullable=False, index=True)
    issued_at  = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # связи
    user   = relationship(
        'User',
        foreign_keys=[user_id],
        back_populates='rp_entries'
    )
    issuer = relationship(
        'User',
        foreign_keys=[issued_by],
        back_populates='rp_issued'
    )


class ActivityReport(Base):
    __tablename__ = 'activity_reports'
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    document_number           = Column(String(64), nullable=True)
    duties                    = Column(Integer, nullable=False, default=0)
    interviews                = Column(Integer, nullable=False, default=0)
    summary                   = Column(Text, nullable=True)
    self_assessment           = Column(Text, nullable=True)
    specialization_assessment = Column(Text, nullable=True)
    date                      = Column(Date, nullable=False, index=True)
    thread_id                 = Column(BigInteger, nullable=True)

    # связь
    user = relationship('User', back_populates='activity_reports')


class InterrogationReport(Base):
    __tablename__ = 'interrogation_reports'
    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    document_number = Column(String(64), nullable=True)
    date         = Column(Date, nullable=False, index=True)
    participants = Column(Text, nullable=True)
    interrogated = Column(Text, nullable=True)
    reason       = Column(Text, nullable=True)
    content1     = Column(Text, nullable=True)
    content2     = Column(Text, nullable=True)
    content3     = Column(Text, nullable=True)
    verdict      = Column(Text, nullable=True)
    thread_id    = Column(BigInteger, nullable=True)

    # связь
    user = relationship('User', back_populates='interrogation_reports')


class Warning(Base):
    __tablename__ = 'warnings'
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    level      = Column(SmallInteger, nullable=False)
    issued_by  = Column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    issued_at  = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # связи
    user   = relationship(
        'User',
        foreign_keys=[user_id],
        back_populates='warnings'
    )
    issuer = relationship(
        'User',
        foreign_keys=[issued_by],
        back_populates='warnings_issued'
    )


class Vacation(Base):
    __tablename__ = 'vacations'
    id       = Column(Integer, primary_key=True, index=True)
    user_id  = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    start_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    end_at   = Column(TIMESTAMP(timezone=True), nullable=False)
    active   = Column(Boolean, nullable=False, default=True)

    # связь
    user = relationship('User', back_populates='vacations')


def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == '__main__':
    init_db()
    print('📦 Таблицы созданы')
