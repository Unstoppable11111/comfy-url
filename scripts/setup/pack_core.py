import zipfile
import tarfile
import io
import os

zip_path = r'e:\codex\video\scripts\comfyui_master.zip'
out_tar = r'e:\codex\video\scripts\core_update.tar.gz'

z = zipfile.ZipFile(zip_path)
with tarfile.open(out_tar, 'w:gz') as tar:
    for f in z.namelist():
        if f.startswith('ComfyUI-master/comfy/') or f.startswith('ComfyUI-master/comfy_extras/') or f in [
            'ComfyUI-master/main.py', 'ComfyUI-master/nodes.py', 
            'ComfyUI-master/execution.py', 'ComfyUI-master/folder_paths.py'
        ]:
            data = z.read(f)
            rel_name = f.replace('ComfyUI-master/', '')
            ti = tarfile.TarInfo(name=rel_name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))

print('Created core_update.tar.gz size:', os.path.getsize(out_tar) / 1024, 'KB')
