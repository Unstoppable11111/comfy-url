import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import rsess

class Term:
    def __init__(self):
        self.c = rsess.connect()
        self.ch = self.c.invoke_shell(term="xterm", width=240, height=60)
        self.ch.settimeout(1.0)
        banner = rsess.read(self.ch, 3).decode("utf-8", "replace")
        if "没有获取到设备" in banner or "请开机" in banner:
            self.c.close()
            raise RuntimeError("实例已关机：请在算家云控制台开机后再运行")
        self.ch.send("0")
        time.sleep(1)
        self.ch.send("\n")
        rsess.read(self.ch, 8)

    def cmd(self, command, wait=30):
        tok = "M%s" % int(time.time() * 1000)
        # marker split so the echoed input does not contain the literal token
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
        # drop the echoed command line
        lines = text.split("\n")
        if lines:
            lines = lines[1:]
        return "\n".join(lines).strip()

    def close(self):
        try:
            self.c.close()
        except Exception:
            pass

if __name__ == "__main__":
    cmds = sys.argv[1:]
    t = Term()
    for x in cmds:
        print("\n$", x)
        print(t.cmd(x)[:6000])
    t.close()
