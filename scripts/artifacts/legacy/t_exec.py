import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('hb-a.suanjiayun.com', 2020, '18379685528', '980822cyc4435',
          timeout=20, look_for_keys=False, allow_agent=False)

cmds = ['echo hello', 'bash -lc "echo hi"', 'id']
for cmd in cmds:
    try:
        ch = c.get_transport().open_session()
        ch.get_pty()
        ch.exec_command(cmd)
        time.sleep(4)
        d = b''
        try:
            while True:
                x = ch.recv(65536)
                if not x:
                    break
                d += x
        except Exception:
            pass
        print(cmd, '=>', repr(d)[:400])
    except Exception as e:
        print(cmd, 'EXC', e)
c.close()
