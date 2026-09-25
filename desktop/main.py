# -*- coding: utf-8 -*-
"""桌面外壳：用 pywebview 包一层，双击即可在原生窗口里使用（无需浏览器）。

用法:  python desktop/main.py
依赖:  pip install pywebview
"""
import os
import socket
import sys
import threading

# 无论从哪个目录启动，都把项目根目录加入 sys.path，确保能 import paperreader 包
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _free_port(start=5000):
    """找一个空闲端口，避免上次实例残留导致 5000 被占而启动失败。"""
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def main():
    from paperreader.serve import create_app
    app = create_app()
    port = _free_port()
    url = "http://127.0.0.1:%d" % port

    def run_server():
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    try:
        import webview
    except ImportError:
        print("缺少 pywebview：pip install pywebview")
        print("已启动本地服务，可直接用浏览器打开 %s" % url)
        run_server()
        return

    threading.Thread(target=run_server, daemon=True).start()

    webview.create_window(
        "paperreader · 任意文献交互阅读器",
        url,
        width=1200, height=800,
    )
    webview.start()


if __name__ == "__main__":
    main()
