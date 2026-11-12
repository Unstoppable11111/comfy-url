import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import rsess
from sjconfig import INDEX

MENU_HINT = "输入服务器序号"
SHELL_HINT = "# "


class Term:
    """登录 → 等菜单 → 选实例 → 拿到容器 shell。"""

    def __init__(self):
        last = None
        for attempt in range(3):
            try:
                self._open()
                return
            except Exception as e:
                last = e
                self.close()
                time.sleep(5)
        raise last

    def _open(self):
        self.c = rsess.connect()
        self.ch = rsess.open_shell(self.c)
        buf, hit = rsess.read_until(self.ch, [MENU_HINT, "没有获取到设备", "请开机"], timeout=60)
        text = buf.decode("utf-8", "replace")
        if hit is None:
            raise RuntimeError("登录后没等到实例菜单（可能网关繁忙），稍后重试")
        if "没有获取到设备" in text or "请开机" in text:
            raise RuntimeError("实例已关机：请在算家云控制台开机后再运行")

        self.ch.send(INDEX)
        time.sleep(1.2)
        self.ch.send("\n")
        buf2, _ = rsess.read_until(self.ch, [SHELL_HINT], timeout=40)
        self._ready_banner = buf2.decode("utf-8", "replace")

    def cmd(self, command, wait=30):
        tok = "M%s" % int(time.time() * 1000)
        send = command + '; echo "%s""%s" $?' % (tok, "R")
        want = tok + "R"
        self.ch.send(send + "\n")
        buf = b""
        end = time.time() + wait
        while time.time() < end:
            try:
                d = self.ch.recv(131072)
                if d:
                    buf += d
                    if want.encode() in buf:
                        break
            except Exception:
                time.sleep(0.1)
        text = buf.decode("utf-8", "replace")
        text = text.replace("\r\n", "\n").replace("\r", "")
        i = text.find(want)
        if i >= 0:
            text = text[:i]
        lines = text.split("\n")
        if lines:
            lines = lines[1:]
        return "\n".join(lines).strip()

    def close(self):
        try:
            self.ch.close()
        except Exception:
            pass
        try:
            self.c.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


if __name__ == "__main__":
    cmds = sys.argv[1:]
    t = Term()
    try:
        for x in cmds:
            print("\n$", x)
            print(t.cmd(x)[:6000])
    finally:
        t.close()
