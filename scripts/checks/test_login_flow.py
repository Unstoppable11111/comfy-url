import paramiko
import time

hostname = "hb-a.suanjiayun.com"
port = 2020
username = "18379685528"
password = "980822cyc4435"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(hostname, port=port, username=username, password=password, timeout=10, allow_agent=False, look_for_keys=False)
    shell = client.invoke_shell()
    time.sleep(2)
    shell.recv(4096)
    shell.send("0\n")
    print("已发送 0\\n，等待响应...")
    for i in range(10):
        time.sleep(1)
        if shell.recv_ready():
            chunk = shell.recv(4096).decode('utf-8', errors='ignore')
            print(f"[第 {i+1} 秒输出]:\n{chunk}")
finally:
    client.close()
