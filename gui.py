# -*- coding: utf-8 -*-
"""
gui.py —— 图形界面（双击打开就能用的傻瓜版）
============================================
这个文件负责提供一个"图形窗口"：
用户不用碰命令行，直接在这个窗口里输入网址、点按钮就能爬取。

小白读法：
这是给"完全不想看代码"的人准备的界面。
你双击「启动爬虫.bat」，就会弹出这个窗口，
照着窗口里的提示一步步操作就行。
"""

# ---------- 第一部分：导入工具 ----------

# 下面这几个都是 Python 自带的库，不需要额外安装。
import tkinter as tk                                  # tkinter：Python 自带的"做窗口界面"工具
from tkinter import messagebox                        # messagebox：用来弹出"提示/错误"小弹窗
from tkinter import scrolledtext                      # scrolledtext：带滚动条的文本框（用来显示结果）
import threading                                      # threading：用来开"后台线程"，避免界面卡死
import os                                             # os：用来处理文件路径、打开文件夹
import subprocess                                     # subprocess：备用，用来在非 Windows 系统上打开文件夹

# 下面这两个是我们自己写的模块（爬虫 + 导出），需要先安装第三方库才能导入成功。
try:
    import crawler                                    # 导入爬虫模块
    import exporter                                   # 导入导出模块
except ImportError as error:                          # 如果导入失败（说明没装 requests/bs4/openpyxl）
    root = tk.Tk()                                    # 临时创建一个窗口
    root.withdraw()                                   # 把这个窗口隐藏，只显示下面的弹窗
    # 弹出一个错误提示，告诉用户怎么解决
    messagebox.showerror(
        "缺少依赖",
        "检测到缺少组件，请先安装依赖：\n\n"
        "pip install -r requirements.txt\n\n"
        "错误信息：" + str(error),
    )
    raise SystemExit(1)                               # 直接退出程序


# ---------- 第二部分：整理网址 ----------

def normalize_url(raw):
    """把用户输入的网址整理成规范形式（自动补 https://）。

    参数：
        raw：用户输入的原始网址文字。

    返回：
        整理好的网址；如果是空的，返回 None。
    """
    url = raw.strip()                                 # 去掉首尾空格
    if not url:                                       # 如果是空的
        return None                                   # 返回 None
    if not url.startswith(("http://", "https://")):   # 如果没有 http/https 开头
        url = "https://" + url                        # 自动补上 https://
    return url                                        # 返回整理好的网址


# ---------- 第三部分：往结果框里追加文字 ----------

def append_text(text):
    """往结果文本框里追加一行文字，并自动滚动到最底部。

    参数：
        text：要追加的文字。
    """
    text_box.config(state="normal")                   # 先允许编辑
    text_box.insert("end", text + "\n")               # 在末尾追加文字（\n 表示换行）
    text_box.see("end")                               # 自动滚动到最底部
    text_box.config(state="disabled")                 # 再禁止编辑（保持只读）


# ---------- 第四部分：爬取逻辑（在后台线程里运行） ----------

def do_crawl(url, keyword):
    """真正执行爬取的函数（在后台线程里运行，避免界面卡死）。

    参数：
        url：要爬取的网址。
        keyword：要检索的关键词（可为空，为空表示不检索）。
    """
    try:
        data = crawler.crawl(url, keyword or None)    # 调用爬虫抓取并分析网页（关键词为空就传 None）
        output_path = exporter.make_output_path(url)  # 计算 Excel 的保存路径
        exporter.export_to_excel(data, output_path)   # 把数据写成 Excel 文件
        # root.after(0, ...) 的作用：把"更新界面"这件事，从后台线程切回主线程执行。
        # 因为 tkinter 规定只有主线程才能修改界面，所以必须用 after 切回去。
        root.after(0, on_success, data, output_path)
    except Exception as error:                        # 如果爬取过程中出错
        root.after(0, on_error, str(error))           # 切回主线程去显示错误


