# -*- coding: utf-8 -*-
"""
crawler.py —— 爬虫的核心模块
================================
这个文件负责两件事：
1. 抓取网页：把一个网址变成我们能分析的"网页文字"。
2. 自动分析网页：从网页里找出标题、类型、表格、列表、正文、图片。

小白读法：
你可以把这个文件想象成一个"侦探"。
你只要给侦探一个网址（比如 https://example.com），
侦探就会自动跑去那个网站，把里面有用的信息一件件找出来交给你。
"""

# ---------- 第一部分：导入需要用到的工具包 ----------

# re 是 Python 自带的"正则表达式"工具，用来做文字匹配和清洗。
import re

# Counter 是 Python 自带的"计数器"工具，用来统计"什么东西出现了多少次"。
from collections import Counter

# urljoin 是 Python 自带的工具，用来把"半截网址"补全成"完整网址"。
from urllib.parse import urljoin

# requests 是第三方库，负责"向网站发请求、拿回网页内容"。
# 第三方库 = 别人写好的、需要先用 pip 安装才能用的库。
import requests

# BeautifulSoup 是第三方库，负责"解析网页、从网页里查找内容"。
from bs4 import BeautifulSoup


# ---------- 第二部分：通用的小工具函数 ----------

def clean_text(text):
    """把一个字符串"洗干净"：去掉首尾空格，把中间的多个空白压成一个空格。

    参数：
        text：要清洗的原始文字。

    返回：
        清洗后的文字。
    """
    text = text.strip()                    # 去掉字符串开头和结尾的空格、换行
    text = re.sub(r"\s+", " ", text)       # 把中间连续的空格/换行/制表符，压缩成单个空格
    return text                            # 返回清洗好的文字


# ---------- 第三部分：抓取网页 ----------

def fetch_html(url, timeout=15):
    """根据网址，向网站请求网页内容，并返回网页的 HTML 文字。

    参数：
        url：要抓取的网址。
        timeout：最长等待多少秒，超过就报错（默认 15 秒）。

    返回：
        网页的 HTML 文字（字符串）。
    """
    # 伪装成"浏览器"的身份去访问。
    # 有些网站会拒绝"爬虫程序"的访问，带上浏览器标识（User-Agent）能降低被拒绝的概率。
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    # 用 GET 方式请求网页（GET 就是"去拿一个网页"最常用的方式）。
    response = requests.get(url, headers=headers, timeout=timeout)

    # 如果网站返回了错误状态码（例如 404 找不到页面），这里会直接抛出异常。
    response.raise_for_status()

    # 处理中文乱码问题：
    # 如果网站没告诉我们编码，或者给的编码是 iso-8859-1（这种编码常导致中文乱码），
    # 就让 requests 自己"猜"一个更准确的编码。
    if response.encoding is None or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding

    # 返回网页的纯文字内容（HTML 代码）。
    return response.text


# ---------- 第四部分：自动识别网页类型 ----------

def detect_page_type(soup):
    """自动判断"这个网页到底是什么类型的"。

    判断规则（按优先级从上到下）：
    1. 网页里有 <article> 标签            -> 文章/新闻型
    2. 网页里有 <table> 表格，且表格里有内容 -> 表格型
    3. 网页里有很多 <li> 列表项            -> 列表型
    4. 网页里有很多 <p> 段落               -> 文章/新闻型
    5. 以上都不符合                       -> 普通网页

    参数：
        soup：已经解析好的网页对象。

    返回：
        一个中文的"网页类型"标签。
    """
    # 统计网页里各种"线索"标签的数量。
    article_count = len(soup.find_all("article"))   # <article> 文章标签的数量
    table_count = len(soup.find_all("table"))       # <table> 表格的数量
    li_count = len(soup.find_all("li"))             # <li> 列表项的数量
    p_count = len(soup.find_all("p"))               # <p> 段落的数量

    # 线索1：只要有 <article> 标签，基本就是文章/新闻页。
    if article_count > 0:
        return "文章/新闻型"

    # 线索2：只要有一个及以上的表格，就判断为"表格型"。
    if table_count > 0:
        return "表格型"

    # 线索3：列表项 >= 5 个，判断为"列表型"。
    if li_count >= 5:
        return "列表型"

    # 线索4：段落 >= 5 个，判断为"文章/新闻型"。
    if p_count >= 5:
        return "文章/新闻型"

    # 兜底：什么都对不上，就当成"普通网页"。
    return "普通网页"


# ---------- 第五部分：提取标题和描述 ----------

