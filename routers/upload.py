# routers/upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import shutil
import os
from uuid import uuid4

router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Validação de tamanho (50MB)
        if file.size > 50 * 1024 * 1024:
            raise HTTPException(400, "Ficheiro demasiado grande (máximo 50MB)")

        # Tipos permitidos
        allowed_types = [
            "image/jpeg", "image/png", "image/gif", "image/webp",
            "video/mp4", "video/webm", "video/quicktime",
            "audio/mpeg", "audio/wav", "audio/ogg",
            "application/pdf", "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]

        if file.content_type not in allowed_types:
            raise HTTPException(400, f"Tipo de ficheiro não permitido: {file.content_type}")

        # Gerar nome único
        ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
        unique_name = f"{uuid4()}.{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        # Salvar ficheiro
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_url = f"http://127.0.0.1:8000/uploads/{unique_name}"

        return {
            "success": True,
            "file_url": file_url,
            "file_name": file.filename,
            "file_type": file.content_type.split("/")[0],
            "file_size": file.size
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Erro upload: {e}")
        raise HTTPException(500, "Erro interno ao processar ficheiro")