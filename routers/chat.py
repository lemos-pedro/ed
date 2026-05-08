from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import User, Sala, Mensagem
from auth import verificar_token
from datetime import datetime
from typing import List, Dict
import os
import uuid
from fastapi import UploadFile, File

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
            self.salas[sala_id] = [
                (ws, u) for ws, u in self.salas[sala_id] if ws != websocket
            ]

    async def broadcast(self, sala_id: int, message: dict):
        if sala_id in self.salas:
            for websocket, _ in self.salas[sala_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    pass


manager = ConnectionManager()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_ficheiro(
    file: UploadFile = File(...),
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        token_data = verificar_token(token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Token inválido")

    # determinar tipo
    content_type = file.content_type or ""
    if content_type.startswith("image"):
        tipo = "image"
    elif content_type.startswith("video"):
        tipo = "video"
    elif content_type.startswith("audio"):
        tipo = "audio"
    else:
        tipo = "document"

    # gerar nome único
    ext = os.path.splitext(file.filename)[1]
    nome_unico = f"{uuid.uuid4()}{ext}"
    caminho = os.path.join(UPLOAD_DIR, nome_unico)

    # guardar ficheiro
    conteudo = await file.read()
    with open(caminho, "wb") as f:
        f.write(conteudo)

    return {
        "url": f"/uploads/{nome_unico}",
        "nome": file.filename,
        "tipo": tipo,
        "tamanho": len(conteudo)
    }
    
@router.websocket("/ws/{sala_id}")
async def chat_websocket(
    sala_id: int,
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
      # ── AUTENTICAÇÃO MELHORADA ─────────────────────────────
    try:
        token_data = verificar_token(token)
        print(f"🔑 Token válido para user_id: {token_data.user_id}")
    except HTTPException as e:
        print(f"❌ Token inválido ou expirado: {e.detail}")
        await websocket.close(code=1008, reason="Token inválido ou expirado")
        return
    except Exception as e:
        print(f"❌ Erro inesperado ao validar token: {e}")
        await websocket.close(code=1011, reason="Erro interno")
        return

    # Buscar utilizador
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if not user:
        print(f"❌ Utilizador ID {token_data.user_id} não encontrado na BD")
        await websocket.close(code=1008, reason="Utilizador não encontrado")
        return

    if user.sala_id != sala_id:
        print(f"❌ Utilizador {user.nome} (ID:{user.id}) tentou aceder à sala {sala_id} mas pertence à {user.sala_id}")
        await websocket.close(code=1008, reason="Não pertence a esta sala")
        return

    # Verificar sala
    result = await db.execute(select(Sala).where(Sala.id == sala_id))
    if not result.scalar_one_or_none():
        print(f"❌ Sala {sala_id} não existe")
        await websocket.close(code=1008, reason="Sala não existe")
        return

    await manager.connect(sala_id, websocket, user)
    print(f"✅ {user.nome} (ID:{user.id}) conectado com sucesso à sala {sala_id}")

    # ── Histórico ──
    historico = await get_historico(sala_id, db)
    print(f"📜 Histórico: {len(historico)} mensagens para {user.nome}")
    await websocket.send_json({
        "tipo": "historico",
        "mensagens": historico
    })

    # ── Entrada na sala ──
    await manager.broadcast(sala_id, {
        "tipo": "sistema",
        "mensagem": f"{user.nome} entrou na sala.",
        "hora": datetime.utcnow().isoformat()
    })

    try:
        while True:
            data = await websocket.receive_json()
            tipo = data.get("tipo")

            # ── Typing ──
            if tipo == "typing":
                await manager.broadcast(sala_id, {
                    "tipo": "typing",
                    "autor": user.nome
                })
                continue

            # ── Reação ──
            if tipo == "reaction":
                message_id = data.get("message_id")
                emoji = data.get("emoji")
                if message_id and emoji:
                    await manager.broadcast(sala_id, {
                        "tipo": "reaction",
                        "message_id": message_id,
                        "emoji": emoji,
                        "user_id": user.id,
                        "autor": user.nome
                    })
                continue

            # ── Mensagem normal ──
            conteudo = data.get("conteudo")
            file_url = data.get("file_url")

            # ignorar mensagens completamente vazias
            if not conteudo and not file_url:
                continue

            nova_mensagem = Mensagem(
                conteudo=conteudo,
                file_url=file_url,
                file_name=data.get("file_name"),
                file_type=data.get("file_type"),
                file_size=data.get("file_size"),
                user_id=user.id,
                sala_id=sala_id
            )

            db.add(nova_mensagem)
            await db.commit()
            await db.refresh(nova_mensagem)

            await manager.broadcast(sala_id, {
                "tipo": "mensagem",
                "id": nova_mensagem.id,
                "user_id": user.id,
                "autor": user.nome,
                "conteudo": nova_mensagem.conteudo,
                "file_url": nova_mensagem.file_url,
                "file_name": nova_mensagem.file_name,
                "file_type": nova_mensagem.file_type,
                "hora": nova_mensagem.enviada_em.isoformat()
            })

    except WebSocketDisconnect:
        manager.disconnect(sala_id, websocket)
        await manager.broadcast(sala_id, {
            "tipo": "sistema",
            "mensagem": f"{user.nome} saiu da sala.",
            "hora": datetime.utcnow().isoformat()
        })
    except Exception as e:
        print(f"❌ Erro no WebSocket: {e}")
        manager.disconnect(sala_id, websocket)


async def get_historico(sala_id: int, db: AsyncSession) -> List[dict]:
    try:
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

        print(f"✅ Histórico carregado: {len(mensagens)} mensagens para sala {sala_id}")
        return mensagens

    except Exception as e:
        print(f"❌ Erro ao carregar histórico: {e}")
        return []