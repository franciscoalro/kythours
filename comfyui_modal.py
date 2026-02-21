import subprocess
import modal
import os

# --- Configuracao ---
COMFYUI_DIR = "/root/ComfyUI"
UI_PORT = 8188
BUILD_ID = "v24"  # Mudar quando adicionar novos nodes (invalida cache).
HF_TOKEN = os.environ.get("HF_TOKEN", "")  # Defina HF_TOKEN nos Secrets do Modal

# =============================================================================
# IMAGEM PRE-BUILDADA (GHCR via GitHub Actions)
# =============================================================================
# A imagem e buildada automaticamente pelo GitHub Actions e publicada em:
#   ghcr.io/franciscoalro/kythours-comfyui:latest
#
# Isso resolve o problema de rebuildar tudo ao trocar de conta/token Modal.
# O pull da imagem leva ~2-3 min em vez de ~25 min de build do zero.
#
# Para atualizar a imagem (ex: adicionar novo custom node):
#   1. Edite o Dockerfile.comfyui
#   2. git commit + git push -> GitHub Actions builda automaticamente
#   3. Mude a tag abaixo (ex: v22) para forcar o Modal a puxar a nova imagem
# =============================================================================
GHCR_IMAGE = "ghcr.io/franciscoalro/kythours-comfyui:latest"

comfyui_image = (
    modal.Image.from_registry(GHCR_IMAGE)
    .env({
        "FORCE_REBUILD_ID": BUILD_ID,
        "HF_TOKEN": HF_TOKEN,
    })
)


# Volume para modelos e outputs
model_volume = modal.Volume.from_name("comfyui-storage", create_if_missing=True)

app = modal.App(name=f"comfyui-{BUILD_ID}")


