"""上传一个或多个文件到实例，可选随后执行命令。全程单会话。

    python push.py a.py /root/a.py [b.json /root/b.json] ... [--run "python3 /root/a.py"]
"""
import base64
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from term import Term

CHUNK = 700


def upload(t, local, remote):
    data = base64.b64encode(open(local, "rb").read()).decode()
    ch = t.ch
    ch.send("stty -echo\n")
    time.sleep(0.3)
    ch.send(": > %s.b64\n" % remote)
    time.sleep(0.2)
    for i in range(0, len(data), CHUNK):
        ch.send("printf '%%s' '%s' >> %s.b64\n" % (data[i:i + CHUNK], remote))
        time.sleep(0.015)
    time.sleep(0.5)
    ch.send("stty echo\n")
    time.sleep(0.3)
    out = t.cmd("base64 -d %s.b64 > %s && rm -f %s.b64 && wc -c %s" % (remote, remote, remote, remote), wait=60)
    last = [ln for ln in out.splitlines() if ln.strip().isdigit()]
    print("uploaded %s -> %s (%s bytes)" % (local, remote, last[-1] if last else "?"))


def main():
    argv = sys.argv[1:]
    run_cmd = None
    if "--run" in argv:
        i = argv.index("--run")
        run_cmd = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]

    pairs = list(zip(argv[0::2], argv[1::2]))
    t = Term()
    try:
        for local, remote in pairs:
            upload(t, local, remote)
        if run_cmd:
            print(t.cmd(run_cmd, wait=180))
    finally:
        t.close()


if __name__ == "__main__":
    main()
