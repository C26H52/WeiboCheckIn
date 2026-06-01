"""
GitHub Actions 签到脚本
1. 从 USERS_JSON secret 还原用户及其 Cookie
2. 随机延迟 0~4 小时
3. 执行批量签到
4. (可选) 通过 GitHub API 更新 USERS_JSON Secret
"""
import os
import sys
import json
import base64
import random
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
os.chdir(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

from weibo_logger import get_logger
log = get_logger()

log.info("=" * 50)
log.info("GitHub Actions 签到启动")

# ── 1. 还原用户数据 ──────────────────────────

users_json_str = os.environ.get("USERS_JSON", "")
if not users_json_str:
    log.error("未设置 USERS_JSON secret")
    sys.exit(1)

users_data = json.loads(users_json_str)
users = users_data["users"]
log.info(f"还原 {len(users)} 个用户")

with open("users.json", "w", encoding="utf-8") as f:
    json.dump(users, f, ensure_ascii=False, indent=2)

for user in users:
    uid = user["uid"]
    cookie_b64 = users_data.get("cookies", {}).get(uid, "")
    if not cookie_b64:
        log.error(f"用户 {user['username']} 缺少Cookie数据")
        continue
    try:
        decoded = base64.b64decode(cookie_b64)
        cf = user.get("cookie_file", f"cookies_{uid}.pkl")
        user["cookie_file"] = cf
        with open(cf, "wb") as f:
            f.write(decoded)
        log.info(f"还原 {cf} ({len(decoded)} bytes)")
    except Exception as e:
        log.error(f"解码 {uid} Cookie 失败: {e}")

# ── 2. 随机延迟 ──────────────────────────────

delay = random.randint(0, 14400)
log.info(f"随机延迟 {delay}秒 (约 {delay//60} 分钟)")
time.sleep(delay)

# ── 3. 执行签到 ──────────────────────────────

from weibo_chaohua import set_cookie_file, start_checkin

all_results = []
for user in users:
    uid = user["uid"]
    username = user["username"]
    cookie_file = user.get("cookie_file", "")
    if not os.path.exists(cookie_file):
        log.error(f"Cookie文件缺失: {cookie_file}, 跳过 {username}")
        continue

    log.info(f"=== {username} (UID={uid}) ===")
    set_cookie_file(cookie_file)
    result = start_checkin()
    all_results.append({"username": username, "uid": uid, "result": result})
    log.info(f"结果: 总数={result['total']} 成功={result['success']} "
             f"失败={result['error']} 已签={result['yiqian']}")

# ── 4. 汇总 ──────────────────────────────────

log.info("=" * 40)
log.info("签到汇总:")
for r in all_results:
    rr = r["result"]
    log.info(f"  {r['username']}: 成功{rr['success']} 失败{rr['error']} 已签{rr['yiqian']}")

# ── 5. 更新 Secrets ──────────────────────────

pat = os.environ.get("PAT_TOKEN", "")
if pat:
    log.info("检测到 PAT_TOKEN, 更新 USERS_JSON Secret...")
    try:
        import requests as req

        repo = os.environ.get("GITHUB_REPOSITORY", "")
        api_url = f"https://api.github.com/repos/{repo}"
        headers = {
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
        }

        pk_resp = req.get(f"{api_url}/actions/secrets/public-key", headers=headers, timeout=10)
        if pk_resp.status_code != 200:
            log.error(f"获取 public key 失败: {pk_resp.status_code}")
        else:
            pk = pk_resp.json()
            key_id = pk["key_id"]
            public_key = pk["key"]

            cookies_data = {}
            for user in users:
                cf = user.get("cookie_file", "")
                if cf and os.path.exists(cf):
                    with open(cf, "rb") as f:
                        cookies_data[user["uid"]] = base64.b64encode(f.read()).decode()

            import subprocess
            subprocess.run([sys.executable, "-m", "pip", "install", "pynacl"], capture_output=True)
            from nacl import encoding, public

            def encrypt_secret(key: str, val: str) -> str:
                pkey = public.PublicKey(key.encode(), encoding.Base64Encoder())
                sealed = public.SealedBox(pkey)
                return base64.b64encode(sealed.encrypt(val.encode())).decode()

            new_data = {"users": users, "cookies": cookies_data}
            new_json = json.dumps(new_data, ensure_ascii=False)
            encrypted = encrypt_secret(public_key, new_json)

            resp = req.put(
                f"{api_url}/actions/secrets/USERS_JSON",
                headers=headers,
                json={"encrypted_value": encrypted, "key_id": key_id},
                timeout=10,
            )
            log.info(f"更新 USERS_JSON: {resp.status_code}")

    except Exception as e:
        log.error(f"更新 Secret 失败: {e}")
else:
    log.info("未设置 PAT_TOKEN, 跳过更新Cookie")

log.info("GitHub Actions 签到完成")
