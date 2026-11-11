import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import rsess

log = rsess.Log("diag.log")
c = rsess.connect()
ch, banner = rsess.open_shell(c, wait_menu=False)
log("=== BANNER ===")
log(banner.decode("utf-8", "replace")[-500:])
ch.send("0\r")
time.sleep(3)
log("=== AFTER SELECT ===")
log(rsess.read(ch, 6).decode("utf-8", "replace")[-1000:])
for cmd in ["echo MARK_START", "whoami; pwd; hostname", "nvidia-smi -L"]:
    out = rsess.send(ch, cmd, seconds=10)
    log("\n$ " + cmd)
    log(out.decode("utf-8", "replace")[-2000:])
c.close()
