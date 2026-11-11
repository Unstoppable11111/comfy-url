# remote —— 算家云实例 SSH 工具

登录 → 进容器 → 跑命令 / 传文件的一层封装。解决两个坑：

1. 登录后不是 shell，而是「算家计算OS」的选实例菜单，必须输入 `0` 才进容器
2. 实例禁用了 SFTP 子系统，没法直接上传文件

## 文件

| 文件 | 作用 |
|---|---|
| `sjconfig.py` | 连接信息：host / port / user / 密码（读环境变量或 `.env.local`） |
| `rsess.py` | 建立 SSH 连接、打开终端、读输出 |
| `term.py` | `Term` 类：自动进容器，`cmd()` 执行命令并等结果返回 |
| `push.py` | 上传本地文件到远端并执行（base64 分块，绕开 SFTP 限制） |
| `rssh.py` | 走 `exec_command` 的简版封装（本实例会关 channel，一般用不到） |
| `selftest.py` | 连通性自检 |

## 用法

```powershell
# 密码：环境变量或 .env.local
set SJ_PWD=xxxx
# 或在本目录建 .env.local，内容一行：SJ_PWD=xxxx

python selftest.py
```

```python
from term import Term

t = Term()                      # 已自动选 0 进容器
print(t.cmd("df -h / | tail -1"))
print(t.cmd("curl -s localhost:8081/system_stats"))   # 多个命令分多次调用
t.close()
```

```powershell
python push.py 本地.py /tmp/x.py "python3 /tmp/x.py"
```

## 原理

- `Term.cmd()` 在命令尾部拼一个随机 marker（`M<时间戳>R`，故意拆成两段写入，避免被终端回显误判），读到 marker 就认为命令结束
- 实例已关机时，菜单会返回「没有获取到设备」，`Term()` 会直接抛 `RuntimeError` 提示开机
- 大文件传输：先 `stty -echo` 关回显，再按 700 字节一行 `printf` 追加 base64，最后 `base64 -d` 还原

## 注意

- 只接受一个交互终端；一次 `Term()` 占一个 SSH 会话，用完记得 `t.close()`
- 命令里避免出现单引号套单引号，容易被 shell 吃掉
