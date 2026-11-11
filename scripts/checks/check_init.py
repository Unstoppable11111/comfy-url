import paramiko, time, re

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('hb-a.suanjiayun.com', port=2020, username='18379685528', password='980822cyc4435', timeout=10, allow_agent=False, look_for_keys=False)
shell = client.invoke_shell()
time.sleep(1); shell.send('0\n'); time.sleep(1.5); shell.send('\n'); time.sleep(0.5)
shell.send("sed -n '380,440p' /ComfyUI/comfy/ldm/qwen_image/model.py\n")
time.sleep(2)
res = shell.recv(8192).decode('utf-8', errors='ignore')
print(re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', res))
client.close()
