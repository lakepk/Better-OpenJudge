"""OpenJudge 桌面应用入口

双击运行或命令行启动，在原生窗口中打开 OpenJudge 网站。

依赖: pip install pywebview
打包: pyinstaller --onefile --windowed --name OpenJudge desktop.py
"""

import webview

URL = 'https://24.199.100.61/openjudge/'

if __name__ == '__main__':
    webview.create_window(
        title='OpenJudge',
        url=URL,
        width=1200,
        height=800,
        min_size=(800, 600),
        resizable=True,
        fullscreen=False,
    )
    webview.start()
