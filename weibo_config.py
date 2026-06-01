import os
import traceback
from configparser import ConfigParser

from weibo_logger import get_logger

log = get_logger()
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.properties")


def _ensure_file():
    if not os.path.exists(CONFIG_FILE):
        log.debug(f"创建配置文件: {CONFIG_FILE}")
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write("")


def get(key: str) -> str:
    _ensure_file()
    config = ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")
    if config.has_option("DEFAULT", key):
        return config.get("DEFAULT", key)
    log.debug(f"[Config] 键 '{key}' 不存在")
    return ""


def set(key: str, value: str):
    _ensure_file()
    config = ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")
    config.set("DEFAULT", key, value)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        config.write(f)
    log.debug(f"[Config] 设置 {key} = {value[:30] if len(value) > 30 else value}")
