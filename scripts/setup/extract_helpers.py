import zipfile

z = zipfile.ZipFile(r'e:\codex\video\scripts\comfyui_master.zip')
targets = {
    'ComfyUI-master/comfy/rmsnorm.py': r'e:\codex\video\scripts\rmsnorm.py',
    'ComfyUI-master/comfy/model_prefetch.py': r'e:\codex\video\scripts\model_prefetch.py',
    'ComfyUI-master/comfy/quant_ops.py': r'e:\codex\video\scripts\quant_ops.py',
    'ComfyUI-master/comfy/ldm/wan/model_animate2.py': r'e:\codex\video\scripts\model_animate2.py',
}

for src, dst in targets.items():
    if src in z.namelist():
        with open(dst, 'wb') as f:
            f.write(z.read(src))
        print("Extracted:", dst)
    else:
        print("Missing in zip:", src)
