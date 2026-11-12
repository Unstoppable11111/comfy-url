"""打印登录后的菜单，确认实例序号。

    python menu.py
"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rsess

c = rsess.connect()
ch = c.invoke_shell(term="xterm", width=140, height=40)
ch.settimeout(1.0)
banner = rsess.read(ch, 6).decode("utf-8", "replace")
print("=== 登录菜单 ===")
print(banner)
print("=== 结束 ===")
ch.close()
c.close()
