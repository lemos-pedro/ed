from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db
from models import User, Sala
from schemas import UserCreate, UserLogin, UserResponse, Token
from auth import hash_senha, verificar_senha, criar_token

router = APIRouter(prefix="/auth", tags=["Autenticação"])

# ─── Registo ─────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(dados: UserCreate, db: AsyncSession = Depends(get_db)):

    # verificar se o email já existe
    result = await db.execute(select(User).where(User.email == dados.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email já registado")

    # verificar se o código da sala existe
    result = await db.execute(select(Sala).where(Sala.codigo == dados.codigo_sala))
    sala = result.scalar_one_or_none()
    if not sala:
        raise HTTPException(status_code=404, detail="Código de sala inválido")

    # criar o utilizador
    novo_user = User(
        nome=dados.nome,
        email=dados.email,
        senha=hash_senha(dados.senha),
        role=dados.role,
        sala_id=sala.id
    )

    db.add(novo_user)
    await db.commit()
    await db.refresh(novo_user)
    return novo_user


# ─── Login ───────────────────────────────────────────

@router.post("/login", response_model=Token)
async def login(dados: UserLogin, db: AsyncSession = Depends(get_db)):

    # verificar se o utilizador existe
    result = await db.execute(select(User).where(User.email == dados.email))
    user = result.scalar_one_or_none()

    if not user or not verificar_senha(dados.senha, user.senha):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorrectos"
        )

    # gerar token
    token = criar_token(data={"sub": str(user.id), "role": user.role})

    return {"access_token": token, "token_type": "bearer"}

# ─── Criar primeiro admin (usar só uma vez) ──────────

@router.post("/setup-admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def setup_admin(dados: UserCreate, db: AsyncSession = Depends(get_db)):

    result = await db.execute(select(User).where(User.role == "admin"))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Admin já existe")

    novo_admin = User(
        nome=dados.nome,
        email=dados.email,
        senha=hash_senha(dados.senha),
        role="admin",
        sala_id=None
    )

    db.add(novo_admin)
    await db.commit()
    await db.refresh(novo_admin)
    return novo_admin