@app.function(
    image=comfyui_image,
    min_containers=0,
    scaledown_window=30 * 60,  # 30 min sem uso = desliga
    max_containers=1,
    allow_concurrent_inputs=1000, # AIOHTTP resolve concurrencia internamente. Evita fila no Proxy do Modal.
    timeout=6 * 60 * 60,  # 6 horas max
    gpu="a10g",
    volumes={f"{COMFYUI_DIR}/models": model_volume},
    secrets=[modal.Secret.from_name("huggingface-secret-2")],
)
# NOTA: @modal.concurrent REMOVIDO — causa erro 405 ao salvar workflows.
# O proxy do Modal decodifica %2F nos URLs, quebrando /api/userdata/workflows/.
# ComfyUI ja e async (aiohttp) e lida com concorrencia internamente.
@modal.web_server(port=UI_PORT, startup_timeout=5 * 60)
def run_comfyui():
    """
    Inicia o ComfyUI no Modal com GPU A10G.
    """
    print(f"[START] ComfyUI (Build: {BUILD_ID})")
    print(f"[INFO] GPU: A10G (24GB VRAM)")

    # Garantir pastas existem
    os.makedirs(f"{COMFYUI_DIR}/models/loras", exist_ok=True)
    os.makedirs(f"{COMFYUI_DIR}/models/loras/FERPHOTO", exist_ok=True)
    os.makedirs(f"{COMFYUI_DIR}/models/checkpoints", exist_ok=True)
    os.makedirs(f"{COMFYUI_DIR}/models/vae", exist_ok=True)
    os.makedirs(f"{COMFYUI_DIR}/models/diffusion_models", exist_ok=True)
    os.makedirs(f"{COMFYUI_DIR}/models/text_encoders", exist_ok=True)
    os.makedirs(f"{COMFYUI_DIR}/models/controlnet", exist_ok=True)
    os.makedirs(f"{COMFYUI_DIR}/models/model_patches", exist_ok=True)
    os.makedirs(f"{COMFYUI_DIR}/output", exist_ok=True)

    # --- Validacao inteligente de arquivos no volume ---
    # Tamanhos minimos esperados (em MB) para arquivos criticos grandes.
    # Se o arquivo existe mas e menor que o esperado, foi download incompleto.
    EXPECTED_MIN_SIZES_MB = {
        "qwen_3_4b.safetensors": 6000,           # ~7GB text encoder
        "Qwen_3_4b-Q8_0.gguf": 3000,             # ~3.6GB GGUF
        "Qwen_3_4b-imatrix-IQ4_XS.gguf": 1500,   # ~2GB GGUF
        "z_image_turbo_bf16.safetensors": 5000,   # ~6GB diffusion model
        "z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors": 3000,  # ~3.5GB
        "Z-Image-Turbo-Fun-Controlnet-Union-2.1.safetensors": 500,  # ~700MB
    }

    print("[INFO] Verificando arquivos corrompidos no volume...")
    cleaned = 0
    for root, dirs, files in os.walk(f"{COMFYUI_DIR}/models"):
        for fname in files:
            fpath = os.path.join(root, fname)
            if fname.endswith((".safetensors", ".pt", ".pth", ".ckpt", ".gguf")):
                fsize = os.path.getsize(fpath)
                fsize_mb = fsize / (1024 * 1024)

                # Check 1: Tamanho minimo especifico para arquivos criticos
                expected_min = EXPECTED_MIN_SIZES_MB.get(fname)
                if expected_min and fsize_mb < expected_min:
                    print(f"[CLEAN] {fname} incompleto ({fsize_mb:.0f}MB < {expected_min}MB esperado). Removendo...")
                    os.remove(fpath)
                    cleaned += 1
                    continue

                # Check 2: Arquivo muito pequeno (< 1MB = HTML de erro ou 404)
                if fsize < 1 * 1024 * 1024:
                    print(f"[CLEAN] Removendo corrompido: {fname} ({fsize} bytes)")
                    os.remove(fpath)
                    cleaned += 1
                    continue

                # Check 3: Validar header safetensors (detecta arquivos truncados)
                if fname.endswith(".safetensors"):
                    try:
                        import safetensors
                        with safetensors.safe_open(fpath, framework="pt", device="cpu") as f:
                            _ = f.keys()  # Tenta ler o header
                    except Exception as e:
                        print(f"[CLEAN] {fname} corrompido (header invalido: {e}). Removendo...")
                        os.remove(fpath)
                        cleaned += 1
                        continue

    if cleaned:
        print(f"[CLEAN] {cleaned} arquivo(s) corrompido(s) removido(s). Serao re-baixados.")
    else:
        print("[CLEAN] Todos os arquivos validos. ✅")


    # --- Downloads de Modelos (Z-Image-Turbo Official) ---
    models_to_download = [
        # Z-Image-Turbo BF16 (High VRAM)
        {
            "url": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors",
            "path": f"{COMFYUI_DIR}/models/diffusion_models/z_image_turbo_bf16.safetensors"
        },
        # Z-Image-Turbo FP8 (Low VRAM) - Opcional, mas util para A10G se quiser economizar
        {
            "url": "https://huggingface.co/Kijai/Z-Image_comfy_fp8_scaled/resolve/main/z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors",
            "path": f"{COMFYUI_DIR}/models/diffusion_models/z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors"
        },
        # Text Encoder (Required)
        {
            "url": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
            "path": f"{COMFYUI_DIR}/models/text_encoders/qwen_3_4b.safetensors"
        },
        # VAE (Required)
        {
            "url": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors",
            "path": f"{COMFYUI_DIR}/models/vae/ae.safetensors"
        },
        # Qwen 3.4B GGUF Text Encoder (para uso com CLIPLoaderGGUF)
        # IQ4_XS - Recomendado (qualidade/tamanho balanceados)
        {
            "url": "https://huggingface.co/worstplayer/Z-Image_Qwen_3_4b_text_encoder_GGUF/resolve/main/Qwen_3_4b-imatrix-IQ4_XS.gguf",
            "path": f"{COMFYUI_DIR}/models/text_encoders/Qwen_3_4b-imatrix-IQ4_XS.gguf"
        },
        # Q8_0 - Maxima qualidade (quase identico ao FP16)
        {
            "url": "https://huggingface.co/worstplayer/Z-Image_Qwen_3_4b_text_encoder_GGUF/resolve/main/Qwen_3_4b-Q8_0.gguf",
            "path": f"{COMFYUI_DIR}/models/text_encoders/Qwen_3_4b-Q8_0.gguf"
        },
        # Qwen3-4b-Z-Image-Engineer-V4-F16
        {
            "url": "https://huggingface.co/BennyDaBall/Qwen3-4b-Z-Image-Engineer-V4/resolve/main/Qwen3-4b-Z-Image-Engineer-V4-F16.gguf",
            "path": f"{COMFYUI_DIR}/models/text_encoders/Qwen3-4b-Z-Image-Engineer-V4-F16.gguf"
        },
        # Upscale Model
        {
            "url": "https://huggingface.co/Thelocallab/2xLexicaRRDBNet_Sharp/resolve/main/2xLexicaRRDBNet_Sharp.pth",
            "path": f"{COMFYUI_DIR}/models/upscale_models/2xLexicaRRDBNet_Sharp.pth"
        },
        # Upscale Model for Amazing Z-Image WF
        {
            "url": "https://huggingface.co/martin-rizzo/ESRGAN-4x/resolve/main/4x_foolhardy_Remacri.safetensors",
            "path": f"{COMFYUI_DIR}/models/upscale_models/4x_foolhardy_Remacri.safetensors"
        },
        # Amazing Z-Image WF v4.0 Diffusion Model
        {
            "url": "https://huggingface.co/jayn7/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q5_K_S.gguf",
            "path": f"{COMFYUI_DIR}/models/diffusion_models/z_image_turbo-Q5_K_S.gguf"
        },
        # Amazing Z-Image WF v4.0 Text Encoder
        {
            "url": "https://huggingface.co/mradermacher/Qwen3-4B-i1-GGUF/resolve/main/Qwen3-4B.i1-Q5_K_S.gguf",
            "path": f"{COMFYUI_DIR}/models/text_encoders/Qwen3-4B.i1-Q5_K_S.gguf"
        },
        # Workflow JSON (Exemplo)
        {
            "url": "https://huggingface.co/jayn7/Z-Image-Turbo-GGUF/resolve/main/example_workflow.json",
            "path": f"{COMFYUI_DIR}/user/default/workflows/z_image_turbo_workflow.json"
        },
        # ControlNet Union 2.1 (in controlnet folder)
        {
            "url": "https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.0/resolve/main/Z-Image-Turbo-Fun-Controlnet-Union-2.1.safetensors",
            "path": f"{COMFYUI_DIR}/models/controlnet/Z-Image-Turbo-Fun-Controlnet-Union-2.1.safetensors"
        },
        # ControlNet Union 2.1 (in model_patches folder)
        {
            "url": "https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.0/resolve/main/Z-Image-Turbo-Fun-Controlnet-Union-2.1.safetensors",
            "path": f"{COMFYUI_DIR}/models/model_patches/Z-Image-Turbo-Fun-Controlnet-Union-2.1.safetensors"
        }
    ]

    # Adicionar todos os LoRAs do Kitoalro (Steps 100 a 900 + Final)
    hf_repo = "kythours/kitoalro"
    lora_prefix = "ohwxphoto"

    # 1. LoRA Final
    models_to_download.append({
        "url": f"https://huggingface.co/{hf_repo}/resolve/main/{lora_prefix}.safetensors",
        "path": f"{COMFYUI_DIR}/models/loras/{lora_prefix}.safetensors"
    })

    # 2. Checkpoints Intermediarios (100, 200, ... 900)
    for i in range(100, 1000, 100):
        step_str = f"{i:09d}" # ex: 000000100
        filename = f"{lora_prefix}_{step_str}.safetensors"
        models_to_download.append({
            "url": f"https://huggingface.co/{hf_repo}/resolve/main/{filename}",
            "path": f"{COMFYUI_DIR}/models/loras/{filename}"
        })

    # --- LoRAs FERPHOTO Otimizadas (kythours/FERGIRL - Repo Privado) ---
    fergirl_repo = "kythours/FERGIRL"
    os.makedirs(f"{COMFYUI_DIR}/models/loras/FERPHOTO", exist_ok=True)

    # 1. FERPHOTO v5 (HF Optimized) — Checkpoints intermediarios
    v5_name = "FERPHOTO_zturbo_HF_OPTIMIZED_v5"
    for step in [250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750, 3000]:
        step_str = f"{step:09d}"  # ex: 000000250
        filename = f"{v5_name}_000000{step:03d}.safetensors"
        models_to_download.append({
            "url": f"https://huggingface.co/{fergirl_repo}/resolve/main/{v5_name}/{v5_name}_000000{step:03d}.safetensors",
            "path": f"{COMFYUI_DIR}/models/loras/FERPHOTO/{v5_name}_{step_str}.safetensors"
        })

    # 2. FERPHOTO v5 — Final checkpoint
    models_to_download.append({
        "url": f"https://huggingface.co/{fergirl_repo}/resolve/main/{v5_name}/{v5_name}.safetensors",
        "path": f"{COMFYUI_DIR}/models/loras/FERPHOTO/{v5_name}.safetensors"
    })

    # 3. FERPHOTO v7 (H100 3000 Final) — Melhor checkpoint
    v7_name = "FERPHOTO_zturbo_HF_OPTIMIZED_v7_H100_3000_copy"
    models_to_download.append({
        "url": f"https://huggingface.co/{fergirl_repo}/resolve/main/{v7_name}/{v7_name}.safetensors",
        "path": f"{COMFYUI_DIR}/models/loras/FERPHOTO/{v7_name}.safetensors"
    })

    # 4. FERPHOTO v7 — Checkpoints intermediarios
    for step in [250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750]:
        step_str = f"{step:09d}"
        models_to_download.append({
            "url": f"https://huggingface.co/{fergirl_repo}/resolve/main/{v7_name}/{v7_name}_{step_str}.safetensors",
            "path": f"{COMFYUI_DIR}/models/loras/FERPHOTO/{v7_name}_{step_str}.safetensors"
        })


    for model in models_to_download:
        # Garantir que a pasta existe
        os.makedirs(os.path.dirname(model["path"]), exist_ok=True)

        dest = model["path"]
        name = os.path.basename(dest)

        # Se ja existe e e valido (> 1MB), pula
        if os.path.exists(dest) and os.path.getsize(dest) > 1 * 1024 * 1024:
            print(f"[OK] {name} ja existe!")
            continue

        # Remover arquivo corrompido/incompleto se existir
        if os.path.exists(dest):
            os.remove(dest)

        print(f"[INFO] Baixando {name}...")
        # Usar token HF para repos privados
        hf_token = os.environ.get("HF_TOKEN", "")
        cmd = [
            "wget", "-q", "--show-progress",
            model["url"],
            "-O", dest
        ]
        if hf_token and "huggingface.co" in model["url"]:
            cmd = [
                "wget", "-q", "--show-progress",
                f"--header=Authorization: Bearer {hf_token}",
                model["url"],
                "-O", dest
            ]
        subprocess.run(cmd, check=False)

        # Validar arquivo apos download (deve ter > 1MB para ser valido)
        if os.path.exists(dest) and os.path.getsize(dest) > 1 * 1024 * 1024:
            size_mb = os.path.getsize(dest) / 1024 / 1024
            print(f"[OK] {name} baixado! ({size_mb:.1f} MB)")
        else:
            # Arquivo invalido (HTML de erro, 404, etc) — deletar
            if os.path.exists(dest):
                os.remove(dest)
            print(f"[SKIP] {name} nao disponivel (ignorado)")



    # Iniciar ComfyUI
    subprocess.Popen(
        [
            "python", "main.py",
            "--listen", "0.0.0.0",
            "--port", str(UI_PORT),
            "--preview-method", "auto",
        ],
        cwd=COMFYUI_DIR,
    )
    print(f"[OK] ComfyUI iniciando na porta {UI_PORT}...")
    print("[INFO] Acesse pela URL publica gerada pelo Modal.")


@app.local_entrypoint()
def main():
    print("=" * 60)
    print("  ComfyUI on Modal")
    print(f"  Build: {BUILD_ID}")
    print("  GPU: A10G (24GB)")
    print("=" * 60)
    print()
    print("A URL publica aparecera automaticamente.")
    print()
    print("Para parar: Ctrl+C")
    print("=" * 60)
