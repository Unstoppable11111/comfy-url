#!/bin/bash
# 下载 Qwen-Image 2.1 三件套到 /ComfyUI/models，支持断点续传
set -u
BASE="https://modelscope.cn/models/Comfy-Org/Qwen-Image-2.1/resolve/master"
ROOT="/ComfyUI/models"

dl() {
  local sub="$1" name="$2" size="$3"
  local dir="$ROOT/$sub"
  mkdir -p "$dir"
  local dest="$dir/$name"

  if [ -f "$dest" ] && [ "$(stat -c%s "$dest")" = "$size" ]; then
    echo "[跳过] $name 已完整"
    return 0
  fi

  local url="$BASE/$sub/$name"
  echo "[开始] $name  期望 $((size/1024/1024)) MB  $(date +%H:%M:%S)"
  if command -v aria2c >/dev/null 2>&1; then
    aria2c -x8 -s8 -k1M -c --auto-file-renaming=false --allow-overwrite=true \
           --console-log-level=warn --summary-interval=15 \
           -d "$dir" -o "$name" "$url"
  else
    curl -L -C - --retry 5 --retry-delay 5 -o "$dest" "$url"
  fi

  local got=$(stat -c%s "$dest" 2>/dev/null || echo 0)
  if [ "$got" = "$size" ]; then
    echo "[完成] $name  $(date +%H:%M:%S)"
  else
    echo "[失败] $name 得到 $got / 需要 $size"
    return 1
  fi
}

dl diffusion_models qwen_image_2.1_int8_convrot.safetensors 7256783064
dl text_encoders    qwen3vl_8b_int8_convrot.safetensors   9350798360
dl vae              qwen_image_2.1_vae_bf16.safetensors   675509688

# 兼容目录
mkdir -p "$ROOT/text_encoders"
[ -e "$ROOT/clip/qwen3vl_8b_int8_convrot.safetensors" ] || \
  ln -sf ../text_encoders/qwen3vl_8b_int8_convrot.safetensors "$ROOT/clip/qwen3vl_8b_int8_convrot.safetensors" 2>/dev/null

echo "ALL_DONE $(date +%H:%M:%S)"
df -h / | tail -1
