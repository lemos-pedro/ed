from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routers import auth, salas, chat, upload
from fastapi.staticfiles import StaticFiles
import os
from routers import auth, salas, chat, livekit

os.makedirs("uploads", exist_ok=True)

app = FastAPI(
    title="ED Chat",
    description="Sistema de chat por salas com autenticação",
    version="1.0.0"
)

# ─── CORS ────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chat.drucciacessorios.pt",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)─ Criar tabelas na BD ─────────────────────────────

@app.on_event("startup")
async def startup():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Tabelas verificadas/criadas com sucesso!")
    except Exception as e:
        print(f"⚠️  Não foi possível conectar à base de dados: {e}")
        print("   O servidor vai continuar, mas sem BD.")

# ─── Routers ─────────────────────────────────────────

app.include_router(auth.router)
app.include_router(salas.router)
app.include_router(chat.router)
app.include_router(upload.router)
app.include_router(livekit.router)


app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ─── Rota de teste ───────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    return {"mensagem": "ED Chat API está online"}