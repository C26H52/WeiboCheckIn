"""
Playwright Cookie 保活脚本

使用真实 Chromium 浏览器维持微博登录态。
每 3-5 天运行一次即可保持 Cookie 有效。
"""
import os
import sys
import json
import time
import pickle
import re
import traceback
from http.cookiejar import Cookie
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

from weibo_logger import get_logger

log = get_logger()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE_DIR, "browser_profile")
os.makedirs(PROFILE_DIR, exist_ok=True)


def export_browser_cookies(context, uid: str, username: str) -> str:
    browser_cookies = context.cookies()
    log.info(f"从浏览器获取 {len(browser_cookies)} 个 Cookie")

    cookies_dict = {}
    for c in browser_cookies:
        domain = c.get("domain", "")
        path = c.get("path", "/")
        cookies_dict.setdefault(domain, {}).setdefault(path, {})
        cookie = Cookie(
            version=0,
            name=c.get("name", ""),
            value=c.get("value", ""),
            port=None,
            port_specified=False,
            domain=domain,
            domain_specified=bool(domain),
            domain_initial_dot=domain.startswith("."),
            path=path,
            path_specified=True,
            secure=c.get("secure", False),
            expires=c.get("expires", -1) if c.get("expires", -1) > 0 else None,
            discard=False,
            comment=None,
            comment_url=None,
            rest={"httponly": c.get("httpOnly", False)},
            rfc2109=False,
        )
        cookies_dict[domain][path][c.get("name")] = cookie

    filename = f"cookies_{uid}.pkl"
    with open(filename, "wb") as f:
        pickle.dump(cookies_dict, f)

    log.info(f"导出到 {filename} ({len(browser_cookies)} 个 Cookie)")
    return filename


def update_users_file(uid: str, username: str, cookie_file: str):
    users_file = os.path.join(BASE_DIR, "users.json")
    users = []
    if os.path.exists(users_file):
        try:
            with open(users_file, "r", encoding="utf-8") as f:
                users = json.load(f)
        except Exception:
            pass

    for u in users:
        if u.get("uid") == uid:
            u["username"] = username
            u["cookie_file"] = cookie_file
            break
    else:
        users.append({"uid": uid, "username": username, "cookie_file": cookie_file})

    with open(users_file, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    log.info(f"更新 users.json: {username} (UID={uid})")


def is_logged_in(page) -> bool:
    cookies = page.context.cookies()
    for c in cookies:
        if c.get("name") == "SSOLoginState" and c.get("domain", "").endswith("weibo.com"):
            try:
                expires = int(c.get("expires", 0))
                if expires > time.time():
                    log.info(f"Cookie 有效, {expires - time.time():.0f} 秒后过期")
                    return True
            except Exception:
                pass
    return False


def get_user_info(page) -> tuple[str, str]:
    """从已登录页面提取 uid 和 username。"""
    uid = ""
    username = ""

    try:
        # 尝试从页面 JS 配置中提取
        config = page.evaluate("""() => {
            var scripts = document.querySelectorAll('script');
            for (var i=0;i<scripts.length;i++) {
                var m = scripts[i].textContent.match(/"user_id":\s*"?(\d+)"?/);
                if (m) return m[1];
            }
            var m = document.documentElement.innerHTML.match(/"user_id":\s*"?(\d+)"?/);
            return m ? m[1] : '';
        }""")
        if config:
            uid = str(config)
    except Exception:
        pass

    # 从 page URL 提取 uid
    if not uid:
        try:
            url = page.url
            m = re.search(r"/u/(\d+)", url)
            if m:
                uid = m.group(1)
        except Exception:
            pass

    if not uid:
        uid = "unknown"

    log.info(f"用户: uid={uid}")
    return uid, username or f"weibo_user_{uid}"


def check_and_refresh():
    log.info("=" * 50)
    log.info("Playwright Cookie 保活启动")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        page = browser.pages[0] if browser.pages else browser.new_page()

        # 访问微博首页, 检测登录状态
        log.info("访问微博首页...")
        page.goto("https://weibo.com/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        if is_logged_in(page):
            log.info("检测到已登录, 导出 Cookie...")
            uid, username = get_user_info(page)
            filename = export_browser_cookies(page.context, uid, username)
            update_users_file(uid, username, filename)
        else:
            log.info("未登录, 打开扫码页面...")
            page.goto("https://weibo.com/login.php", wait_until="domcontentloaded", timeout=30000)
            print("\n" + "=" * 50)
            print("请在打开的浏览器窗口中用微博 App 扫码登录")
            print("=" * 50 + "\n")

            try:
                page.wait_for_url(
                    lambda url: "login" not in url
                    and "passport" not in url
                    and "weibo.com" in url,
                    timeout=300000,
                )
                log.info("扫码完成, 提取信息...")
                page.wait_for_timeout(3000)

                uid, username = get_user_info(page)
                filename = export_browser_cookies(page.context, uid, username)
                update_users_file(uid, username, filename)
                print(f"\n导出完成: {username} (UID={uid})")

            except PwTimeout:
                log.error("扫码超时 (5 分钟)")

        browser.close()
        log.info("保活脚本结束")


if __name__ == "__main__":
    check_and_refresh()
