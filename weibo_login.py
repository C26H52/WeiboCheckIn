import json
import time
import traceback
from typing import List, Optional, Tuple

import requests

from weibo_beans import (
    QRInfo,
    WeiBoQRImgBean,
    WeiBoVerifyBean,
    LoginBean,
    UserBean,
    _safe_init,
)
from weibo_utils import weibo_to_json
from weibo_cookie import load_cookies, save_cookies
from weibo_logger import get_logger

log = get_logger()

USER_AGENT_QR = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
)
USER_AGENT_CHECKIN = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)

REFERER_WEIBO = "https://weibo.com"

_cookie_file = None


def set_cookie_file(path: str):
    global _cookie_file
    _cookie_file = path


def _create_no_redirect_session(load_cookiejar: bool = True) -> requests.Session:
    s = requests.Session()
    s.max_redirects = 0
    if load_cookiejar:
        load_cookies(s, _cookie_file)
    return s


def _create_follow_session(load_cookiejar: bool = True) -> requests.Session:
    s = requests.Session()
    if load_cookiejar:
        load_cookies(s, _cookie_file)
    return s


def _get_qr_login_info() -> Optional[str]:
    ts = int(time.time() * 1000)
    url = f"https://login.sina.com.cn/sso/qrcode/image?entry=sinawap&size=180&callback=STK_{ts}1"
    s = _create_no_redirect_session(load_cookiejar=False)
    try:
        log.debug(f"[QR] 请求获取二维码: {url}")
        resp = s.get(url, headers={"referer": REFERER_WEIBO, "user-agent": USER_AGENT_QR}, timeout=30)
        log.debug(f"[QR] 响应状态码: {resp.status_code}")
        log.debug(f"[QR] 响应体(前500): {resp.text[:500]}")
        return weibo_to_json(resp.text)
    except Exception as e:
        log.error(f"[QR] 获取二维码异常: {e}\n{traceback.format_exc()}")
        return None


def get_qr_info() -> Optional[QRInfo]:
    json_str = _get_qr_login_info()
    if not json_str:
        log.error("[QR] JSONP解析为空")
        return None
    try:
        data = json.loads(json_str)
        log.debug(f"[QR] 解析结果: retcode={data.get('retcode')}")
        bean = WeiBoQRImgBean.from_json(data)
    except Exception as e:
        log.error(f"[QR] 解析JSON异常: {e}\n{traceback.format_exc()}")
        return None
    if bean.retcode != 20000000 or not bean.data:
        log.error(f"[QR] retcode异常: {bean.retcode}, data存在: {bean.data is not None}")
        return None
    info = QRInfo()
    info.qr_code = bean.data.qrid
    info.qr_url = bean.data.image
    log.info(f"[QR] 获取成功: qrid={info.qr_code}, image={info.qr_url[:60]}...")
    return info


def _verify_qr(qr_id: str) -> Optional[str]:
    ts = int(time.time() * 1000)
    url = f"https://login.sina.com.cn/sso/qrcode/check?entry=sinawap&qrid={qr_id}&callback=STK_{ts}2"
    s = _create_no_redirect_session(load_cookiejar=False)
    try:
        log.debug(f"[Verify] 请求验证: qrid={qr_id}")
        resp = s.get(url, headers={"referer": REFERER_WEIBO, "user-agent": USER_AGENT_QR}, timeout=30)
        log.debug(f"[Verify] 响应状态码: {resp.status_code}")
        log.debug(f"[Verify] 响应体(前300): {resp.text[:300]}")
        if resp.status_code != 200:
            log.error(f"[Verify] 状态码不是200: {resp.status_code}")
            return None
        return weibo_to_json(resp.text)
    except Exception as e:
        log.error(f"[Verify] 异常: {e}\n{traceback.format_exc()}")
        return None


def get_verify_info(qr_id: str) -> WeiBoVerifyBean:
    json_str = _verify_qr(qr_id)
    if not json_str:
        log.warning("[Verify] 返回空")
        return WeiBoVerifyBean(retcode=-1, msg="网络错误")
    try:
        data = json.loads(json_str)
        bean = WeiBoVerifyBean.from_json(data)
        log.debug(f"[Verify] 解析结果: retcode={bean.retcode}, msg={bean.msg}")
        return bean
    except Exception as e:
        log.error(f"[Verify] 解析异常: {e}\n{traceback.format_exc()}")
        return WeiBoVerifyBean(retcode=-1, msg="解析失败")


