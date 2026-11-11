import sys, time, re
import paramiko

HOST, PORT, USER, PWD = "hb-a.suanjiayun.com", 2020, "18379685528", "980822cyc4435"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PWD, timeout=25,
              banner_timeout=25, auth_timeout=25, look_for_keys=False, allow_agent=False)
    return c

class Sh:
    def __init__(self, c):
        self.chan = c.invoke_shell(term="xterm", width=200, height=50)
        self.chan.settimeout(30)
        self.buf = ""
        time.sleep(1.0)
        self.drain()
        self.n = 0
    def drain(self):
        try:
            while True:
                if self.chan.recv_ready():
                    self.buf += self.chan.recv(65536).decode("utf-8", "replace")
                else:
                    break
        except Exception:
            pass
    def cmd(self, command, timeout=60):
        self.n += 1
        mark = f"__END_{self.n}_{int(time.time())}__"
        self.chan.send(f"{command}; echo {mark} $?\n")
        deadline = time.time() + timeout
        out = ""
        while time.time() < deadline:
            if self.chan.recv_ready():
                out += self.chan.recv(65536).decode("utf-8", "replace")
                if mark in out:
                    break
            else:
                time.sleep(0.05)
                if mark in out:
                    break
        idx = out.find(mark)
        body = out[:idx] if idx >= 0 else out + "\n<<TIMEOUT>>"
        # strip echoed command line
        lines = body.split("\n")
        if lines and command[:20] in lines[0]:
            lines = lines[1:]
        return "\n".join(lines).rstrip(), (out[idx:].split("\n")[0] if idx >= 0 else "?")

if __name__ == "__main__":
    cmds = sys.argv[1:]
    c = connect()
    sh = Sh(c)
    for cmd in cmds:
        out, rc = sh.cmd(cmd)
        print(f"\n$ {cmd}\n{out}\n[rc {rc}]")
    c.close()
