import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

from sjconfig import HOST, PORT, USER, PWD, INDEX


def _connect_once(timeout):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PWD, timeout=timeout,
              banner_timeout=timeout, auth_timeout=timeout,
              look_for_keys=False, allow_agent=False)
    return c


def connect(retries=4, delay=6, timeout=45):
    """连实例。服务器偶尔不返回 banner，重试几次。"""
    last = None
    for i in range(retries):
        try:
            return _connect_once(timeout)
        except Exception as e:
            last = e
            if i < retries - 1:
                time.sleep(delay)
    raise last


def open_shell(c, width=240, height=60):
    ch = c.invoke_shell(term="xterm", width=width, height=height)
    ch.settimeout(1.0)
    return ch


def read(ch, seconds=2.0, idle=1.5):
    buf = b""
    end = time.time() + seconds
    while time.time() < end:
        try:
            d = ch.recv(65536)
            if d:
                buf += d
                end = time.time() + idle
        except Exception:
            time.sleep(0.15)
    return buf


def read_until(ch, needles, timeout=20.0):
    """读到出现任意一个关键词，或超时。返回 (buf, 命中的词 或 None)"""
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        try:
            d = ch.recv(65536)
            if d:
                buf += d
                text = buf.decode("utf-8", "replace")
                for n in needles:
                    if n in text:
                        return buf, n
        except Exception:
            time.sleep(0.1)
    return buf, None


class Log:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8", errors="replace")

    def __call__(self, *a):
        s = " ".join(str(x) for x in a)
        print(s)
        self.f.write(s + "\n")
        self.f.flush()