def on_success(data, output_path):
    """爬取成功后，更新界面（在主线程里执行）。"""
    append_text("✅ 爬取完成！")                       # 显示完成
    append_text("网页标题：" + data["标题"])           # 显示标题
    append_text("网页类型：" + data["网页类型"])       # 显示网页类型
    append_text("找到表格：" + str(len(data["表格"])) + " 个")
    append_text("找到列表：" + str(len(data["列表"])) + " 条")
    append_text("找到正文段落：" + str(len(data["正文"])) + " 段")
    append_text("找到图片：" + str(len(data["图片"])) + " 张")

    # 如果做了关键词检索，把检索结果也显示出来
    search = data.get("关键词检索")
    if search:
        append_text("")
        keyword = search["关键词"]
        total = search["总次数"]
        if total > 0:
            append_text("🔍 关键词「" + keyword + "」共出现 " + str(total) + " 次：")
            for item in search["结果"][:20]:          # 窗口里最多显示前 20 条，避免刷屏
                append_text("   · [" + item["区域"] + "] " + item["片段"])
            if len(search["结果"]) > 20:
                append_text("   … 其余 " + str(len(search["结果"]) - 20) + " 处请在 Excel 的「关键词检索」工作表查看")
        else:
            append_text("🔍 未找到关键词「" + keyword + "」")

    append_text("📊 已生成 Excel：" + output_path)     # 显示保存路径
    append_text("")                                   # 空一行
    append_text("点下面的「打开结果文件夹」即可查看生成的表格。")

    status_label.config(text="✅ 完成")                # 更新状态栏文字
    crawl_button.config(state="normal")               # 恢复"开始爬取"按钮
    open_button.config(state="normal")                # 启用"打开结果文件夹"按钮


def on_error(error_text):
    """爬取失败时，更新界面（在主线程里执行）。"""
    append_text("❌ 爬取失败：" + error_text)          # 显示错误信息
    append_text("提示：请检查网址是否正确、网络是否畅通。")
    status_label.config(text="❌ 失败")                # 更新状态栏
    crawl_button.config(state="normal")               # 恢复"开始爬取"按钮
    messagebox.showerror("爬取失败", error_text)       # 弹窗提示错误


# ---------- 第五部分：点击"开始爬取"按钮时触发 ----------

def start_crawl():
    """用户点击「开始爬取」按钮后执行的函数。"""
    url = normalize_url(entry.get())                  # 取出输入框里的网址并整理
    if not url:                                       # 如果网址是空的
        messagebox.showwarning("提示", "请先输入网址！")  # 弹窗提醒
        return                                        # 直接返回，不往下执行

    keyword = keyword_entry.get().strip()             # 取出关键词（可为空）

    crawl_button.config(state="disabled")             # 禁用按钮，防止重复点击
    open_button.config(state="disabled")              # 暂时禁用"打开文件夹"按钮
    status_label.config(text="⏳ 正在爬取…")          # 更新状态栏文字

    text_box.config(state="normal")                   # 允许编辑文本框
    text_box.delete("1.0", "end")                     # 清空上次的结果
    text_box.config(state="disabled")                 # 重新设为只读
    append_text("正在爬取：" + url)                    # 显示正在爬取的网址
    if keyword:                                       # 如果填了关键词
        append_text("检索关键词：" + keyword)          # 显示要检索的关键词
    append_text("请稍候，可能需要几秒钟…")            # 提示等待

    # 开一个后台线程执行爬取，这样界面不会"卡死"。
    # daemon=True 表示：主程序退出时，这个线程也跟着一起结束。
    threading.Thread(target=do_crawl, args=(url, keyword), daemon=True).start()


# ---------- 第六部分：打开结果文件夹 ----------

def open_output_folder():
    """用系统资源管理器打开 output 文件夹。"""
    if os.name == "nt":                               # 如果是 Windows 系统
        os.startfile(exporter.OUTPUT_DIR)             # 直接打开 output 文件夹
    else:                                             # 如果是 Mac / Linux
        subprocess.Popen(["xdg-open", exporter.OUTPUT_DIR])  # 用系统命令打开


# ---------- 第七部分：搭建界面 ----------

# 创建主窗口
root = tk.Tk()
root.title("小白爬虫工具")                            # 窗口标题
root.geometry("640x620")                              # 窗口初始大小（宽 x 高）
root.configure(bg="#f5f6fa")                          # 窗口背景色

# --- 顶部标题 ---
title_label = tk.Label(
    root,
    text="🕷️ 小白爬虫工具",
    font=("微软雅黑", 18, "bold"),
    bg="#f5f6fa",
    fg="#2c3e50",
)
title_label.pack(pady=(16, 4))                        # 放到窗口里，上下留一点间距

