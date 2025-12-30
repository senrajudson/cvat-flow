# src/main.py
from pathlib import Path
from dotenv import load_dotenv
import os

from src.utils.auth import User
from src.utils.cvat_auth import CvatAuth
from src.utils.cvat_client import CvatClient
from src.utils.upload_images import UploadImagesConfig, UploadImagesCvat


def main() -> None:
    load_dotenv()

    base_url = (os.getenv("CVAT_URL") or "").rstrip("/")
    org_slug = os.getenv("CVAT_ORG") or "meioambiente"

    user = User(
        username=os.getenv("CVAT_USER"),
        password=os.getenv("CVAT_PASS") or "",
        email=os.getenv("CVAT_EMAIL"),
    )

    # Continua igual: você usa sua lógica de login para pegar o access token
    auth = CvatAuth(base_url=base_url)
    token = auth.login_token(user, token_name="training-model")

    # Agora o CvatClient é baseado no cvat-sdk
    client = CvatClient(base_url=base_url, token=token, organization=org_slug)

    about = client.about()
    print(f"🧩 CVAT About: {about}")

    upload_config = UploadImagesConfig(
        project_name="Emissoes",
        dataset_path=Path("datasets/emissoes_dataset/images"),
        task_size=100,
        img_quality=85,
        chunk_size=100,
    )

    uploader = UploadImagesCvat(config=upload_config, client=client)
    task_ids = uploader.run()

    print(f"✅ Upload concluído | Tasks criadas: {task_ids}")


if __name__ == "__main__":
    main()
