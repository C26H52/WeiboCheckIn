import json
import os
from typing import List, Dict

from weibo_logger import get_logger

log = get_logger()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")


def _load_users() -> List[Dict]:
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_users(users: List[Dict]):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    log.debug(f"[Users] 保存 {len(users)} 个用户")


def list_users() -> List[Dict]:
    return _load_users()


def add_user(uid: str, username: str, cookie_file: str):
    users = _load_users()
    for u in users:
        if u["uid"] == uid:
            u["username"] = username
            u["cookie_file"] = cookie_file
            _save_users(users)
            log.info(f"[Users] 更新用户: {username} (UID={uid})")
            return
    users.append({"uid": uid, "username": username, "cookie_file": cookie_file})
    _save_users(users)
    log.info(f"[Users] 新增用户: {username} (UID={uid})")


def remove_user(uid: str):
    users = _load_users()
    users = [u for u in users if u["uid"] != uid]
    _save_users(users)


def get_user_count() -> int:
    return len(_load_users())
