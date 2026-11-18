# -*- coding: utf-8 -*-
"""
main.py —— 程序入口
================================
这个文件负责和用户"对话"：
提示输入网址 → 调用爬虫 → 打印分析结果 → 调用导出模块生成 Excel。

小白读法：
这是整个程序的"大门"。你运行这个文件，整个爬虫就启动了。
运行时它会问你"要爬哪个网址"，你输入网址回车，它就会自动干活。
"""

# ---------- 第一部分：导入我们自己写的模块 ----------

# 导入爬虫模块（负责抓取和分析网页，就是 crawler.py 这个文件）。
import crawler

# 导入导出模块（负责生成 Excel，就是 exporter.py 这个文件）。
import exporter


# ---------- 第二部分：处理输入的网址 ----------

def normalize_url(raw):
    """把用户输入的网址"整理"成规范形式。

    如果用户只输了 www.baidu.com 这种（没写 http/https 开头），
    就自动补上 https://。

    参数：
        raw：用户输入的原始网址文字。

    返回：
        整理好的网址；如果输入是空的，返回 None。
    """
    url = raw.strip()                        # 去掉首尾的空格
    if not url:                              # 如果去空格后是空的
        return None                          # 返回 None（表示"没有有效网址"）

    # 如果网址不是以 http:// 或 https:// 开头，就自动在前面补上 https://。
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url                               # 返回整理好的网址


# ---------- 第三部分：打印结果 ----------

def print_summary(data):
    """把爬取到的结果，用整齐的文字打印到屏幕上给用户看。

    参数：
        data：爬虫返回的结果字典。
    """
    print("✅ 爬取完成！分析结果如下：")
    print("=" * 50)
    print(f"  网页标题：{data['标题']}")
    print(f"  网页类型：{data['网页类型']}")
    print(f"  找到表格：{len(data['表格'])} 个")
    print(f"  找到列表：{len(data['列表'])} 条")
    print(f"  找到正文段落：{len(data['正文'])} 段")
    print(f"  找到图片：{len(data['图片'])} 张")
    if data["描述"]:                         # 如果描述不是空的
        print(f"  网页描述：{data['描述'][:100]}")  # 只显示前 100 个字符，防止刷屏
    print("=" * 50)


# ---------- 第四部分：主程序 ----------

def main():
    """主函数：整个程序的起点。"""
    print("=" * 50)
    print("  欢迎使用「小白爬虫」工具 🕷️")
    print("  输入网址即可自动抓取，并生成 Excel 表格")
    print("=" * 50)

    while True:                              # 用一个循环，让用户可以连续爬多个网址
        # 提示用户输入网址（直接按回车 = 退出程序）。
        raw_url = input("\n请输入要爬取的网址（直接回车退出）：").strip()

        if not raw_url:                      # 如果用户直接回车（输入为空）
            print("已退出，再见！👋")
            break                            # 跳出循环，结束程序

        url = normalize_url(raw_url)         # 整理用户输入的网址
        keyword = input("请输入要检索的关键词（直接回车跳过检索）：").strip() or None
        print(f"\n正在爬取：{url} ...")       # 提示用户正在爬取
        if keyword:                          # 如果填了关键词
            print(f"检索关键词：{keyword}")

        try:
            data = crawler.crawl(url, keyword)  # 调用爬虫，抓取并分析网页（可带关键词）
        except Exception as e:               # 如果爬取过程中出错（如网址打错、断网）
            print(f"❌ 爬取失败：{e}")        # 打印错误信息
            print("提示：请检查网址是否正确、网络是否畅通。")
            continue                         # 跳过本次，回到循环开头让用户重新输入

        print_summary(data)                  # 打印分析结果

        # 如果做了关键词检索，把结果打印出来
        if keyword:
            search = data.get("关键词检索", {})
            total = search.get("总次数", 0)
            results = search.get("结果", [])
            if total > 0:
                print(f"\n🔍 关键词「{keyword}」共出现 {total} 次：")
                for item in results[:20]:
                    print(f"   · [{item['区域']}] {item['片段']}")
                if len(results) > 20:
                    print(f"   … 其余 {len(results) - 20} 处请在 Excel 的「关键词检索」工作表查看")
            else:
                print(f"\n🔍 未找到关键词「{keyword}」")

        # 生成 Excel 文件的保存路径。
        output_path = exporter.make_output_path(url)
        # 把数据写成 Excel 文件。
        exporter.export_to_excel(data, output_path)
        # 告诉用户文件保存到了哪里。
        print(f"📊 已生成 Excel 表格：{output_path}")


# 这是 Python 的固定写法：只有"直接运行这个文件"时，才会执行下面的 main()。
# （如果这个文件被别的文件 import 导入，就不会自动执行，避免误运行。）
if __name__ == "__main__":
    main()
