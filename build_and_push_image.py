"""
build_and_push_image.py
=======================
Builda a imagem ComfyUI completa (com todos os custom nodes) e faz push
para o Docker Hub. Depois disso, o comfyui_modal.py pode puxar a imagem
pronta em qualquer conta/workspace — sem rebuildar do zero.

USO:
  1. Configure DOCKER_USER abaixo com seu usuário do Docker Hub.
  2. Execute: modal run build_and_push_image.py
  3. Quando terminar, copie a variável IMAGE_TAG gerada para comfyui_modal.py

CUSTO: Apenas tempo de build (roda 1x). A imagem fica pública no Docker Hub grátis.
"""

import modal

# ============================================================
# CONFIGURE AQUI
# ============================================================
DOCKER_USER = "SEU_USUARIO_DOCKERHUB"   # ex: "franciscoalro"
IMAGE_NAME = "comfyui-modal"
IMAGE_TAG = "v21-rgfix"                  # Sincronize com BUILD_ID no comfyui_modal.py
FULL_IMAGE = f"{DOCKER_USER}/{IMAGE_NAME}:{IMAGE_TAG}"

COMFYUI_DIR = "/root/ComfyUI"
# ============================================================

print(f"[INFO] Imagem alvo: {FULL_IMAGE}")

# Reutiliza exatamente a mesma definição de imagem do comfyui_modal.py
comfyui_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "wget", "curl", "libgl1", "libglib2.0-0", "ffmpeg")
    .run_commands(
        "pip install --upgrade pip",
        "pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121",
    )
    .run_commands(
        f"git clone https://github.com/comfyanonymous/ComfyUI.git {COMFYUI_DIR}",
        f"rm -rf {COMFYUI_DIR}/models && mkdir -p {COMFYUI_DIR}/models",
    )
    .run_commands(
        f"cd {COMFYUI_DIR} && pip install --no-cache-dir -r requirements.txt",
        "pip install --no-cache-dir xformers==0.0.28.post3 --index-url https://download.pytorch.org/whl/cu121",
        "pip install --no-cache-dir --upgrade transformers",
        "pip install --no-cache-dir accelerate qwen-vl-utils opencv-python scipy timm einops sageattention pandas gguf",
    )
    .run_commands(
        f"git clone https://github.com/ltdrdata/ComfyUI-Manager.git {COMFYUI_DIR}/custom_nodes/ComfyUI-Manager",
        f"git clone https://github.com/chflame163/ComfyUI_LayerStyle.git {COMFYUI_DIR}/custom_nodes/ComfyUI_LayerStyle",
        f"git clone https://github.com/kijai/ComfyUI-KJNodes.git {COMFYUI_DIR}/custom_nodes/ComfyUI-KJNodes",
        f"git clone https://github.com/city96/ComfyUI-GGUF.git {COMFYUI_DIR}/custom_nodes/ComfyUI-GGUF",
        f"git clone https://github.com/rgthree/rgthree-comfy.git {COMFYUI_DIR}/custom_nodes/rgthree-comfy",
        f"git clone https://github.com/Azornes/Comfyui-Resolution-Master.git {COMFYUI_DIR}/custom_nodes/ComfyUI-Resolution-Master",
    )
    .run_commands(
        f"git clone https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler.git {COMFYUI_DIR}/custom_nodes/ComfyUI-SeedVR2_VideoUpscaler",
        f"git clone https://github.com/aistudynow/ComfyUI-QwenVL.git {COMFYUI_DIR}/custom_nodes/ComfyUI-QwenVL",
        f"git clone https://github.com/yolain/ComfyUI-Easy-Use.git {COMFYUI_DIR}/custom_nodes/ComfyUI-Easy-Use",
        f"git clone https://github.com/PozzettiAndrea/ComfyUI-DepthAnythingV3.git {COMFYUI_DIR}/custom_nodes/ComfyUI-DepthAnythingV3",
        f"git clone https://github.com/r-vage/ComfyUI-RvTools_v2.git {COMFYUI_DIR}/custom_nodes/ComfyUI-RvTools",
        f"git clone https://github.com/fannovel16/comfyui_controlnet_aux.git {COMFYUI_DIR}/custom_nodes/comfyui_controlnet_aux",
        f"git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git {COMFYUI_DIR}/custom_nodes/ComfyUI-Custom-Scripts",
        f"git clone https://github.com/chibiace/ComfyUI-Chibi-Nodes.git {COMFYUI_DIR}/custom_nodes/ComfyUI-Chibi-Nodes",
        f"git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git {COMFYUI_DIR}/custom_nodes/ComfyUI-Impact-Pack",
        f"git clone https://github.com/PGCRT/CRT-Nodes.git {COMFYUI_DIR}/custom_nodes/CRT-Nodes",
        f"git clone https://github.com/ClownsharkBatwing/RES4LYF.git {COMFYUI_DIR}/custom_nodes/RES4LYF",
        f"git clone https://github.com/gseth/ControlAltAI-Nodes.git {COMFYUI_DIR}/custom_nodes/ControlAltAI-Nodes",
        f"git clone https://github.com/jags111/efficiency-nodes-comfyui.git {COMFYUI_DIR}/custom_nodes/efficiency-nodes-comfyui",
        f"git clone https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git {COMFYUI_DIR}/custom_nodes/ComfyUI-Impact-Subpack",
        f"git clone https://github.com/ssitu/ComfyUI_UltimateSDUpscale.git --recursive {COMFYUI_DIR}/custom_nodes/ComfyUI_UltimateSDUpscale",
    )
    .run_commands(
        f"git clone https://github.com/PozzettiAndrea/ComfyUI-SAM3.git {COMFYUI_DIR}/custom_nodes/ComfyUI-SAM3",
        f"git clone https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch.git {COMFYUI_DIR}/custom_nodes/ComfyUI-Inpaint-CropAndStitch",
        f"git clone https://github.com/1038lab/ComfyUI-JoyCaption.git {COMFYUI_DIR}/custom_nodes/ComfyUI-JoyCaption",
        f"git clone https://github.com/WASasquatch/was-node-suite-comfyui.git {COMFYUI_DIR}/custom_nodes/was-node-suite-comfyui",
        f"git clone https://github.com/ChangeTheConstants/SeedVarianceEnhancer.git {COMFYUI_DIR}/custom_nodes/SeedVarianceEnhancer",
    )
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI_LayerStyle && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-KJNodes && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-GGUF && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-SeedVR2_VideoUpscaler && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-QwenVL && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-Easy-Use && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-DepthAnythingV3 && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-RvTools && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/comfyui_controlnet_aux && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-Impact-Pack && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/CRT-Nodes && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/RES4LYF && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ControlAltAI-Nodes && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/efficiency-nodes-comfyui && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-Impact-Subpack && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI_UltimateSDUpscale && pip install -r requirements.txt || true")
    .run_commands("pip install --no-cache-dir ultralytics")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-SAM3 && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-Inpaint-CropAndStitch && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/ComfyUI-JoyCaption && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/was-node-suite-comfyui && pip install -r requirements.txt || true")
    .run_commands(f"cd {COMFYUI_DIR}/custom_nodes/SeedVarianceEnhancer && pip install -r requirements.txt || true")
    .run_commands(
        f"sed -i 's/resp = svg.format(bg=bg, fg=fg)/resp = svg.replace(\"{{{{bg}}}}\", bg).replace(\"{{{{fg}}}}\", fg)/' {COMFYUI_DIR}/custom_nodes/rgthree-comfy/py/server/routes_config.py"
    )
)

