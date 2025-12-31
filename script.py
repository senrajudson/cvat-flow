import time
import requests

API = "http://127.0.0.1:8010"

payload = {
    "project_name": "Emissoes",
    # no Windows prefira / (ou use \\ no JSON)
    "dataset_path": r"D:/Judson_projetos/training_model/datasets/emissoes_dataset/images",
    "task_size": 100,
    "img_quality": 85,
    "chunk_size": 100,
}

def main():
    # 1) dispara upload
    r = requests.post(f"{API}/upload", json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()

    job_id = data["job_id"]
    print(f"✅ Job criado: {job_id} | status={data['status']}")

    # 2) consulta até terminar
    while True:
        s = requests.get(f"{API}/jobs/{job_id}", timeout=30)
        s.raise_for_status()
        st = s.json()

        print(f"📡 status={st['status']}", end="")

        if st.get("detail"):
            print(f" | detail={st['detail']}")
        else:
            print()

        if st["status"] == "done":
            print(f"🎯 Tasks criadas: {st.get('task_ids')}")
            break

        if st["status"] == "error":
            print("❌ Erro no job.")
            break

        time.sleep(2)

if __name__ == "__main__":
    main()
