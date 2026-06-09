"""
查询微信公众号的 biz（fakeid）工具

使用方法：
    python tools/query_biz.py

需要先设置环境变量：
    set WA_MP__COOKIE=你的微信MP后台cookie
    set WA_MP__TOKEN=你的token

然后输入公众号名称，即可查询对应的 biz。
"""

import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests


def query_biz(name: str, cookie: str, token: str) -> list[dict]:
    """搜索公众号，返回匹配结果"""
    url = "https://mp.weixin.qq.com/cgi-bin/searchbiz"
    params = {
        "action": "search_biz",
        "begin": "0",
        "count": "5",
        "query": name,
        "token": token,
        "lang": "zh_CN",
        "f": "json",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": cookie,
        "Referer": "https://mp.weixin.qq.com/",
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        data = resp.json()

        if "list" not in data:
            ret = data.get("base_resp", {}).get("ret", "unknown")
            print(f"  查询失败，ret={ret}，可能 Cookie 已过期")
            return []

        results = []
        for item in data["list"]:
            results.append({
                "name": item.get("nickname", ""),
                "biz": item.get("fakeid", ""),
                "signature": item.get("signature", ""),
                "round_head_img": item.get("round_head_img", ""),
            })
        return results

    except Exception as e:
        print(f"  查询出错: {e}")
        return []


def main():
    # 从环境变量读取 Cookie 和 Token
    cookie = os.environ.get("WA_MP__COOKIE", "")
    token = os.environ.get("WA_MP__TOKEN", "")

    if not cookie or not token:
        print("请先设置环境变量：")
        print("  set WA_MP__COOKIE=你的cookie")
        print("  set WA_MP__TOKEN=你的token")
        sys.exit(1)

    print("微信公众号 biz 查询工具")
    print("输入公众号名称查询，输入 q 退出\n")

    while True:
        name = input("请输入公众号名称: ").strip()
        if name.lower() == "q":
            print("退出")
            break
        if not name:
            continue

        print(f"正在查询 \"{name}\"...")
        results = query_biz(name, cookie, token)

        if not results:
            print("  未找到匹配的公众号\n")
            continue

        print(f"\n  找到 {len(results)} 个结果：\n")
        for i, r in enumerate(results, 1):
            print(f"  {i}. 名称: {r['name']}")
            print(f"     biz:  {r['biz']}")
            print(f"     简介: {r['signature'][:50]}")
            print()

        # 提示配置格式
        if results:
            print("  复制以下内容到 config.yaml 的 subscriptions 中：\n")
            for r in results:
                print(f'  - name: "{r["name"]}"')
                print(f'    rss_path: "/wechat/mp/{r["biz"]}"')
            print()


if __name__ == "__main__":
    main()
