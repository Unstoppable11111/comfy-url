"""连通性自检：登录实例，选 0 进容器，跑一条命令。

    python selftest.py
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from term import Term

t = Term()
try:
    print(t.cmd("echo SELFTEST_OK; hostname; hostname -I | awk '{print $1}'"))
finally:
    t.close()
