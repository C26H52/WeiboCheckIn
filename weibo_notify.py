"""
Server酱 微信通知模块
注册地址: https://sct.ftqq.com
"""
import os
import traceback

import requests

from weibo_logger import get_logger

log = get_logger()

SERVERCHAN_URL = "https://sctapi.ftqq.com/{sendkey}.send"


def send_notification(title: str, content: str, sendkey: str = ""):
    """发送微信通知。sendkey 为空时从环境变量或配置文件读取。"""
    if not sendkey:
        sendkey = os.environ.get("SERVERCHAN_SENDKEY", "")
    if not sendkey:
        from weibo_config import get as conf_get
        sendkey = conf_get("SERVERCHAN_SENDKEY")

    if not sendkey:
        log.warning("[Notify] 未配置 SERVERCHAN_SENDKEY，跳过推送")
        return

    try:
        resp = requests.post(
            SERVERCHAN_URL.format(sendkey=sendkey),
            data={"title": title, "desp": content},
            timeout=15,
        )
        log.info(f"[Notify] 推送结果: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        log.error(f"[Notify] 推送失败: {e}\n{traceback.format_exc()}")
