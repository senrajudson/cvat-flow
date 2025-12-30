# src/utils/upload_images.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from pydantic import BaseModel, Field, ConfigDict

from src.utils.cvat_client import CvatClient


class UploadImagesConfig(BaseModel):
    """
    Configuração geral do upload.
    """
    project_name: str
    dataset_path: Path
    task_size: int = Field(100, ge=1, le=10_000)
    img_quality: int = Field(85, ge=1, le=100)
    chunk_size: int = Field(100, ge=0)

    def images(self) -> List[Path]:
        """
        Lista todas as imagens válidas no dataset.
        """
        if not self.dataset_path.exists():
            raise ValueError(f"Caminho não encontrado: {self.dataset_path}")

        imgs = sorted(
            p for p in self.dataset_path.iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )

        if not imgs:
            raise ValueError("Nenhuma imagem encontrada")

        return list(imgs)

    def build_task_name(self, batch_index: int) -> str:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{self.project_name}_batch_{batch_index:03d}_{ts}"


def chunked(seq: List[Path], size: int) -> Iterable[List[Path]]:
    """
    Divide a lista em blocos de tamanho 'size'.
    """
    for i in range(0, len(seq), size):
        yield seq[i: i + size]


class UploadImagesCvat(BaseModel):
    """
    Pipeline:

      1. Descobre todas as imagens do dataset.
      2. Divide em batches de 'task_size'.
      3. Garante que o projeto existe (get_or_create_project).
      4. Cria uma task por batch.
      5. Faz upload via TUS usando CvatClient.attach_data_to_task().
    """
    config: UploadImagesConfig
    client: CvatClient

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def run(self) -> List[int]:
        imgs = self.config.images()
        batches = list(chunked(imgs, self.config.task_size))

        if not batches:
            raise RuntimeError("Nenhum batch de imagens foi gerado")

        # Se o projeto não existir, cria
        project_id = self.client.get_or_create_project(self.config.project_name)
        print(f"[CVAT] Usando projeto '{self.config.project_name}' (id={project_id})")

        created_task_ids: List[int] = []

        for idx, batch in enumerate(batches, start=1):
            task_name = self.config.build_task_name(idx)
            print(f"[CVAT] Criando task '{task_name}' com {len(batch)} imagens...")

            task_id = self.client.create_task(
                name=task_name,
                project_id=project_id,
            )
            print(f"[CVAT] -> Task criada com id={task_id}, iniciando upload via TUS...")

            rq_id = self.client.attach_data_to_task(
                task_id=task_id,
                images=batch,
                image_quality=self.config.img_quality,
                chunk_size=self.config.chunk_size,
            )
            print(f"[CVAT] Upload para task {task_id} enviado. rq_id={rq_id}")

            created_task_ids.append(task_id)

        return created_task_ids
