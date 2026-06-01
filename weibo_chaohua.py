import json
import time
import traceback
from typing import Optional

import requests

from weibo_beans import (
    CHListBean,
    ChList,
    CheckinOkBean,
    CheckinBean,
    _safe_init,
)
from weibo_cookie import load_cookies, save_cookies
from weibo_logger import get_logger

log = get_logger()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)
REFERER_WEIBO = "https://weibo.com/"

_cookie_file = None


def set_cookie_file(path: str):
    global _cookie_file
    _cookie_file = path


def _create_session() -> requests.Session:
    s = requests.Session()
    s.max_redirects = 0
    load_cookies(s, _cookie_file)
    return s


def get_chaohua_list(page: int) -> Optional[CHListBean]:
    url = f"https://weibo.com/ajax/profile/topicContent?tabid=231093_-_chaohua&page={page}"
    log.info(f"[超话列表] 请求第{page}页")
    log.debug(f"[超话列表] URL: {url}")
    s = _create_session()
    try:
        resp = s.get(url, headers={"user-agent": USER_AGENT, "referer": REFERER_WEIBO}, timeout=30)
        log.debug(f"[超话列表] 状态码: {resp.status_code}")
        body = resp.text
        log.debug(f"[超话列表] 响应体(前300): {body[:300]}")
        save_cookies(s, _cookie_file)
        data = json.loads(body)
        bean = CHListBean.from_json(data)
        item_count = len(bean.data.list) if bean.data else 0
        log.info(f"[超话列表] 第{page}页获取成功, 共{item_count}个超话")
        return bean
    except Exception as e:
        log.error(f"[超话列表] 第{page}页异常: {e}\n{traceback.format_exc()}")
        save_cookies(s, _cookie_file)
        return None


def checkin_chaohua(oid: str) -> Optional[CheckinOkBean]:
    checkin_url = (
        f"https://weibo.com/p/aj/general/button"
        f"?ajwvr=6&api=http://i.huati.weibo.com/aj/super/checkin"
        f"&status=0&location=page_100808_super_index&id={oid}"
    )
    referer = f"https://weibo.com/p/{oid}/super_index"
    log.debug(f"[签到] oid={oid}")
    s = _create_session()
    try:
        resp = s.get(
            checkin_url,
            headers={
                "user-agent": USER_AGENT,
                "referer": referer,
                "x-requested-with": "XMLHttpRequest",
            },
            timeout=30,
        )
        body = resp.text
        log.debug(f"[签到] oid={oid} 状态码={resp.status_code} body(前200)={body[:200]}")
        save_cookies(s, _cookie_file)

        try:
            raw = json.loads(body)
            checkin_bean = _safe_init(CheckinBean, raw)
        except Exception as e:
            log.error(f"[签到] JSON解析失败 oid={oid}: {e}")
            return None

        if checkin_bean.code == 100000:
            try:
                ok_data = json.loads(body)
                return CheckinOkBean.from_json(ok_data)
            except Exception as e:
                log.error(f"[签到] CheckinOkBean解析失败 oid={oid}: {e}")
                result = CheckinOkBean()
                result.code = str(checkin_bean.code)
                result.msg = checkin_bean.msg
                return result
        else:
            log.debug(f"[签到] oid={oid} code={checkin_bean.code} msg={checkin_bean.msg}")
            result = CheckinOkBean()
            result.code = str(checkin_bean.code)
            result.msg = checkin_bean.msg
            return result
    except Exception as e:
        log.error(f"[签到] 请求异常 oid={oid}: {e}\n{traceback.format_exc()}")
        save_cookies(s, _cookie_file)
        return None


def start_checkin() -> dict:
    """执行签到，返回统计结果dict"""
    log.info("========== 开始签到 ==========")
    total = success = error = yiqian = 0
    details = []

    page = 1
    while True:
        ch = get_chaohua_list(page)
        if not ch or not ch.data:
            log.error(f"获取第{page}页超话列表失败")
            break

        max_page = ch.data.max_page
        for item in ch.data.list:
            oid = item.oid.split(":")[-1]
            result = checkin_chaohua(oid)
            total += 1
            status = "error"
            msg = "签到失败!"

            if result is None:
                error += 1
            elif result.code == "100000":
                success += 1
                status = "success"
                if result.data:
                    parts = [result.data.alert_title, result.data.alert_subtitle, result.data.alert_activity]
                    msg = ", ".join(p for p in parts if p) or "签到成功"
                else:
                    msg = "签到成功"
            elif result.code == "382004":
                yiqian += 1
                status = "yiqian"
                msg = "今日已签"
            else:
                error += 1
                msg = result.msg

            details.append({"title": item.title, "status": status, "msg": msg})

            try:
                time.sleep(1.5)
            except KeyboardInterrupt:
                return {"total": total, "success": success, "error": error, "yiqian": yiqian, "details": details}

        if page >= max_page:
            break
        page += 1

    log.info(f"签到结束: 总数={total} 成功={success} 失败={error} 已签={yiqian}")
    return {"total": total, "success": success, "error": error, "yiqian": yiqian, "details": details}