def _sina_sso_login(alt: str) -> Tuple[List[str], Optional[str], Optional[str]]:
    ts = int(time.time() * 1000)
    url = (
        f"https://login.sina.com.cn/sso/login.php"
        f"?entry=sinawap&returntype=TEXT&crossdomain=1&cdult=3"
        f"&domain=weibo.cn&alt={alt}&savestate=30&callback=STK_{ts}3"
    )
    log.info(f"[SSO] 开始SSO登录: alt={alt}")
    log.debug(f"[SSO] 请求URL: {url}")
    s = _create_follow_session()
    try:
        resp = s.get(url, headers={"referer": REFERER_WEIBO, "user-agent": USER_AGENT_QR}, timeout=30)
        log.debug(f"[SSO] 响应状态码: {resp.status_code}")
        log.debug(f"[SSO] 响应头: {dict(resp.headers)}")
        log.debug(f"[SSO] 响应体(前500): {resp.text[:500]}")
        log.debug(f"[SSO] 最终URL(重定向后): {resp.url}")
        body = resp.text
        save_cookies(s, _cookie_file)
        json_str = weibo_to_json(body)
        log.debug(f"[SSO] JSONP转JSON结果(前500): {json_str[:500]}")
        data = json.loads(json_str)
        log.debug(f"[SSO] 解析JSON: keys={list(data.keys())}")
        bean = _safe_init(LoginBean, data)
        log.info(f"[SSO] 成功获取跨域URL {len(bean.crossDomainUrlList)} 条, uid={bean.uid}, nick={bean.nick}")
        return bean.crossDomainUrlList, bean.uid, bean.nick
    except Exception as e:
        log.error(f"[SSO] SSO登录异常: {e}\n{traceback.format_exc()}")
        save_cookies(s, _cookie_file)
        return [], None, None


def _open_new_weibo(urls: List[str]) -> Tuple[bool, str, str]:
    for i, url in enumerate(urls):
        if not url.startswith("https://passport.weibo.com"):
            log.debug(f"[Passport] 跳过非passport URL[{i}]: {url[:80]}...")
            continue
        log.info(f"[Passport] 正在请求passport[{i}]: {url[:100]}...")
        s = _create_follow_session()
        try:
            resp = s.get(url, headers={"user-agent": USER_AGENT_QR}, timeout=30)
            html = resp.text
            log.debug(f"[Passport] 状态码={resp.status_code}, 最终URL={resp.url}")
            log.debug(f"[Passport] 响应体(前300): {html[:300]}")
            save_cookies(s, _cookie_file)
            json_str = html[1 : len(html) - 3]
            log.debug(f"[Passport] 截取JSON(前300): {json_str[:300]}")
            data = json.loads(json_str)
            user = UserBean.from_json(data)
            log.info(f"[Passport] 解析User: result={user.result}, name={user.userInfo.displayname if user.userInfo else 'None'}")
            if user.result and user.userInfo:
                log.info(f"[Passport] 登录成功: {user.userInfo.displayname} (UID={user.userInfo.uniqueid})")
                return True, user.userInfo.uniqueid, user.userInfo.displayname
        except Exception as e:
            log.error(f"[Passport] Passport[{i}]异常: {e}\n{traceback.format_exc()}")
            save_cookies(s, _cookie_file)
            continue
    log.warning("[Passport] 所有passport URL均未登录成功")
    return False, "", ""


def do_login() -> Tuple[bool, str, str]:
    """执行完整登录流程。返回 (成功, uid, username)"""
    qr_info = get_qr_info()
    if not qr_info:
        log.error("二维码获取失败")
        print("二维码获取失败")
        return False, "", ""

    print("二维码已生成，请用微博App扫码登录")
    print(f"二维码地址: {qr_info.qr_url}")
    log.info(f"等待扫码... qrid={qr_info.qr_code}")
    print("等待扫码确认...")

    while True:
        verify = get_verify_info(qr_info.qr_code)
        if verify.retcode == 20000000:
            print("扫码确认成功，正在登录...")
            log.info(f"[Login] 扫码确认, alt={verify.data.alt if verify.data else ''}")
            alt = verify.data.alt if verify.data else ""
            urls, uid, nick = _sina_sso_login(alt)
            if not urls:
                log.error("[Login] SSO登录返回空URL列表")
                print("SSO登录失败")
                return False, "", ""
            success, uid2, username = _open_new_weibo(urls)
            if success:
                print(f"登录成功: {username} (UID={uid2})")
                return True, uid2, username
            print("Passport登录失败")
            return False, "", ""
        elif verify.retcode == 50114001:
            log.debug("[Login] 等待扫码中...")
            print("还未扫码，继续等待...")
        else:
            log.warning(f"[Login] QR验证返回: retcode={verify.retcode}, msg={verify.msg}")
            print(verify.msg)

        try:
            time.sleep(3)
        except KeyboardInterrupt:
            log.info("用户取消")
            print("\n已取消")
            return False, "", ""


def verify_and_login() -> bool:
    """CLI简化版，保持兼容"""
    success, uid, username = do_login()
    return success
