"""把定妆照复制进 ComfyUI/input/cast/<tag>/，按角色 ID 命名（C01.png）。

    python setup_cast.py qianlong /ComfyUI/output/drama/cast_qianlong
"""
import os
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
    cid = f.split("_")[0]
    shutil.copy(os.path.join(src, f), os.path.join(dest, cid + ".png"))
    n += 1
print("copied %d -> %s" % (n, dest))
print(sorted(os.listdir(dest)))
