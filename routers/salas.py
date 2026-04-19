from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db
from models import Sala, User
from schemas import SalaCreate, SalaResponse
from auth import get_current_admin, get_current_user
import random
import string

router = APIRouter(prefix="/salas", tags=["Salas"])

# ─── Gerar código único ──────────────────────────────

def gerar_codigo(tamanho: int = 6) -> str:
    caracteres = string.ascii_uppercase + string.digits
    return ''.join(random.choices(caracteres, k=tamanho))

# ─── Criar sala (só admin) ───────────────────────────

@router.post("/", response_model=SalaResponse, status_code=status.HTTP_201_CREATED)
async def criar_sala(
    dados: SalaCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    # garantir código único
    while True:
        codigo = gerar_codigo()
        result = await db.execute(select(Sala).where(Sala.codigo == codigo))
        if not result.scalar_one_or_none():
            break

    nova_sala = Sala(
        nome=dados.nome,
        codigo=codigo,
        criado_por_id=admin.id
    )

    db.add(nova_sala)
    await db.commit()
    await db.refresh(nova_sala)
    return nova_sala


# ─── Listar todas as salas (só admin) ───────────────

@router.get("/", response_model=list[SalaResponse])
async def listar_salas(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = await db.execute(select(Sala))
    return result.scalars().all()


# ─── Ver sala do utilizador actual ──────────────────

@router.get("/minha", response_model=SalaResponse)
async def minha_sala(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user.sala_id:
        raise HTTPException(status_code=404, detail="Não estás associado a nenhuma sala")

    result = await db.execute(select(Sala).where(Sala.id == user.sala_id))
    sala = result.scalar_one_or_none()

    if not sala:
        raise HTTPException(status_code=404, detail="Sala não encontrada")

    return sala


# ─── Ver utilizadores de uma sala (só admin) ────────

@router.get("/{sala_id}/usuarios", response_model=list)
async def usuarios_da_sala(
    sala_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = await db.execute(select(User).where(User.sala_id == sala_id))
    usuarios = result.scalars().all()

    return [{"id": u.id, "nome": u.nome, "email": u.email, "role": u.role} for u in usuarios]