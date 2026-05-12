from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import User, Sala, Mensagem
from auth import verificar_token
from datetime import datetime
from typing import List, Dict
import os
from uuid import uuid4

router = APIRouter(prefix="/chat", tags=["Chat"])


class ConnectionManager:
    def __init__(self):
        self.salas: Dict[int, List[tuple]] = {}

    async def connect(self, sala_id: int, websocket: WebSocket, user: User):
        await websocket.accept()
        if sala_id not in self.salas:
            self.salas[sala_id] = []
        self.salas[sala_id].append((websocket, user))

    def disconnect(self, sala_id: int, websocket: WebSocket):
        if sala_id in self.salas:
            self.salas[sala_id] = [(ws, u) for ws, u in self.salas[sala_id] if ws != websocket]

    async def broadcast(self, sala_id: int, message: dict, exclude=None):
        """Broadcast para todos exceto o remetente (para evitar duplicação)"""
        if sala_id in self.salas:
            for websocket, user in self.salas[sala_id]:
                if exclude and user.id == exclude:
                    continue
                try:
                    await websocket.send_json(message)
                except:
                    pass


manager = ConnectionManager()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_ficheiro(file: UploadFile = File(...), token: str = Query(...)):
    try:
        token_data = verificar_token(token)
    except:
        raise HTTPException(401, "Token inválido")

    content_type = file.content_type or ""
    if content_type.startswith("image"):
        tipo = "image"
    elif content_type.startswith("video"):
        tipo = "video"
    elif content_type.startswith("audio"):
        tipo = "audio"
    else:
        tipo = "document"

    ext = os.path.splitext(file.filename)[1].lower()
    nome_unico = f"{uuid4()}{ext}"
    caminho = os.path.join(UPLOAD_DIR, nome_unico)

    conteudo = await file.read()
    with open(caminho, "wb") as f:
        f.write(conteudo)

    return {
        "success": True,
        "file_url": f"/uploads/{nome_unico}",
        "file_name": file.filename,
        "file_type": tipo,
        "file_size": len(conteudo)
    }


@router.websocket("/ws/{sala_id}")
async def chat_websocket(
    sala_id: int,
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        token_data = verificar_token(token)
    except:
        await websocket.close(code=1008, reason="Token inválido")
        return

    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if not user or user.sala_id != sala_id:
        await websocket.close(code=1008, reason="Acesso negado")
        return

    result = await db.execute(select(Sala).where(Sala.id == sala_id))
    if not result.scalar_one_or_none():
        await websocket.close(code=1008, reason="Sala não existe")
        return

    await manager.connect(sala_id, websocket, user)
    print(f"✅ {user.nome} conectado à sala {sala_id}")

    # Histórico
    historico = await get_historico(sala_id, db)
    await websocket.send_json({"tipo": "historico", "mensagens": historico})

    # Entrada
    await manager.broadcast(sala_id, {
        "tipo": "sistema",
        "mensagem": f"{user.nome} entrou na sala.",
        "hora": datetime.utcnow().isoformat()
    }, exclude=user.id)

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("tipo") == "typing":
                await manager.broadcast(sala_id, {"tipo": "typing", "autor": user.nome}, exclude=user.id)
                continue

            nova_mensagem = Mensagem(
                conteudo=data.get("conteudo"),
                file_url=data.get("file_url"),
                file_name=data.get("file_name"),
                file_type=data.get("file_type"),
                file_size=data.get("file_size"),
                user_id=user.id,
                sala_id=sala_id
            )

            db.add(nova_mensagem)
            await db.commit()
            await db.refresh(nova_mensagem)

            broadcast_msg = {
                "tipo": "mensagem",
                "id": nova_mensagem.id,
                "user_id": user.id,
                "autor": user.nome,
                "conteudo": nova_mensagem.conteudo,
                "file_url": nova_mensagem.file_url,
                "file_name": nova_mensagem.file_name,
                "file_type": nova_mensagem.file_type,
                "hora": nova_mensagem.enviada_em.isoformat()
            }

            # Broadcast para TODOS EXCETO o remetente
            await manager.broadcast(sala_id, broadcast_msg, exclude=user.id)

    except WebSocketDisconnect:
        manager.disconnect(sala_id, websocket)
        await manager.broadcast(sala_id, {
            "tipo": "sistema",
            "mensagem": f"{user.nome} saiu da sala.",
            "hora": datetime.utcnow().isoformat()
        })
    except Exception as e:
        print(f"❌ Erro no WebSocket: {e}")


async def get_historico(sala_id: int, db: AsyncSession) -> List[dict]:
    result = await db.execute(
        select(
            Mensagem.id,
            Mensagem.conteudo,
            Mensagem.file_url,
            Mensagem.file_name,
            Mensagem.file_type,
            Mensagem.enviada_em,
            User.id.label("user_id"),
            User.nome.label("autor")
        )
        .join(User, Mensagem.user_id == User.id)
        .where(Mensagem.sala_id == sala_id)
        .order_by(Mensagem.enviada_em.asc())
    )

    mensagens = []
    for row in result.mappings():
        msg = dict(row)
        if msg.get("enviada_em"):
            msg["hora"] = msg["enviada_em"].isoformat()
            del msg["enviada_em"]
        mensagens.append(msg)
    return mensagens