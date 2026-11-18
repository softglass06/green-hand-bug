# -*- coding: utf-8 -*-
"""
renderer.py —— 动态网页渲染模块（可选）
========================================
有些网站的正文是 JavaScript 动态加载的，普通的 requests 抓不到。
这个文件用 Selenium 驱动一个真正的浏览器（默认用 Windows 自带的 Edge），
把网页"渲染"出来，再返回渲染后的 HTML。

小白读法：
普通爬虫只会"读"网页源代码；这个模块会"打开一个真浏览器"，
让网页里的 JS 跑完、内容都显示出来之后，再把网页文字抓回来。

注意：这是可选的。只有界面里勾选了「动态渲染」才会用到它；
不勾选时完全不需要安装 selenium。
"""


def render_html(url, timeout=20):
    """用浏览器打开网页，等它渲染完成后，返回页面的 HTML 文字。

    参数：
        url：要渲染的网址。
        timeout：最多等多少秒（含浏览器启动和页面加载）。

    返回：
        渲染后的 HTML 文字（字符串）。
    """
    try:
        from selenium import webdriver                       # 延迟导入
        from selenium.webdriver.edge.options import Options   # Edge 的配置
    except ImportError as error:
        raise RuntimeError(
            "需要先安装 selenium 才能使用「动态渲染」功能，"
            "请在命令行运行：pip install selenium"
        ) from error

    options = Options()
    options.add_argument("--headless")            # 无头模式：不弹出浏览器窗口
    options.add_argument("--disable-gpu")         # 关掉 GPU，减少报错
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")
    # 去掉"我是自动化工具"的痕迹，降低被反爬识别的概率
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Edge(options=options)      # 用 Windows 自带的 Edge
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)                            # 打开网页（会执行 JS）
        import time
        time.sleep(2)                              # 再等一下，让动态内容加载完
        return driver.page_source                  # 返回渲染后的 HTML
    finally:
        driver.quit()                              # 无论成功失败都关闭浏览器
