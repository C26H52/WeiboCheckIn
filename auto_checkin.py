"""
每日定时签到脚本 — 由 Windows 任务计划程序在 00:00 触发。
触发后随机等待 0~24 小时，再执行批量签到。
"""
import os
import sys
import random
import time
from datetime import datetime, timedelta

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from weibo_logger import get_logger
log = get_logger()

log.info("=" * 50)
log.info("定时签到触发")
now = datetime.now()

delay_seconds = random.randint(0, 86400)
exec_time = now + timedelta(seconds=delay_seconds)
log.info(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
log.info(f"随机延迟: {delay_seconds}秒 ({delay_seconds // 3600}小时{delay_seconds % 3600 // 60}分钟)")
log.info(f"预计签到: {exec_time.strftime('%Y-%m-%d %H:%M:%S')}")

time.sleep(delay_seconds)

from weibo_users import list_users
from weibo_chaohua import set_cookie_file, start_checkin

users = list_users()
log.info(f"开始批量签到, 共{len(users)}个用户")

if not users:
    log.warning("没有已登录用户，跳过")
    sys.exit(0)

all_results = []

for user in users:
    uid = user["uid"]
    username = user["username"]
    cookie_file = user["cookie_file"]
    log.info(f"--- 签到: {username} (UID={uid}) ---")
    set_cookie_file(cookie_file)
    result = start_checkin()
    log.info(f"结果: 总数={result['total']} 成功={result['success']} 失败={result['error']} 已签={result['yiqian']}")
    all_results.append((username, result))

lines = ["| 用户 | 成功 | 失败 | 已签 |", "|------|------|------|------|"]
for username, rr in all_results:
    lines.append(f"| {username} | {rr['success']} | {rr['error']} | {rr['yiqian']} |")

from weibo_notify import send_notification
send_notification(
    title=f"微博签到完成 ({len(all_results)}人)",
    content="\n".join(lines),
)

log.info("定时签到完成")
