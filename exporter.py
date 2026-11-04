# -*- coding: utf-8 -*-
"""
exporter.py —— 导出模块
================================
这个文件负责：把爬虫抓到的数据，自动写成一个 Excel 文件（.xlsx）。

小白读法：
你可以把这个文件想象成一个"抄写员"。
侦探（crawler.py）把信息找回来之后，
抄写员就把这些信息工工整整地抄进一个 Excel 表格里，方便你查看。
"""

# ---------- 第一部分：导入需要用到的工具包 ----------

# os 是 Python 自带的工具，用来处理"文件路径"（比如拼接文件夹路径）。
import os

# re 是 Python 自带的"正则表达式"工具，用来清洗文件名里的非法字符。
import re

# datetime 是 Python 自带的"日期时间"工具，用来给生成的文件加上时间戳。
from datetime import datetime

# openpyxl 是第三方库，用来"读写 Excel 文件"。
import openpyxl

# 下面三个是 openpyxl 里的"样式"工具，用来让表格更好看。
from openpyxl.styles import Font, PatternFill


# ---------- 第二部分：计算输出路径 ----------

# 输出文件夹的路径：这个程序所在目录下的 output 文件夹。
# __file__ 表示"当前这个文件（exporter.py）自己的路径"。
# os.path.dirname 取它所在的文件夹，os.path.abspath 把它变成绝对路径。
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def make_output_path(url):
    """根据网址，生成一个"带时间戳 + 网站名"的 Excel 文件完整路径。

    参数：
        url：爬取的网址。

    返回：
        生成的 .xlsx 文件的完整路径（字符串）。
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)       # 如果 output 文件夹不存在，就自动创建（存在则不报错）

    # 从网址里取出"域名"（例如 https://www.baidu.com/xxx -> www.baidu.com）。
    domain = url.split("//")[-1].split("/")[0]

    # 把域名里"不能出现在文件名里"的字符，替换成下划线。
    # 允许保留：字母、数字、中文、下划线、连字符、点。
    domain = re.sub(r"[^0-9a-zA-Z一-龥._-]", "_", domain)

    # 生成时间戳，例如 20261028_153045（年月日_时分秒）。
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 拼接最终文件名，例如 20261028_153045_www.baidu.com.xlsx。
    filename = f"{timestamp}_{domain}.xlsx"

    # 返回"文件夹路径 + 文件名"的完整路径。
    return os.path.join(OUTPUT_DIR, filename)


# ---------- 第三部分：给表头加样式 ----------

def _style_header(ws, row=1, col_count=1):
    """把某个工作表的第一行（表头行）加粗、加上浅蓝底色。

    参数：
        ws：要处理的工作表对象。
        row：表头在第几行（默认第 1 行）。
        col_count：表头一共几列。
    """
    for col in range(1, col_count + 1):          # 遍历每一列
        cell = ws.cell(row=row, column=col)      # 拿到这个格子
        cell.font = Font(bold=True)              # 字体加粗
        cell.fill = PatternFill("solid", fgColor="DDEBF7")  # 填充浅蓝色背景


# ---------- 第四部分：自动调整列宽 ----------

def _auto_width(ws, max_width=60):
    """根据每列内容的长度，自动调整这一列的宽度。

    参数：
        ws：要处理的工作表对象。
        max_width：单列最宽不超过多少（避免某列被一个超长链接撑爆）。
    """
    for column in ws.columns:                    # 遍历工作表的每一列
        max_len = 0                              # 记录这一列最长的内容长度
        letter = column[0].column_letter         # 拿到这一列的"列字母"（如 A、B、C）
        for cell in column:                      # 遍历这一列的每个格子
            if cell.value is not None:           # 如果格子有内容
                text = str(cell.value)           # 把内容转成字符串
                # 计算文字长度：中文等全角字符占 2 个宽度，普通字符占 1 个宽度。
                length = sum(2 if ord(ch) > 127 else 1 for ch in text)
                max_len = max(max_len, length)   # 更新最长长度
        # 设置列宽：最长长度 + 2（留点边），并且不超过 max_width 上限。
        ws.column_dimensions[letter].width = min(max_len + 2, max_width)


# ---------- 第五部分：把数据写进 Excel ----------

def export_to_excel(data, output_path):
    """把爬虫结果 data 写成一个 Excel 文件，并保存到 output_path。

    会创建多个工作表（有多少数据就建多少）：
    - "网页信息"：网址、标题、网页类型、描述
    - "表格1"、"表格2"...：网页里的每个表格各占一个工作表
    - "列表数据"：网页里的列表条目
    - "正文段落"：网页正文的段落
    - "图片链接"：网页里的图片网址

    参数：
        data：爬虫返回的字典（就是 crawler.crawl 的返回值）。
        output_path：要保存到的 .xlsx 文件完整路径。

    返回：
        保存的文件路径。
    """
    wb = openpyxl.Workbook()                     # 新建一个空白的 Excel 工作簿
    info_ws = wb.active                          # 拿到默认的第一个工作表
    info_ws.title = "网页信息"                   # 把它的名字改成"网页信息"

    # ---- 工作表1：网页信息 ----
    info_rows = [                                # 准备要写入的几行"字段名 + 内容"
        ("网址", data.get("网址", "")),
        ("标题", data.get("标题", "")),
        ("网页类型", data.get("网页类型", "")),
        ("描述", data.get("描述", "")),
    ]
    for row_index, (key, value) in enumerate(info_rows, start=1):  # 从第 1 行开始写
        info_ws.cell(row=row_index, column=1, value=key)    # 第 1 列写"字段名"
        info_ws.cell(row=row_index, column=2, value=value)  # 第 2 列写"内容"
    _style_header(info_ws, row=1, col_count=2)   # 给第一行加粗上色
    _auto_width(info_ws)                         # 自动调整列宽

    # ---- 工作表2、3、4...：每个表格一个工作表 ----
    for table in data.get("表格", []):           # 遍历爬到的所有表格
        sheet_name = f"表格{table['序号']}"       # 工作表名字，如"表格1"
        ws = wb.create_sheet(sheet_name)         # 新建这个工作表

        headers = list(table["表头"])            # 取出表头（拷贝一份，避免影响原数据）
        rows = list(table["行"])                 # 取出数据行

        # 如果网页里的表格没有 <th> 表头，就用第一行数据当表头。
        if not headers and rows:
            headers = rows[0]                    # 第一行变成表头
            rows = rows[1:]                      # 剩下的才是数据行

        # 写表头（第 1 行）。
        for col_index, header in enumerate(headers, start=1):
            ws.cell(row=1, column=col_index, value=header)

        # 写数据行（从第 2 行开始）。
        for row_index, row_data in enumerate(rows, start=2):
            for col_index, value in enumerate(row_data, start=1):
                ws.cell(row=row_index, column=col_index, value=value)

        _style_header(ws, row=1, col_count=max(len(headers), 1))  # 表头加粗上色
        _auto_width(ws)                          # 自动调整列宽

    # ---- 工作表：列表数据 ----
    list_items = data.get("列表", [])            # 取出列表数据
    if list_items:                               # 只有列表非空时才创建这个表
        list_ws = wb.create_sheet("列表数据")    # 新建工作表
        list_ws.cell(row=1, column=1, value="列表项")  # 第 1 行写表头
        for i, item in enumerate(list_items, start=2):  # 从第 2 行开始写每一条
            list_ws.cell(row=i, column=1, value=item)
        _style_header(list_ws, row=1, col_count=1)  # 表头加粗上色
        _auto_width(list_ws)                     # 自动调整列宽

    # ---- 工作表：正文段落 ----
    paragraphs = data.get("正文", [])            # 取出正文段落
    if paragraphs:                               # 只有正文非空时才创建
        text_ws = wb.create_sheet("正文段落")    # 新建工作表
        text_ws.cell(row=1, column=1, value="段落内容")  # 第 1 行写表头
        for i, text in enumerate(paragraphs, start=2):  # 从第 2 行开始写
            text_ws.cell(row=i, column=1, value=text)
        _style_header(text_ws, row=1, col_count=1)  # 表头加粗上色
        _auto_width(text_ws)                     # 自动调整列宽

    # ---- 工作表：图片链接 ----
    images = data.get("图片", [])                # 取出图片链接
    if images:                                   # 只有图片非空时才创建
        img_ws = wb.create_sheet("图片链接")     # 新建工作表
        img_ws.cell(row=1, column=1, value="图片网址")  # 第 1 行写表头
        for i, url in enumerate(images, start=2):      # 从第 2 行开始写
            img_ws.cell(row=i, column=1, value=url)
        _style_header(img_ws, row=1, col_count=1)  # 表头加粗上色
        _auto_width(img_ws)                      # 自动调整列宽

    wb.save(output_path)                         # 把工作簿保存到指定路径
    return output_path                           # 返回保存路径
