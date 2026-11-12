"""算家云实例连接信息。

优先级：环境变量 > 同目录 .env.local > 默认值。
密码只放 .env.local（已在 .gitignore 忽略），不写进代码。

.env.local 支持：
    SJ_HOST=xn-b.suanjiayun.com
    SJ_PORT=2020
    SJ_USER=18379685528
    SJ_PWD=xxxx
    SJ_INDEX=0        # 登录菜单里选第几个实例
"""
import os

_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.local")


def _load_env_file():
    data = {}
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    return data


_FILE_ENV = _load_env_file()


def get(key, default=None):
    return os.environ.get(key) or _FILE_ENV.get(key) or default


HOST = get("SJ_HOST", "hb-a.suanjiayun.com")
PORT = int(get("SJ_PORT", "2020"))
USER = get("SJ_USER", "18379685528")
INDEX = str(get("SJ_INDEX", "0"))


def _password():
    pwd = get("SJ_PWD")
    if pwd:
        return pwd
    raise RuntimeError(
        "缺少 SSH 密码：设置环境变量 SJ_PWD，或在 %s 中写入 SJ_PWD=..." % _ENV_FILE
    )


PWD = _password()
