"""算家云实例连接信息。

密码不写进代码：优先读环境变量，其次读同目录下的 .env.local。
用法：
    set SJ_PWD=xxxx            # PowerShell
    export SJ_PWD=xxxx         # bash
或在本目录新建 .env.local，写一行：SJ_PWD=xxxx
"""
import os

HOST = os.environ.get("SJ_HOST", "hb-a.suanjiayun.com")
PORT = int(os.environ.get("SJ_PORT", "2020"))
USER = os.environ.get("SJ_USER", "18379685528")

_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.local")


def _password():
    pwd = os.environ.get("SJ_PWD")
    if pwd:
        return pwd
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("SJ_PWD="):
                    return line.split("=", 1)[1].strip()
    raise RuntimeError(
        "缺少 SSH 密码：设置环境变量 SJ_PWD，或在 %s 中写入 SJ_PWD=..." % _ENV_FILE
    )


PWD = _password()