# --- 使用说明（引导用户一步步操作） ---
guide_text = (
    "使用说明（照着做就行）：\n"
    "① 在网址输入框里，粘贴或输入要爬取的网址\n"
    "② 可选：在关键词输入框里填一个词，程序会在网页里检索它\n"
    "③ 点击「开始爬取」按钮\n"
    "④ 等待几秒，程序会自动分析并生成 Excel 表格\n"
    "⑤ 点击「打开结果文件夹」，查看生成的表格"
)
guide_label = tk.Label(
    root,
    text=guide_text,
    font=("微软雅黑", 11),
    bg="#f5f6fa",
    fg="#555555",
    justify="left",                                   # 多行文字左对齐
    anchor="w",                                       # 文字靠左
)
guide_label.pack(fill="x", padx=24, pady=(0, 8))      # 左右留边距

# --- 网址输入行 ---
input_frame = tk.Frame(root, bg="#f5f6fa")            # 用一个"容器"把标签和输入框放一起
input_frame.pack(fill="x", padx=24, pady=4)

url_label = tk.Label(
    input_frame,
    text="网址：",
    font=("微软雅黑", 12),
    bg="#f5f6fa",
)
url_label.pack(side="left")                           # 标签靠左

entry = tk.Entry(input_frame, font=("微软雅黑", 12))  # 网址输入框
entry.pack(side="left", fill="x", expand=True, padx=(6, 0))  # 输入框占满剩余宽度
entry.bind("<Return>", lambda event: start_crawl())   # 按回车键也能触发爬取

# --- 小提示 ---
hint_label = tk.Label(
    root,
    text="提示：可以省略 https://，例如直接输入 www.baidu.com 就行",
    font=("微软雅黑", 9),
    bg="#f5f6fa",
    fg="#999999",
)
hint_label.pack(anchor="w", padx=24, pady=(2, 6))     # 靠左显示

# --- 关键词输入行（可选） ---
keyword_frame = tk.Frame(root, bg="#f5f6fa")          # 用一个"容器"放关键词标签和输入框
keyword_frame.pack(fill="x", padx=24, pady=4)

keyword_label = tk.Label(
    keyword_frame,
    text="关键词：",
    font=("微软雅黑", 12),
    bg="#f5f6fa",
)
keyword_label.pack(side="left")                       # 标签靠左

keyword_entry = tk.Entry(keyword_frame, font=("微软雅黑", 12))  # 关键词输入框
keyword_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))
keyword_entry.bind("<Return>", lambda event: start_crawl())  # 按回车也能触发爬取

# --- 关键词小提示 ---
keyword_hint = tk.Label(
    root,
    text="可选：填了关键词，就会在网页里检索它出现在哪些地方；留空则只爬取不检索",
    font=("微软雅黑", 9),
    bg="#f5f6fa",
    fg="#999999",
)
keyword_hint.pack(anchor="w", padx=24, pady=(2, 6))   # 靠左显示

# --- 开始按钮 ---
crawl_button = tk.Button(
    root,
    text="开始爬取",
    font=("微软雅黑", 13, "bold"),
    bg="#27ae60",
    fg="white",
    activebackground="#219150",                       # 鼠标按下时的颜色
    relief="flat",                                    # 去掉按钮凸起边框
    padx=20,
    pady=6,
    command=start_crawl,                              # 点击按钮时调用 start_crawl
)
crawl_button.pack(pady=6)

# --- 状态栏 ---
status_label = tk.Label(
    root,
    text="等待输入网址…",
    font=("微软雅黑", 10),
    bg="#f5f6fa",
    fg="#666666",
)
status_label.pack(pady=(2, 4))

# --- 结果文本框（带滚动条） ---
text_box = scrolledtext.ScrolledText(
    root,
    font=("微软雅黑", 10),
    height=12,
    wrap="word",                                      # 单词太长时自动换行
    state="disabled",                                 # 初始设为只读
    bg="#ffffff",
)
text_box.pack(fill="both", expand=True, padx=24, pady=(0, 8))

# --- 打开文件夹按钮 ---
open_button = tk.Button(
    root,
    text="打开结果文件夹",
    font=("微软雅黑", 11),
    bg="#3498db",
    fg="white",
    activebackground="#2c81ba",                       # 鼠标按下时的颜色
    relief="flat",
    padx=16,
    pady=4,
    state="disabled",                                 # 初始禁用（还没爬过，无结果可开）
    command=open_output_folder,                       # 点击时打开 output 文件夹
)
open_button.pack(pady=(0, 12))

# 进入 tkinter 的"消息循环"，让窗口一直显示、持续响应操作。
root.mainloop()
