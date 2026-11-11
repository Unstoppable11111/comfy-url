import sys, time, socket
import paramiko

from sjconfig import HOST, PORT, USER, PWD

def connect(timeout=25):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PWD,
              timeout=timeout, banner_timeout=timeout, auth_timeout=timeout,
              look_for_keys=False, allow_agent=False)
    return c

def run(c, cmd, timeout=90):
    chan = c.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out, err = b"", b""
    deadline = time.time() + timeout
    while True:
        if chan.recv_ready():
            out += chan.recv(65536)
        if chan.recv_stderr_ready():
            err += chan.recv_stderr(65536)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        if time.time() > deadline:
            chan.close()
            return out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), "TIMEOUT"
        time.sleep(0.05)
    rc = chan.recv_exit_status()
    chan.close()
    return out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), rc

if __name__ == "__main__":
    cmds = sys.argv[1:]
    if not cmds:
        cmds = [sys.stdin.read()]
    try:
        c = connect()
    except Exception as e:
        print("CONNECT_FAILED:", type(e).__name__, e)
        sys.exit(1)
    for cmd in cmds:
        o, e, rc = run(c, cmd)
        print(f"\n$ {cmd}")
        print(o, end="")
        if e.strip():
            print("[stderr]", e, end="")
        print(f"[rc={rc}]")
    c.close()
