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

# time 是 Python 自带的工具，用来在请求之间"歇一下"（礼貌爬取、失败重试）。
import time

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

_SESSION = None                                 # 全局会话，整个程序共用一个（保存 Cookie 等）


def _get_session():
    """获取（或创建）一个全局的 requests 会话。

    用"会话"的好处：
    1. 能自动保存网站给的 Cookie（登录态、翻页时要带的东西等）。
    2. 能统一设置一套"像真人浏览器"的请求头，降低被反爬拦截的概率。
    """
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
    return _SESSION


def fetch_html(url, timeout=15, retries=2, delay=1.0):
    """根据网址，向网站请求网页内容，并返回网页的 HTML 文字。

    做了两件"对抗反爬"的事：
    1. 用一套像真人浏览器的请求头 + 会保存 Cookie 的会话去访问；
    2. 遇到网络抖动 / 服务器 5xx / 429(太频繁) 会自动重试几次，并逐次加长等待。

    参数：
        url：要抓取的网址。
        timeout：最长等待多少秒，超过就报错（默认 15 秒）。
        retries：失败后最多重试几次（默认 2 次）。
        delay：重试前等待的秒数（会随重试次数递增）。

    返回：
        网页的 HTML 文字（字符串，已处理好中文乱码）。
    """
    session = _get_session()                     # 用同一个会话，自动带 Cookie
    last_error = None

    for attempt in range(retries + 1):           # 一共尝试 retries + 1 次
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()          # 非 2xx（成功）都抛 HTTPError
            return _decode_html(response)
        except requests.exceptions.RequestException as error:
            last_error = error
            # 判断这次错误值不值得重试：
            # 网络断连 / 超时 / 服务器 5xx / 429(请求太频繁) → 值得重试
            retryable = isinstance(
                error,
                (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
            )
            resp = getattr(error, "response", None)
            if resp is not None and (resp.status_code >= 500 or resp.status_code == 429):
                retryable = True
            if not retryable:                    # 例如 404 找不到页面，重试也没用，直接抛
                raise
            if attempt < retries:                # 还没用尽重试次数，歇一下再试
                time.sleep(delay * (attempt + 1))  # 越往后等越久，更"礼貌"

    raise last_error                             # 全部失败，抛出最后一次的错误


def _decode_html(response):
    """把网页的原始字节，按正确的编码转成文字（解决中文乱码）。

    思路：拿几个"可能是正确编码"的候选，按可信度逐个尝试，
    谁能正常解码（不报错）就用谁。候选顺序：
    1. requests 根据字节内容"猜"出来的编码（最靠谱）
    2. 网页自己在 <meta charset> 里声明的编码
    3. 服务器在 HTTP 头里声明的编码
    4. 最后兜底用 utf-8

    参数：
        response：requests 拿到的响应对象。

    返回：
        解码好的网页文字（字符串）。
    """
    raw = response.content                      # 网页的原始字节（未解码）

    # 逐个收集候选编码，去重并保持顺序
    candidates = []
    for enc in (response.apparent_encoding, _detect_meta_charset(raw), response.encoding, "utf-8"):
        if enc:                                  # 如果这个候选不是空
            enc = enc.strip().lower()            # 去掉空格、统一小写
            if enc not in candidates:            # 去重
                candidates.append(enc)

    # 依次尝试：谁能正常解码（不报错），就用谁
    for enc in candidates:
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue                             # 这个编码不对，试下一个

    # 全部失败时，用 utf-8 强解（遇到坏字节用 � 代替，保证不崩溃）
    return raw.decode("utf-8", errors="replace")


def _detect_meta_charset(raw):
    """从网页前 8KB 字节里，找出 <meta charset="xxx"> 声明的编码。

    参数：
        raw：网页的原始字节。

    返回：
        声明的编码字符串（如 "utf-8"、"gbk"），找不到返回 None。
    """
    head = raw[:8192].lower()                    # 只看前 8KB，charset 一般都在最前面
    match = re.search(rb'charset\s*=\s*["\']?\s*([a-z0-9_\-]+)', head)
    if match:
        enc = match.group(1).decode("ascii", errors="ignore")
        return enc or None
    return None


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
    """提取网页正文的段落文字。

    优先抓 <p> 标签；如果 <p> 太少（很多现代网站的正文直接写在
    <div>/<section>/<article> 里），就再用"叶子块"的方式兜底，尽量把正文抓全。

    参数：
        soup：已经解析好的网页对象。
        limit：最多提取多少段（防止网页太长导致文件过大）。

    返回：
        一个列表，装的是每一段文字。
    """
    paragraphs = []                          # 准备装段落
    seen = set()                             # 用来去重（比列表查找更快）

    def add(text):
        """去重后加入结果。"""
        if text and text not in seen:
            seen.add(text)
            paragraphs.append(text)

    # 第一步：抓所有 <p> 段落标签
    for p in soup.find_all("p"):
        text = clean_text(p.get_text())      # 取出文字并清洗
        add(text)
        if len(paragraphs) >= limit:         # 达到上限就停止
            return paragraphs

    # 第二步：<p> 太少时，用"叶子块级标签"兜底抓正文。
    if len(paragraphs) < 5:
        for tag in soup.find_all(["article", "main", "section", "div", "blockquote"]):
            # 如果这个块里面还套着别的块级标签，就跳过它——
            # 因为它的文字会由里面的小块分别抓到，整块抓会重复一大坨。
            if tag.find(["article", "main", "section", "div", "blockquote", "p", "li", "table"]):
                continue
            text = clean_text(tag.get_text())
            if len(text) >= 2:               # 过滤掉太短的碎片（如单个按钮文字）
                add(text)
                if len(paragraphs) >= limit:
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


# ---------- 第八点五部分：关键词检索 ----------

def search_keyword(data, keyword):
    """在已经提取好的网页数据里，检索某个关键词出现的所有位置。

    检索范围：标题、描述、正文段落、列表条目、表格单元格（即"全部内容"）。

    参数：
        data：crawler.crawl 返回的结果字典。
        keyword：要检索的关键词。

    返回：
        一个元组 (总次数, 结果列表)。
        结果列表里每项是一个字典：{"区域": 区域名, "片段": 命中片段的文字}。
    """
    low_keyword = keyword.lower()                # 统一转小写，实现"不区分大小写"匹配

    # 把所有要搜索的"区域"收集到一个列表里，每项是 (区域名, 文字)。
    areas = [("标题", data.get("标题", ""))]
    if data.get("描述"):
        areas.append(("描述", data["描述"]))
    for paragraph in data.get("正文", []):
        areas.append(("正文段落", paragraph))
    for item in data.get("列表", []):
        areas.append(("列表条目", item))
    for table in data.get("表格", []):
        for row in table.get("行", []):
            for cell in row:
                areas.append(("表格单元格", cell))

    total = 0                                    # 关键词一共出现了多少次
    results = []                                 # 装每个命中片段

    for area, text in areas:
        if not text:
            continue
        count = text.lower().count(low_keyword)  # 这段文字里出现了几次
        if count <= 0:
            continue
        total += count
        # 把这段文字里每个命中位置截成"带前后文的片段"，加入结果
        for snippet in _find_contexts(text, keyword):
            results.append({"区域": area, "片段": snippet})

    return total, results


def _find_contexts(text, keyword, window=30):
    """在 text 里找出 keyword 的每一个位置，截取前后 window 个字符作为上下文片段。

    关键词会用【】包起来，方便一眼看到命中的地方。

    参数：
        text：要搜索的原始文字。
        keyword：关键词。
        window：片段里关键词前后各保留多少个字符（默认 30）。

    返回：
        一个列表，装的是每个命中位置的片段文字。
    """
    low_text = text.lower()                      # 转小写，配合不区分大小写
    low_keyword = keyword.lower()
    snippets = []                                # 准备装片段
    pos = 0                                      # 从文字开头开始找

    while True:
        idx = low_text.find(low_keyword, pos)    # 找下一个关键词出现的位置
        if idx == -1:                            # 找不到更多了
            break

        # 计算片段在原文里的起止位置（前后各留 window 个字符）
        left = max(0, idx - window)
        right = min(len(text), idx + len(keyword) + window)

        # 取出片段，并算出关键词在片段里的起点位置
        snippet = text[left:right]
        kw_start = idx - left

        # 用【】把关键词包起来，起到"高亮"效果
        highlighted = (
            snippet[:kw_start]
            + "【" + snippet[kw_start:kw_start + len(keyword)] + "】"
            + snippet[kw_start + len(keyword):]
        )

        # 片段两端如果被截断，加个省略号提示
        prefix = "…" if left > 0 else ""
        suffix = "…" if right < len(text) else ""

        snippets.append(prefix + highlighted + suffix)
        pos = idx + len(keyword)                 # 从这个关键词之后继续找

    return snippets


# ---------- 第八点六部分：翻页 ----------

def find_next_page_url(soup, current_url):
    """在网页里找出"下一页"的链接，用于多页爬取。

    优先找 HTML 标准里的 rel="next" 链接；
    找不到就找文字像"下一页 / 下页 / next / > / ›"的链接。

    参数：
        soup：已经解析好的网页对象。
        current_url：当前网页的网址（用来补全半截链接）。

    返回：
        下一页的完整网址；找不到返回 None。
    """
    # 方法1：HTML 标准的分页标记 rel="next"
    next_a = soup.find("a", rel="next")
    if next_a and next_a.get("href"):
        return urljoin(current_url, next_a["href"])

    # 方法2：找文字像"下一页"的链接
    for a in soup.find_all("a"):
        text = clean_text(a.get_text())
        if text and any(k in text for k in ("下一页", "下页", "next", "Next", "›", ">")):
            href = a.get("href")
            if href:
                return urljoin(current_url, href)

    return None


# ---------- 第九部分：总入口 ----------

def crawl(url, keyword=None, pages=1, use_browser=False):
    """总入口：抓取并分析网页（支持翻页和动态渲染），把结果打包成一个字典返回。

    参数：
        url：要爬取的网址。
        keyword：可选，要检索的关键词。传了它，结果里会多一个"关键词检索"字段。
        pages：最多爬几页（>=1）。翻页靠网页里的"下一页"链接，找不到会提前停止。
        use_browser：True 时用浏览器（Selenium）渲染动态内容，拿到 JS 加载后的网页。

    返回：
        一个字典，包含标题、网页类型、描述、表格、列表、正文、图片等所有结果。
    """
    try:
        pages = int(pages)
    except (TypeError, ValueError):
        pages = 1
    pages = max(1, pages)                        # 至少爬 1 页

    page_list = []                               # 每页的分析结果先存这里
    current_url = url
    visited = set()                              # 防止翻页翻出环，重复爬同一页

    for page_index in range(pages):
        if not current_url or current_url in visited:
            break                                # 没有下一页 / 已经在环里，停止
        visited.add(current_url)

        try:
            html = _fetch_page_html(current_url, use_browser)  # 抓这一页
            soup = _parse_soup(html)             # 解析这一页
        except Exception:
            break                                # 某页抓取失败，就不再往下翻

        page_list.append(_extract_page(soup, current_url))

        next_url = find_next_page_url(soup, current_url)  # 找"下一页"
        if next_url is None:
            break                                # 没有下一页了，结束翻页
        if page_index < pages - 1:               # 还要继续翻时才歇一下
            time.sleep(0.8)                      # 礼貌地歇一下再翻页，降低被拦风险
        current_url = next_url

    data = _merge_pages(page_list, url)          # 把多页结果合并成一个字典

    # 如果用户传了关键词，就做关键词检索
    if keyword:
        total, results = search_keyword(data, keyword)
        data["关键词检索"] = {
            "关键词": keyword,
            "总次数": total,
            "结果": results,
        }

    return data


def _fetch_page_html(url, use_browser):
    """获取一页的 HTML：普通请求用 requests；动态渲染用浏览器（Selenium）。"""
    if use_browser:
        import renderer                        # 延迟导入，不用浏览器时不需要装 selenium
        return renderer.render_html(url)
    return fetch_html(url)


def _parse_soup(html):
    """把 HTML 解析成 BeautifulSoup 对象，并删掉脚本/样式等非正文内容。"""
    try:
        soup = BeautifulSoup(html, "lxml")     # 优先用 lxml（快）
    except Exception:
        soup = BeautifulSoup(html, "html.parser")  # 没装 lxml 就退回自带解析器
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()                        # 删掉脚本、样式等无关内容
    return soup


def _extract_page(soup, url):
    """分析单个网页，返回这一页的结果字典。"""
    return {
        "网址": url,
        "标题": extract_title(soup),
        "网页类型": detect_page_type(soup),
        "描述": extract_meta_description(soup),
        "表格": extract_tables(soup),
        "列表": extract_list_items(soup),
        "正文": extract_paragraphs(soup),
        "图片": extract_images(soup, url),
    }


def _merge_pages(page_list, first_url):
    """把多页的结果合并成一个字典（表格重编号，列表/正文/图片去重）。"""
    if not page_list:                            # 一页都没抓到
        return {
            "网址": first_url,
            "标题": "（未找到标题）",
            "网页类型": "普通网页",
            "描述": "",
            "表格": [],
            "列表": [],
            "正文": [],
            "图片": [],
            "爬取页数": 0,
        }

    merged = {
        "网址": first_url,
        "标题": page_list[0]["标题"],
        "网页类型": page_list[0]["网页类型"],
        "描述": page_list[0]["描述"],
        "表格": [],
        "列表": [],
        "正文": [],
        "图片": [],
        "爬取页数": len(page_list),
    }

    seen_list = set()
    seen_paragraphs = set()
    seen_images = set()
    table_index = 0

    for page in page_list:
        for table in page["表格"]:               # 表格：重新编序号
            table_index += 1
            merged["表格"].append({
                "序号": table_index,
                "表头": table["表头"],
                "行": table["行"],
            })
        for item in page["列表"]:                # 列表：去重
            if item not in seen_list:
                seen_list.add(item)
                merged["列表"].append(item)
        for paragraph in page["正文"]:           # 正文：去重
            if paragraph not in seen_paragraphs:
                seen_paragraphs.add(paragraph)
                merged["正文"].append(paragraph)
        for image in page["图片"]:               # 图片：去重
            if image not in seen_images:
                seen_images.add(image)
                merged["图片"].append(image)

    return merged
