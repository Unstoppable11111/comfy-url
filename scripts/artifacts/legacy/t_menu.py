import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import rsess

c = rsess.connect()
ch = c.invoke_shell(term="xterm", width=220, height=50)
ch.settimeout(1.0)
print("BANNER:", rsess.read(ch, 3).decode("utf-8", "replace")[-200:])

for step in ["0", "\n"]:
    ch.send(step)
    print(f"--- sent {step!r} ---")
    print(repr(rsess.read(ch, 8))[:600])
print("--- now send echo test ---")
ch.send("echo HI_THERE\n")
print(repr(rsess.read(ch, 8))[:600])
c.close()
