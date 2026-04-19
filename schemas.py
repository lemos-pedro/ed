from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum

class RoleEnum(str, Enum):
    admin = "admin"
    user = "user"

# ─── Salas ───────────────────────────────────────────

class SalaCreate(BaseModel):
    nome: str

class SalaResponse(BaseModel):
    id: int
    nome: str
    codigo: str
    criada_em: datetime

    class Config:
        from_attributes = True

# ─── Utilizadores ────────────────────────────────────

class UserCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    codigo_sala: str          # código introduzido no registo
    role: RoleEnum = RoleEnum.user

class UserLogin(BaseModel):
    email: EmailStr
    senha: str

class UserResponse(BaseModel):
    id: int
    nome: str
    email: str
    role: RoleEnum
    sala_id: Optional[int]
    criado_em: datetime

    class Config:
        from_attributes = True

# ─── Token ───────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None

# ─── Mensagens ───────────────────────────────────────

class MensagemResponse(BaseModel):
    id: int
    conteudo: str
    enviada_em: datetime
    user_id: int
    sala_id: int
    autor_nome: str

    class Config:
        from_attributes = True


        