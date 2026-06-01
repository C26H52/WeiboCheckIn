"""
本地运行: 导出当前用户数据为 GitHub Secrets 格式。
只需一个 Secret: USERS_JSON
"""
import os
import sys
import json
import base64

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
os.chdir(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

print("=" * 60)
print("GitHub Secrets 导出工具")
print("=" * 60)
print()
print("请复制下面的值到仓库 Settings >")
print("Secrets and variables > Actions > New repository secret")
print()

users_file = "users.json"
if not os.path.exists(users_file):
    print("⚠ users.json 不存在，请先在 Web 界面扫码添加账号")
    sys.exit(1)

with open(users_file, "r", encoding="utf-8") as f:
    users = json.load(f)

cookies_data = {}
for u in users:
    cf = u.get("cookie_file", "")
    uid = u["uid"]
    if cf and os.path.exists(cf):
        with open(cf, "rb") as f:
            cookies_data[uid] = base64.b64encode(f.read()).decode()
        print(f"✅ {u['username']} (UID={uid}): {cf} -> {len(cookies_data[uid])}字符 base64")

users_json_data = {"users": users, "cookies": cookies_data}
final_json = json.dumps(users_json_data, ensure_ascii=False)
print()
print(f"📦 打包完成: {len(final_json)} 字符")
print()

print("┌" + "─" * 58 + "┐")
print("│ Secret Name:  USERS_JSON" + " " * 30 + "│")
print("├" + "─" * 58 + "┤")
for line in final_json[:500].split("\n"):
    print("│ " + line[:56].ljust(56) + " │")
if len(final_json) > 500:
    print("│ ... (截断, 请复制完整输出)                           │")
print("└" + "─" * 58 + "┘")
print()
print("⚠ 请复制上面框内的完整 JSON，粘贴到 Secret 的 Value")
print()
if len(final_json) > 48000:
    print("⚠⚠⚠ 数据超过 48KB！GitHub Secrets 限制 48KB。请减少账号。")
else:
    print(f"✅ 大小 {len(final_json)} / 48000 字节，可以安全存储")
print()
print("=" * 60)
print("可选 Secrets:")
print("  SERVERCHAN_SENDKEY: Server酱 SendKey")
print("    注册: https://sct.ftqq.com  → 拿到 SendKey")
print("    作用: 签到完成后推送结果到微信")
print("  PAT_TOKEN: GitHub Personal Access Token")
print("  权限: repo + workflow")
print("  作用: 自动更新 Cookie")
print("=" * 60)
