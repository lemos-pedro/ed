from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class RoleEnum(str, enum.Enum):
    admin = "admin"
    user = "user"

class Sala(Base):
    __tablename__ = "salas"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    codigo = Column(String(10), unique=True, nullable=False)
    criada_em = Column(DateTime(timezone=True), server_default=func.now())

    criado_por_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    usuarios = relationship("User", back_populates="sala", foreign_keys="User.sala_id")
    mensagens = relationship("Mensagem", back_populates="sala")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    senha = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.user)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    sala_id = Column(Integer, ForeignKey("salas.id"), nullable=True)

    sala = relationship("Sala", back_populates="usuarios", foreign_keys=[sala_id])
    mensagens = relationship("Mensagem", back_populates="autor")


class Mensagem(Base):
    __tablename__ = "mensagens"

    id = Column(Integer, primary_key=True, index=True)
    conteudo = Column(Text, nullable=False)
    enviada_em = Column(DateTime(timezone=True), server_default=func.now())

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sala_id = Column(Integer, ForeignKey("salas.id"), nullable=False)

    autor = relationship("User", back_populates="mensagens")
    sala = relationship("Sala", back_populates="mensagens")

    