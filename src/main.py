# src/api.py
from __future__ import annotations

import os
from uuid import uuid4
from typing import Any, Dict, Optional
from pathlib import Path
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.login.auth import User
from src.login.cvat_auth import CvatAuth
from src.client.cvat_client import CvatClient
from src.upload.upload_images import UploadImagesConfig, UploadImagesCvat

load_dotenv()

app = FastAPI(title="CVAT Uploader API", version="1.0.0")

BASE_URL = (os.getenv("CVAT_URL") or "").rstrip("/")
ORG_SLUG = os.getenv("CVAT_ORG") or "meioambiente"

USER = User(
    username=os.getenv("CVAT_USER"),
    password=os.getenv("CVAT_PASS") or "",
    email=os.getenv("CVAT_EMAIL"),
)

JOBS: Dict[str, Dict[str, Any]] = {}


class UploadRequest(BaseModel):
    project_name: str = Field(..., examples=["Emissoes"])
    dataset_path: str = Field(..., examples=["datasets/emissoes_dataset/images"])
    task_size: int = 100
    img_quality: int = 85
    chunk_size: int = 100


class UploadResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    detail: Optional[str] = None
    task_ids: Optional[list[int]] = None


def _get_client() -> CvatClient:
    if not BASE_URL:
        raise RuntimeError("CVAT_URL não configurado")

    auth = CvatAuth(base_url=BASE_URL)
    token = auth.login_token(USER, token_name="uploader-api")
    return CvatClient(base_url=BASE_URL, token=token, organization=ORG_SLUG)


def _run_upload_job(job_id: str, req: UploadRequest) -> None:
    try:

        # p = Path(req.dataset_path) <---- LINUX

        #-------------------------
        #       WINDOWS          |
        #-------------------------

        raw = req.dataset_path.strip().strip('"').strip("'")

        # aceita / ou \ e também "C:\..." ou caminho relativo
        p = Path(raw)

        # se vier relativo, faz relativo ao diretório do projeto (ou ao cwd do serviço)
        if not p.is_absolute():
            base_dir = Path(os.getenv("DATASETS_BASE_DIR", Path.cwd()))
            p = (base_dir / p)

        #-------------------------
        #     END WINDOWS        |
        #-------------------------

        dataset_path_resolved = p.expanduser().resolve()

        # checks mínimos (não são o “mapeamento seguro”, só evita erro bobo)
        if not dataset_path_resolved.exists():
            JOBS[job_id] = {"status": "error", "detail": f"Caminho não encontrado: {dataset_path_resolved}"}
            return
        if not dataset_path_resolved.is_dir():
            JOBS[job_id] = {"status": "error", "detail": f"Não é uma pasta: {dataset_path_resolved}"}
            return

        client = _get_client()

        config = UploadImagesConfig(
            project_name=req.project_name,
            dataset_path=dataset_path_resolved,
            task_size=req.task_size,
            img_quality=req.img_quality,
            chunk_size=req.chunk_size,
        )

        JOBS[job_id] = {"status": "running"}
        uploader = UploadImagesCvat(config=config, client=client)
        task_ids = uploader.run()

        JOBS[job_id] = {"status": "done", "task_ids": task_ids}

    except Exception as e:
        JOBS[job_id] = {"status": "error", "detail": repr(e)}


@app.post("/upload", response_model=UploadResponse)
def upload(req: UploadRequest, background: BackgroundTasks) -> UploadResponse:
    job_id = str(uuid4())
    JOBS[job_id] = {"status": "queued"}
    background.add_task(_run_upload_job, job_id, req)
    return UploadResponse(job_id=job_id, status="queued")


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str) -> JobStatusResponse:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id não encontrado")

    return JobStatusResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        detail=job.get("detail"),
        task_ids=job.get("task_ids"),
    )

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8010"))

    uvicorn.run("src.api:app", host=host, port=port, reload=True)