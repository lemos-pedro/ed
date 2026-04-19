from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db
from models import User, Sala, Mensagem
from auth import verificar_token
from typing import Dict, List
from datetime import datetime

router = APIRouter(prefix="/chat", tags=["Chat"])

# ─── Gestor de conexões por sala ─────────────────────

class ConnectionManager:
    def __init__(self):
        # { sala_id: [ (websocket, user) ] }
        self.salas: Dict[int, List[tuple]] = {}

    async def connect(self, sala_id: int, websocket: WebSocket, user: User):
        await websocket.accept()
        if sala_id not in self.salas:
            self.salas[sala_id] = []
        self.salas[sala_id].append((websocket, user))

    def disconnect(self, sala_id: int, websocket: WebSocket):
        if sala_id in self.salas:
            self.salas[sala_id] = [
                (ws, u) for ws, u in self.salas[sala_id] if ws != websocket
            ]

    async def broadcast(self, sala_id: int, mensagem: dict):
        if sala_id in self.salas:
            for websocket, _ in self.salas[sala_id]:
                await websocket.send_json(mensagem)


manager = ConnectionManager()


# ─── WebSocket do chat ───────────────────────────────

@router.websocket("/ws/{sala_id}")
async def chat_websocket(
    sala_id: int,
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    # verificar token
    try:
        token_data = verificar_token(token)
    except HTTPException:
        await websocket.close(code=1008)
        return

    # verificar utilizador
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    if not user:
        await websocket.close(code=1008)
        return

    # verificar se o utilizador pertence à sala
    if user.sala_id != sala_id:
        await websocket.close(code=1008)
        return

    # verificar se a sala existe
    result = await db.execute(select(Sala).where(Sala.id == sala_id))
    sala = result.scalar_one_or_none()
    if not sala:
        await websocket.close(code=1008)
        return

    # conectar
    await manager.connect(sala_id, websocket, user)

    # avisar todos que o utilizador entrou
    await manager.broadcast(sala_id, {
        "tipo": "sistema",
        "mensagem": f"{user.nome} entrou na sala.",
        "hora": datetime.utcnow().isoformat()
    })

    try:
        while True:
            data = await websocket.receive_text()

            # guardar mensagem na base de dados
            nova_mensagem = Mensagem(
                conteudo=data,
                user_id=user.id,
                sala_id=sala_id
            )
            db.add(nova_mensagem)
            await db.commit()
            await db.refresh(nova_mensagem)

            # enviar para todos na sala
            await manager.broadcast(sala_id, {
                "tipo": "mensagem",
                "user_id": user.id,
                "autor": user.nome,
                "mensagem": data,
                "hora": nova_mensagem.enviada_em.isoformat()
            })

    except WebSocketDisconnect:
        manager.disconnect(sala_id, websocket)
        await manager.broadcast(sala_id, {
            "tipo": "sistema",
            "mensagem": f"{user.nome} saiu da sala.",
            "hora": datetime.utcnow().isoformat()
        })