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
    shell = client.invoke_shell(term='vt100')
    time.sleep(2)
    print("Initial:", shell.recv(4096).decode('utf-8', errors='ignore'))
    shell.send("0\r")
    time.sleep(2)
    print("After 0\\r:", shell.recv(4096).decode('utf-8', errors='ignore'))
    shell.send("\r")
    time.sleep(2)
    print("After \\r:", shell.recv(4096).decode('utf-8', errors='ignore'))
finally:
    client.close()
