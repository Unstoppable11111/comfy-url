import paramiko

hostname = "hb-a.suanjiayun.com"
port = 2020
username = "18379685528"
password = "980822cyc4435"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(hostname, port=port, username=username, password=password, timeout=10, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    print("SFTP CWD:", sftp.listdir("."))
    print("SFTP /:", sftp.listdir("/"))
    sftp.close()
finally:
    client.close()
