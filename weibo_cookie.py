import os
import pickle
import traceback
from http.cookiejar import Cookie
from typing import Optional

import requests

from weibo_logger import get_logger

log = get_logger()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_COOKIE_FILE = os.path.join(BASE_DIR, "cookies.pkl")


def _get_cookie_path(filepath: Optional[str] = None) -> str:
    if filepath:
        if not os.path.isabs(filepath):
            filepath = os.path.join(BASE_DIR, filepath)
        return filepath
    return DEFAULT_COOKIE_FILE


def save_cookies(session: requests.Session, filepath: Optional[str] = None):
    path = _get_cookie_path(filepath)
    jar = session.cookies
    cookies_dict = {}
    for domain, path_cookies in jar._cookies.items():
        cookies_dict[domain] = {}
        for p, cookies in path_cookies.items():
            cookies_dict[domain][p] = {
                name: {
                    "value": c.value,
                    "expires": c.expires,
                    "path": c.path,
                    "domain": c.domain,
                    "secure": c.secure,
                    "httponly": c._rest.get("httponly", False),
                    "version": c.version,
                    "port": c.port,
                    "port_specified": c.port_specified,
                    "domain_specified": c.domain_specified,
                    "domain_initial_dot": c.domain_initial_dot,
                    "path_specified": c.path_specified,
                    "comment": c.comment,
                    "comment_url": c.comment_url,
                    "discard": c.discard,
                    "rfc2109": c.rfc2109,
                }
                for name, c in cookies.items()
            }
    with open(path, "wb") as f:
        pickle.dump(cookies_dict, f)
    total = sum(len(cs) for pcs in cookies_dict.values() for cs in pcs.values())
    log.info(f"[Cookie] 保存 {total} 个Cookie到 {os.path.basename(path)}")


def load_cookies(session: requests.Session, filepath: Optional[str] = None):
    path = _get_cookie_path(filepath)
    if not os.path.exists(path):
        log.info(f"[Cookie] 文件 {os.path.basename(path)} 不存在")
        return
    try:
        with open(path, "rb") as f:
            cookies_dict = pickle.load(f)
        count = 0
        for domain, path_cookies in cookies_dict.items():
            for p, cookies in path_cookies.items():
                for name, data in cookies.items():
                    c = Cookie(
                        version=data.get("version", 0),
                        name=name,
                        value=data["value"],
                        port=data.get("port"),
                        port_specified=data.get("port_specified", False),
                        domain=data["domain"],
                        domain_specified=data.get("domain_specified", False),
                        domain_initial_dot=data.get("domain_initial_dot", False),
                        path=data["path"],
                        path_specified=data.get("path_specified", False),
                        secure=data.get("secure", False),
                        expires=data.get("expires"),
                        discard=data.get("discard", False),
                        comment=data.get("comment"),
                        comment_url=data.get("comment_url"),
                        rest={"httponly": data.get("httponly", False)},
                        rfc2109=data.get("rfc2109", False),
                    )
                    session.cookies.set_cookie(c)
                    count += 1
        log.info(f"[Cookie] 从 {os.path.basename(path)} 加载 {count} 个Cookie")
    except Exception as e:
        log.error(f"[Cookie] 加载异常: {e}\n{traceback.format_exc()}")


def cookie_file_exists(filepath: Optional[str] = None) -> bool:
    return os.path.exists(_get_cookie_path(filepath))
