# Weixin Personal Daemon

这是一个独立运行的 Python 常驻进程（不依赖 OpenClaw，单账号），迁移了以下能力：

1. 登录（扫码）
2. 在 console 显示二维码
3. 接收消息（长轮询）
4. 主动推送文本消息（由同一进程内业务逻辑调用）

## 启动

```bash
uv run weixin-daemon
```

首次运行若没有会话，会自动拉起扫码登录并在控制台打印二维码。

## 编程式集成（同进程）

```bash
uv run weixin-daemon
```

在你的业务代码里（同一个 Python 进程），直接使用：

```python
from lib.weixin_bot.daemon import PersonalWeixinDaemon

daemon = PersonalWeixinDaemon()

def on_message(event: dict) -> None:
    text = event.get("text", "")
    from_user = event.get("from_user_id", "")
    if text:
        daemon.send_text(from_user, f"收到: {text}")

daemon.add_message_handler(on_message)
daemon.run_forever()
```

你也可以在定时任务里直接调用 `daemon.send_text(to_user_id, text)`。

登录成功后会写入 `.weixin_py/session.json`，收消息过程中会维护 `.weixin_py/context_tokens.json`，发送时默认自动读取对应用户的 `context token`。