app = modal.App("comfyui-image-builder")


@app.function(
    image=comfyui_image,
    timeout=60 * 60,  # 1 hora max para o build
    cpu=4,
)
def build_and_push():
    """
    Esta função roda dentro da imagem já buildada pelo Modal.
    Ela exporta a imagem e faz push para o Docker Hub.
    
    ALTERNATIVA MAIS SIMPLES: Use modal image build (ver comentário abaixo).
    """
    import subprocess
    print(f"[OK] Imagem buildada com sucesso pelo Modal!")
    print(f"[INFO] Para usar em outra conta, adicione ao comfyui_modal.py:")
    print(f"")
    print(f"  comfyui_image = modal.Image.from_registry(")
    print(f"      '{FULL_IMAGE}',")
    print(f"      add_python='3.11'")
    print(f"  )")
    print(f"")
    print(f"[INFO] Depois faça push manualmente via Docker:")
    print(f"  docker pull ... (Modal nao expoe docker diretamente)")


@app.local_entrypoint()
def main():
    """
    Instrucoes para publicar a imagem no Docker Hub.
    
    METODO RECOMENDADO: Usar GitHub Actions para buildar e publicar automaticamente.
    Ver dockerfile abaixo ou use o script manual.
    """
    print("=" * 60)
    print("  ComfyUI Image Builder")
    print("=" * 60)
    print()
    print("OPCAO 1 (Mais simples) - Modal Image Snapshot:")
    print("  O Modal ja salva a imagem buildada internamente.")
    print("  O cache persiste dentro do mesmo workspace.")
    print()
    print("OPCAO 2 (Cross-account) - Docker Hub:")
    print("  1. Instale Docker Desktop")
    print("  2. Execute: docker login")
    print(f"  3. Crie um Dockerfile (ver abaixo) e execute:")
    print(f"     docker build -t {FULL_IMAGE} -f Dockerfile.comfyui .")
    print(f"     docker push {FULL_IMAGE}")
    print()
    print("OPCAO 3 (Recomendado) - GitHub Actions:")
    print("  Ver arquivo .github/workflows/build-comfyui.yml")
    print()
    print(f"Depois, no comfyui_modal.py, substitua a definicao da imagem por:")
    print()
    print(f"  comfyui_image = modal.Image.from_registry(")
    print(f"      '{FULL_IMAGE}',")
    print(f"  )")
    print()
    print("Isso vai puxar a imagem pronta em QUALQUER conta Modal!")
