from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import auth, salas, chat

app = FastAPI(
    title="ED Chat",
    description="Sistema de chat por salas com autenticação",
    version="1.0.0"
)

# ─── CORS ────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Criar tabelas na BD ─────────────────────────────

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ─── Routers ─────────────────────────────────────────

app.include_router(auth.router)
app.include_router(salas.router)
app.include_router(chat.router)

# ─── Rota de teste ───────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    return {"mensagem": "ED Chat API está online"}