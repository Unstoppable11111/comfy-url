import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import rsess

c = rsess.connect()
ch = c.invoke_shell(term="xterm", width=240, height=60)
ch.settimeout(1.0)
rsess.read(ch, 3)
ch.send("0")
time.sleep(1)
ch.send("\n")
rsess.read(ch, 8)

def cmd(command, wait=25, idle=2.5):
    mark = "____DONE%d____" % int(time.time() * 1000)
    ch.send(command + "\n")
    buf = b""
    end = time.time() + wait
    while time.time() < end:
        try:
            d = ch.recv(131072)
            if d:
                buf += d
                if mark.encode() in buf:
                    break
                end = max(end, time.time() + idle)
        except Exception:
            time.sleep(0.15)
    ch.send("echo " + mark + "\n")
    # read until marker
    end2 = time.time() + 15
    while time.time() < end2:
        try:
            d = ch.recv(131072)
            if d:
                buf += d
                if mark.encode() in buf:
                    break
        except Exception:
            time.sleep(0.15)
    text = buf.decode("utf-8", "replace")
    i = text.find(mark)
    if i >= 0:
        text = text[:i]
    lines = text.replace("\r\n", "\n").replace("\r", "").split("\n")
    if lines and lines[0].strip().startswith(command.strip()[:15]):
        lines = lines[1:]
    return "\n".join(lines).strip()

cmds = [
    "hostname; date; uname -r; nproc; free -g | head -2",
    "nvidia-smi",
    "df -h / /root /root/autodl-tmp 2>/dev/null",
    "ps -eo pid,ppid,stat,etime,pcpu,rss,args --sort=-pcpu | head -25",
    "ps aux | grep -Ei 'pip|conda|python|wget|curl|git clone|aria2' | grep -v grep | head -20",
]
out = open("diag2.log", "w", encoding="utf-8")
for x in cmds:
    r = cmd(x)
    out.write("\n$ " + x + "\n" + r + "\n")
    out.flush()
    print("\n$", x)
    print(r[:4000])
c.close()
out.close()