def extract_title(soup):
    """提取网页的标题。

    优先取 <title> 标签里的文字；如果没有，再退而求其次取第一个 <h1>。

    参数：
        soup：已经解析好的网页对象。

    返回：
        网页标题（字符串）。
    """
    title_tag = soup.find("title")          # 查找网页里的 <title> 标签
    if title_tag is not None:               # 如果找到了 <title> 标签
        title = clean_text(title_tag.get_text())   # 取出它的文字并清洗
        if title:                           # 如果清洗后不是空字符串
            return title                    # 返回这个标题

    h1_tag = soup.find("h1")                # 没找到标题，就找第一个 <h1> 大标题
    if h1_tag is not None:                  # 如果找到了 <h1> 标签
        return clean_text(h1_tag.get_text())      # 返回清洗后的文字

    return "（未找到标题）"                   # 实在找不到，返回一个提示文字


def extract_meta_description(soup):
    """提取网页的"描述"（网页作者写在 <meta> 里的一段简介）。

    参数：
        soup：已经解析好的网页对象。

    返回：
        网页描述（字符串），找不到时返回空字符串。
    """
    meta = soup.find("meta", attrs={"name": "description"})  # 查找 name="description" 的 meta 标签
    if meta is None:                         # 如果没找到这个标签
        return ""                            # 直接返回空字符串
    return clean_text(meta.get("content", ""))  # 返回标签里 content 属性的文字并清洗


# ---------- 第六部分：提取表格 ----------

def extract_tables(soup):
    """提取网页里所有的 <table> 表格。

    每个表格会变成一个字典，包含三样东西：
    - "序号"：这是网页里的第几个表格
    - "表头"：每一列的标题（来自 <th> 标签）
    - "行"  ：表格里的一行行数据（来自 <tr> 标签）

    参数：
        soup：已经解析好的网页对象。

    返回：
        一个列表，列表里是一个个"表格字典"。
    """
    tables = []                              # 用一个空列表，准备装所有表格

    # enumerate 会一边遍历一边给每个表格编上"序号"（从 0 开始）。
    for index, table in enumerate(soup.find_all("table")):
        headers = []                         # 用来装当前表格的"表头"
        rows = []                            # 用来装当前表格的"数据行"

        # 第一步：找表头（<th> 标签，一般放在表格最上面或最左边）。
        for th in table.find_all("th"):      # 遍历这个表格里所有的 <th> 标签
            header_text = clean_text(th.get_text())  # 取出文字并清洗
            if header_text:                  # 如果不是空文字
                headers.append(header_text)  # 就加入表头列表

        # 第二步：找数据行（<tr> 标签，代表表格里的"一行"）。
        for tr in table.find_all("tr"):      # 遍历这个表格里所有的 <tr> 行
            cells = []                       # 用来装这一行的每个格子
            # 每个格子可能是 <td>（普通单元格）也可能是 <th>（表头单元格），两个都要抓。
            for cell in tr.find_all(["td", "th"]):
                cell_text = clean_text(cell.get_text())  # 取出格子文字并清洗
                cells.append(cell_text)      # 加入当前行
            if cells:                        # 如果这一行有内容（不是空行）
                rows.append(cells)           # 就把整行加入 rows

        # 把当前表格的信息打包成一个字典，追加到 tables 列表里。
        tables.append({"序号": index + 1, "表头": headers, "行": rows})

    return tables                            # 返回所有表格


# ---------- 第七部分：提取列表 ----------

def _extract_repeated_cards(soup):
    """提取网页里"重复出现的卡片/条目"（比如商品卡片、新闻条目）。

    思路：
    很多网站的列表不是用 <li> 写的，而是用一堆"长得一样"的 div 卡片。
    我们统计每种"标签名 + class 名"出现了多少次，
    出现次数最多、且 >= 3 次的那种，就很可能是"列表里的重复条目"。

    参数：
        soup：已经解析好的网页对象。

    返回：
        一个列表，装的是提取到的文字条目。
    """
    counts = Counter()                       # 用一个计数器，统计每种元素出现多少次

    # find_all(True) 表示"找出网页里所有的标签"。
    for el in soup.find_all(True):
        cls = el.get("class")                # 取出这个标签的 class 属性
        if not cls:                          # 如果这个标签没有 class，先跳过（减少干扰）
            continue
        # 用"标签名 + class 名"拼成一个身份标识，例如 "div.product-card"。
        key = el.name + "." + ".".join(cls)
        counts[key] += 1                     # 这种身份出现次数 +1

    # 如果没有统计到任何元素，直接返回空列表。
    if not counts:
        return []

    # 找出出现次数最多的那一种身份。
    best_key, best_count = counts.most_common(1)[0]

    # 如果出现次数 < 3，说明网页里没有明显的"重复条目"，返回空列表。
    if best_count < 3:
        return []

    # 把身份标识拆回"标签名"和"class 列表"。
    parts = best_key.split(".")              # 例如 ["div", "product-card"]
    tag_name = parts[0]                      # 第一个是标签名 "div"
    class_list = parts[1:]                   # 剩下的都是 class 名 ["product-card"]

    results = []                             # 准备装结果
    # 重新找出所有符合"这个身份"的元素，提取文字。
    for el in soup.find_all(tag_name, class_=class_list):
        text = clean_text(el.get_text())     # 取出元素里的文字并清洗
        if text and text not in results:     # 如果不是空文字、且还没收录过
            results.append(text)             # 加入结果
    return results                           # 返回结果


