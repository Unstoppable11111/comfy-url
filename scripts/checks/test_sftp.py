import paramiko

hostname = "hb-a.suanjiayun.com"
port = 2020
username = "18379685528"
password = "980822cyc4435"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(hostname, port=port, username=username, password=password, timeout=10, allow_agent=False, look_for_keys=False)
    try:
        sftp = client.open_sftp()
        print("SFTP_AVAILABLE: TRUE")
        sftp.close()
    except Exception as e:
        print("SFTP_AVAILABLE: FALSE", e)
finally:
    client.close()
