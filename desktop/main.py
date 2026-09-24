# -*- coding: utf-8 -*-
"""桌面外壳：用 pywebview 包一层，双击即可在原生窗口里使用（无需浏览器）。

用法:  python desktop/main.py
依赖:  pip install pywebview
"""
import threading


def main():
    from paperreader.serve import create_app
    app = create_app()

    def run_server():
        app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

    try:
        import webview
    except ImportError:
        print("缺少 pywebview：pip install pywebview")
        print("已启动本地服务，可直接用浏览器打开 http://127.0.0.1:5000")
        run_server()
        return

    threading.Thread(target=run_server, daemon=True).start()

    webview.create_window(
        "paperreader · 任意文献交互阅读器",
        "http://127.0.0.1:5000",
        width=1200, height=800,
    )
    webview.start()


if __name__ == "__main__":
    main()