def extract_list_items(soup):
    """提取网页里的"列表内容"。

    会先抓 <li> 标签的文字；
    如果 <li> 太少，再用"重复卡片"的方法兜底。

    参数：
        soup：已经解析好的网页对象。

    返回：
        一个列表，装的是提取到的文字条目。
    """
    items = []                               # 准备装列表条目

    # 方法1：抓取所有 <li> 标签的文字。
    for li in soup.find_all("li"):           # 遍历所有 <li> 标签
        text = clean_text(li.get_text())     # 取出文字并清洗
        if text and text not in items:       # 如果不是空文字、且没重复
            items.append(text)               # 加入结果

    # 方法2：如果 <li> 太少（< 3 个），再用"重复卡片"的方法补充。
    if len(items) < 3:
        cards = _extract_repeated_cards(soup)  # 调用上面的重复卡片提取函数
        for text in cards:                   # 遍历卡片提取到的文字
            if text and text not in items:   # 去重
                items.append(text)           # 加入结果

    return items                             # 返回列表条目


# ---------- 第八部分：提取正文和图片 ----------

def extract_paragraphs(soup, limit=300):
    """提取网页正文里的段落文字（来自 <p> 标签）。

    参数：
        soup：已经解析好的网页对象。
        limit：最多提取多少段（防止网页太长导致文件过大）。

    返回：
        一个列表，装的是每一段文字。
    """
    paragraphs = []                          # 准备装段落

    for p in soup.find_all("p"):             # 遍历所有 <p> 段落标签
        text = clean_text(p.get_text())      # 取出文字并清洗
        if text and text not in paragraphs:  # 去空、去重
            paragraphs.append(text)          # 加入结果
            if len(paragraphs) >= limit:     # 达到上限就停止
                break
    return paragraphs                        # 返回所有段落


def extract_images(soup, base_url, limit=300):
    """提取网页里的图片链接。

    参数：
        soup：已经解析好的网页对象。
        base_url：当前网页的网址（用来把半截图片路径补成完整网址）。
        limit：最多提取多少张图片。

    返回：
        一个列表，装的是图片的完整网址。
    """
    images = []                              # 准备装图片链接

    for img in soup.find_all("img"):         # 遍历所有 <img> 图片标签
        src = img.get("src")                 # 取出图片的 src 地址
        if not src:                          # 如果这个图片没有 src 地址，跳过
            continue
        if src.startswith("data:"):          # 如果地址是 data: 开头（内嵌小图/占位图），跳过
            continue
        # 把半截路径补成完整网址（例如 /images/a.png -> https://网站/images/a.png）。
        full_url = urljoin(base_url, src)
        if full_url not in images:           # 去重
            images.append(full_url)          # 加入结果
            if len(images) >= limit:         # 达到上限就停止
                break
    return images                            # 返回图片链接


# ---------- 第九部分：总入口 ----------

def crawl(url):
    """总入口：抓取并分析一个网页，把结果打包成一个字典返回。

    参数：
        url：要爬取的网址。

    返回：
        一个字典，包含标题、网页类型、描述、表格、列表、正文、图片等所有结果。
    """
    html = fetch_html(url)                        # 1. 抓取网页，拿到 HTML 文字

    # 2. 把 HTML 解析成方便查找的对象。
    #    优先用 lxml 解析器（速度快）；如果没装 lxml，就退回 Python 自带的 html.parser（慢一点但不用额外安装）。
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # 3. 调用上面各个函数，把分析结果打包成一个字典。
    data = {
        "网址": url,                              # 记录网址
        "标题": extract_title(soup),              # 提取标题
        "网页类型": detect_page_type(soup),       # 识别网页类型
        "描述": extract_meta_description(soup),   # 提取描述
        "表格": extract_tables(soup),             # 提取所有表格
        "列表": extract_list_items(soup),         # 提取列表
        "正文": extract_paragraphs(soup),         # 提取正文段落
        "图片": extract_images(soup, url),        # 提取图片链接
    }
    return data                                   # 4. 返回打包好的结果
