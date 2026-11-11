import base64, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from term import Term

local, remote = sys.argv[1], sys.argv[2]
run_args = sys.argv[3:]

data = base64.b64encode(open(local, "rb").read()).decode()
t = Term()
ch = t.ch
ch.send("stty -echo\n")
time.sleep(0.4)
ch.send(": > %s.b64\n" % remote)
time.sleep(0.3)
CH = 700
for i in range(0, len(data), CH):
    ch.send("printf '%%s' '%s' >> %s.b64\n" % (data[i:i + CH], remote))
    time.sleep(0.02)
time.sleep(0.6)
ch.send("stty echo\n")
time.sleep(0.3)
out = t.cmd("base64 -d %s.b64 > %s; wc -c %s" % (remote, remote, remote), wait=60)
print(out)
if run_args:
    print(t.cmd(" ".join(run_args), wait=180))
t.close()
