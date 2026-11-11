import io, sys, time
import paramiko

from sjconfig import HOST, PORT, USER, PWD

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PWD, timeout=25,
              banner_timeout=25, auth_timeout=25, look_for_keys=False, allow_agent=False)
    return c

def open_shell(c, wait_menu=True):
    ch = c.invoke_shell(term="xterm", width=220, height=50)
    ch.settimeout(1.0)
    buf = read(ch, 3)
    if wait_menu:
        ch.send("0\r")
        buf += read(ch, 8)
    return ch, buf

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

def send(ch, cmd, seconds=8, idle=2.0):
    ch.send(cmd + "\r")
    return read(ch, seconds, idle)

class Log:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8", errors="replace")
    def __call__(self, *a):
        s = " ".join(str(x) for x in a)
        print(s)
        self.f.write(s + "\n")
        self.f.flush()
