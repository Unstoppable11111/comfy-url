"""把定妆照复制进 ComfyUI/input/cast/<tag>/，保留角色 ID 或 _face 命名（如 C01.png / C01_face.png）。

    python setup_cast.py qianlong /ComfyUI/output/drama/cast_qianlong
"""
import os
import re
import shutil
import sys

tag = sys.argv[1]
src = sys.argv[2]
dest = "/ComfyUI/input/cast/%s" % tag
os.makedirs(dest, exist_ok=True)

n = 0
for f in sorted(os.listdir(src)):
    if not f.endswith(".png"):
        continue
    stem = os.path.splitext(f)[0]
    cid = re.sub(r"_\d+_$", "", stem)
    shutil.copy(os.path.join(src, f), os.path.join(dest, cid + ".png"))
    n += 1
print("copied %d -> %s" % (n, dest))
print(sorted(os.listdir(dest)))
