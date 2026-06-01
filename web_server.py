import json
import os
import random
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Optional

from flask import Flask, Response, jsonify, render_template_string, request

import weibo_login
import weibo_chaohua
from weibo_beans import UserBean
from weibo_users import list_users, add_user, remove_user, get_user_count
from weibo_logger import get_logger

log = get_logger()

app = Flask(__name__)

_qr_state = {"qr_id": None, "qr_url": None, "status": "idle"}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>微博超话签到</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f0f2f5; color: #333; min-height: 100vh; }
.header { background: linear-gradient(135deg, #e6162d, #ff6900); color: #fff;
          padding: 20px; text-align: center; font-size: 22px; font-weight: bold;
          box-shadow: 0 2px 8px rgba(0,0,0,.15); }
.container { max-width: 800px; margin: 24px auto; padding: 0 16px; }
.card { background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.card-title { font-size: 16px; font-weight: 600; margin-bottom: 16px;
              padding-bottom: 8px; border-bottom: 1px solid #f0f0f0; display: flex;
              justify-content: space-between; align-items: center; }
.btn { display: inline-block; padding: 10px 24px; border: none; border-radius: 8px;
       font-size: 15px; cursor: pointer; transition: all .2s; margin-right: 8px;
       font-weight: 500; }
.btn-primary { background: #e6162d; color: #fff; }
.btn-primary:hover { background: #c41225; }
.btn-primary:disabled { background: #f5a0ac; cursor: not-allowed; }
.btn-secondary { background: #f0f0f0; color: #333; }
.btn-secondary:hover { background: #e0e0e0; }
.btn-danger { background: #fff; color: #ff4d4f; border: 1px solid #ff4d4f; }
.btn-danger:hover { background: #fff1f0; }
.qr-box { text-align: center; padding: 16px; }
.qr-box img { width: 180px; height: 180px; border: 1px solid #eee; border-radius: 8px; }
.qr-text { margin-top: 12px; color: #888; font-size: 13px; }
.user-list { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
.user-tag { background: #f6f8fa; border-radius: 8px; padding: 10px 16px; display: flex;
            align-items: center; gap: 10px; font-size: 14px; }
.user-tag .name { font-weight: 600; }
.user-tag .uid { color: #999; font-size: 12px; }
.user-tag .del { cursor: pointer; color: #ff4d4f; font-weight: bold; padding: 0 4px; }
.user-tag .del:hover { color: #c41225; }
.empty { text-align: center; color: #bbb; padding: 20px 0; font-size: 14px; }
.result-list { max-height: 420px; overflow-y: auto; }
.result-item { display: flex; justify-content: space-between; align-items: center;
               padding: 10px 0; border-bottom: 1px solid #f5f5f5; font-size: 14px; }
.result-item:last-child { border-bottom: none; }
.result-item .user-label { color: #e6162d; font-weight: 600; min-width: 40px; padding-left: 8px; }
.result-title { flex: 1; padding-left: 8px; }
.result-status { font-weight: 500; min-width: 70px; text-align: right; padding-left: 12px; }
.status-success { color: #52c41a; }
.status-error { color: #ff4d4f; }
.status-yiqian { color: #faad14; }
.summary { display: flex; gap: 24px; flex-wrap: wrap; margin-top: 12px; padding-top: 12px;
           border-top: 1px solid #f0f0f0; }
.summary-item { text-align: center; }
.summary-num { font-size: 28px; font-weight: 700; }
.summary-label { font-size: 12px; color: #888; margin-top: 4px; }
</style>
</head>
<body>
<div class="header">微博超话签到</div>
<div class="container">

  <div class="card">
    <div class="card-title">
      <span>已登录用户 (<span id="userCount">{{ user_count }}</span>)</span>
      <span>
        <button class="btn btn-primary" onclick="startLogin()" id="btnLogin">添加账号</button>
        <button class="btn btn-primary" onclick="batchCheckin()" id="btnBatchCheckin"
                {{ 'disabled' if user_count == 0 else '' }}>一键签到</button>
      </span>
    </div>
    <div class="user-list" id="userList">
      {% for u in users %}
      <div class="user-tag">
        <span class="name">{{ u.username }}</span>
        <span class="uid">{{ u.uid }}</span>
        <span class="del" onclick="delUser('{{ u.uid }}')" title="删除">x</span>
      </div>
      {% endfor %}
      {% if users|length == 0 %}
      <div class="empty">暂无账号，请先扫码添加</div>
      {% endif %}
    </div>
  </div>

  <div class="card">
    <div class="card-title">
      <span>定时签到</span>
      <span id="schedulerStatus" style="color:#888;font-size:13px">检测中...</span>
    </div>
    <div style="color:#888;font-size:13px;margin-bottom:12px;">
      每天 00:00 触发，在当天随机时间自动为所有账号签到
    </div>
    <button class="btn btn-primary" id="btnSchedulerOn" onclick="toggleScheduler(true)">启用</button>
    <button class="btn btn-secondary" id="btnSchedulerOff" onclick="toggleScheduler(false)" style="display:none">关闭</button>
  </div>

  <div class="card" id="qrCard" style="display:none">
    <div class="card-title">扫码登录</div>
    <div class="qr-box">
      <img id="qrImg" src="" alt="二维码加载中...">
      <div class="qr-text" id="qrHint">请使用微博 App 扫描二维码</div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">签到结果</div>
    <div class="result-list" id="resultList">
      <div class="empty" id="emptyHint">点击"一键签到"开始</div>
    </div>
    <div class="summary" id="summary" style="display:none">
      <div class="summary-item">
        <div class="summary-num" id="sUser">0</div>
        <div class="summary-label">用户数</div>
      </div>
      <div class="summary-item">
        <div class="summary-num" id="sTotal">0</div>
        <div class="summary-label">超话数</div>
      </div>
      <div class="summary-item">
        <div class="summary-num status-success" id="sSuccess">0</div>
        <div class="summary-label">成功</div>
      </div>
      <div class="summary-item">
        <div class="summary-num status-yiqian" id="sYiqian">0</div>
        <div class="summary-label">已签</div>
      </div>
      <div class="summary-item">
        <div class="summary-num status-error" id="sError">0</div>
        <div class="summary-label">失败</div>
      </div>
    </div>
  </div>

</div>

<script>
let qrTimer = null;

function startLogin() {
  document.getElementById('qrCard').style.display = 'block';
  document.getElementById('qrHint').innerText = '正在获取二维码...';
  document.getElementById('qrImg').src = '';
  document.getElementById('btnLogin').disabled = true;

  fetch('/api/login/qr')
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        document.getElementById('qrImg').src = data.qr_url;
        document.getElementById('qrHint').innerText = '请使用微博 App 扫描二维码';
        qrTimer = setInterval(pollVerify, 3000);
      } else {
        document.getElementById('qrHint').innerText = '获取二维码失败';
        document.getElementById('btnLogin').disabled = false;
      }
    })
    .catch(e => {
      document.getElementById('qrHint').innerText = '网络错误';
      document.getElementById('btnLogin').disabled = false;
    });
}

function pollVerify() {
  fetch('/api/login/verify')
    .then(r => r.json())
    .then(data => {
      if (data.retcode === 20000000) {
        clearInterval(qrTimer);
        document.getElementById('qrHint').innerText = '扫码成功，正在登录...';
        completeLogin(data);
      } else if (data.retcode === 50114001) {
        document.getElementById('qrHint').innerText = '等待扫码...';
      } else if (data.retcode === -1) {
        document.getElementById('qrHint').innerText = '等待中...';
      } else {
        document.getElementById('qrHint').innerText = data.msg || '未知状态';
      }
    });
}

function completeLogin(verifyData) {
  fetch('/api/login/complete', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({alt: verifyData.alt || ''})
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      document.getElementById('qrHint').innerText = '登录成功: ' + data.username;
      setTimeout(() => { location.reload(); }, 1000);
    } else {
      document.getElementById('qrHint').innerText = '登录失败: ' + data.msg;
      document.getElementById('btnLogin').disabled = false;
    }
  });
}

function delUser(uid) {
  if (!confirm('确定删除该账号？')) return;
  fetch('/api/user/remove', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({uid: uid})
  }).then(() => location.reload());
}

function batchCheckin() {
  document.getElementById('btnBatchCheckin').disabled = true;
  document.getElementById('emptyHint').style.display = 'none';
  document.getElementById('resultList').innerHTML = '';
  document.getElementById('summary').style.display = 'none';

  let userCount = 0, total = 0, success = 0, error = 0, yiqian = 0;

  const evtSource = new EventSource('/api/checkin/batch');
  evtSource.onmessage = function(e) {
    const data = JSON.parse(e.data);
    if (data.type === 'user_start') {
      userCount++;
      const div = document.createElement('div');
      div.className = 'result-item';
      div.innerHTML = '<span class="user-label">' + data.username + '</span>'
        + '<span style="color:#888">开始签到...</span>';
      div.id = 'user-' + data.uid;
      document.getElementById('resultList').appendChild(div);
    } else if (data.type === 'progress') {
      total++;
      if (data.status === 'success') success++;
      else if (data.status === 'yiqian') yiqian++;
      else error++;

      const div = document.createElement('div');
      div.className = 'result-item';
      div.innerHTML = '<span style="padding-left:48px" class="result-title">'
        + data.title + '</span>'
        + '<span class="result-status status-' + data.status + '">' + data.msg + '</span>';
      document.getElementById('resultList').appendChild(div);
      document.getElementById('resultList').scrollTop = document.getElementById('resultList').scrollHeight;
    } else if (data.type === 'user_done') {
      const el = document.getElementById('user-' + data.uid);
      if (el) el.innerHTML = '<span class="user-label">' + data.username + '</span>'
        + '<span style="color:#52c41a">完成 (成功:' + data.success + ' 失败:' + data.error + ' 已签:' + data.yiqian + ')</span>';
    } else if (data.type === 'done') {
      evtSource.close();
      document.getElementById('btnBatchCheckin').disabled = false;
    }

    document.getElementById('sUser').innerText = userCount;
    document.getElementById('sTotal').innerText = total;
    document.getElementById('sSuccess').innerText = success;
    document.getElementById('sYiqian').innerText = yiqian;
    document.getElementById('sError').innerText = error;
    document.getElementById('summary').style.display = 'flex';
  };
  evtSource.onerror = function() {
    evtSource.close();
    document.getElementById('btnBatchCheckin').disabled = false;
  };
}
</script>
<script>
function toggleScheduler(enable) {
  var url = enable ? '/api/scheduler/enable' : '/api/scheduler/disable';
  var msg = enable ? '启用' : '关闭';
  fetch(url, {method:'POST'})
    .then(r => r.json())
    .then(d => {
      alert(msg + (d.success ? '成功' : '失败: ' + d.msg));
      checkScheduler();
    });
}
function checkScheduler() {
  fetch('/api/scheduler/status')
    .then(r => r.json())
    .then(d => {
      document.getElementById('schedulerStatus').innerText = d.enabled ? '已启用' : '未启用';
      document.getElementById('btnSchedulerOn').style.display = d.enabled ? 'none' : 'inline-block';
      document.getElementById('btnSchedulerOff').style.display = d.enabled ? 'inline-block' : 'none';
    });
}
checkScheduler();
</script>
</html>"""


@app.route("/")
def index():
    users = list_users()
    return render_template_string(HTML_TEMPLATE, users=users, user_count=len(users))


# ---- 登录 API ----

@app.route("/api/login/qr")
def api_login_qr():
    qr_info = weibo_login.get_qr_info()
    if not qr_info:
        return jsonify({"success": False, "msg": "获取二维码失败"})
    _qr_state["qr_id"] = qr_info.qr_code
    _qr_state["qr_url"] = qr_info.qr_url
    _qr_state["status"] = "waiting"
    return jsonify({"success": True, "qr_url": qr_info.qr_url})


@app.route("/api/login/verify")
def api_login_verify():
    qr_id = _qr_state.get("qr_id")
    if not qr_id:
        return jsonify({"retcode": -1, "msg": "二维码未生成"})
    verify = weibo_login.get_verify_info(qr_id)
    if verify.retcode == 20000000:
        _qr_state["alt"] = verify.data.alt if verify.data else ""
        _qr_state["status"] = "confirmed"
    return jsonify({"retcode": verify.retcode, "msg": verify.msg, "alt": _qr_state.get("alt", "")})


@app.route("/api/login/complete", methods=["POST"])
def api_login_complete():
    data = request.get_json()
    alt = data.get("alt", "")
    log.info(f"[Web] 开始完成登录, alt={alt}")

    urls, uid, nick = weibo_login._sina_sso_login(alt)
    if not urls:
        return jsonify({"success": False, "msg": "SSO登录失败"})

    # 创建一个临时 cookie 文件用于登录
    tmp_cookie = f"cookies_{uid}.pkl"
    weibo_login.set_cookie_file(tmp_cookie)

    success, uid2, username = weibo_login._open_new_weibo(urls)
    if success:
        add_user(uid2, username, tmp_cookie)
        log.info(f"[Web] 登录成功-已保存: {username} cookie={tmp_cookie}")
        return jsonify({"success": True, "username": username, "uid": uid2})

    return jsonify({"success": False, "msg": "Passport登录失败"})


# ---- 用户管理 ----

@app.route("/api/user/remove", methods=["POST"])
def api_user_remove():
    data = request.get_json()
    uid = data.get("uid", "")
    users = list_users()
    for u in users:
        if u["uid"] == uid:
            cf = u.get("cookie_file", "")
            if cf and os.path.exists(os.path.join(os.path.dirname(__file__), cf)):
                os.remove(os.path.join(os.path.dirname(__file__), cf))
            break
    remove_user(uid)
    return jsonify({"success": True})


# ---- 批量签到 ----

@app.route("/api/checkin/batch")
def api_checkin_batch():
    def generate():
        users = list_users()
        log.info(f"[Web] 开始批量签到, {len(users)} 个用户")
        for user in users:
            uid = user["uid"]
            username = user["username"]
            cookie_file = user["cookie_file"]
            log.info(f"[Web] 签到用户: {username} cookie={cookie_file}")

            yield f"data: {json.dumps({'type': 'user_start', 'uid': uid, 'username': username})}\n\n"

            weibo_chaohua.set_cookie_file(cookie_file)
            result = weibo_chaohua.start_checkin()

            for item in result["details"]:
                yield f"data: {json.dumps({'type': 'progress', 'title': item['title'], 'status': item['status'], 'msg': item['msg']})}\n\n"

            yield f"data: {json.dumps({'type': 'user_done', 'uid': uid, 'username': username, 'success': result['success'], 'error': result['error'], 'yiqian': result['yiqian']})}\n\n"

        log.info("[Web] 批量签到完成")
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


# ---- 定时任务管理 ----

SCHEDULED_TASK_NAME = "WeiboAutoCheckin"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = sys.executable


def _run_schtasks(args: list) -> dict:
    """执行 schtasks 命令，返回 {success, output}"""
    try:
        result = subprocess.run(
            ["schtasks"] + args,
            capture_output=True, text=True, timeout=15,
        )
        output = result.stdout or result.stderr
        log.debug(f"[Scheduler] schtasks {' '.join(args)}: {output[:200]}")
        return {"success": result.returncode == 0, "output": output}
    except Exception as e:
        log.error(f"[Scheduler] 命令异常: {e}")
        return {"success": False, "output": str(e)}


@app.route("/api/scheduler/status")
def api_scheduler_status():
    res = _run_schtasks(["/query", "/tn", SCHEDULED_TASK_NAME, "/fo", "csv", "/nh"])
    enabled = res["success"] and "WeiboAutoCheckin" in res["output"]
    return jsonify({"enabled": enabled})


@app.route("/api/scheduler/enable", methods=["POST"])
def api_scheduler_enable():
    auto_script = os.path.join(SCRIPT_DIR, "auto_checkin.py")

    # 先删后建
    _run_schtasks(["/delete", "/tn", SCHEDULED_TASK_NAME, "/f"])

    res = _run_schtasks([
        "/create", "/tn", SCHEDULED_TASK_NAME,
        "/tr", f'"{PYTHON_EXE}" "{auto_script}"',
        "/sc", "daily", "/st", "00:00",
        "/f",
    ])
    if res["success"]:
        log.info("[Scheduler] 定时任务已创建: 每天00:00触发")
        return jsonify({"success": True, "msg": "定时任务已启用"})
    else:
        log.error(f"[Scheduler] 创建失败: {res['output']}")
        return jsonify({"success": False, "msg": res["output"]})


@app.route("/api/scheduler/disable", methods=["POST"])
def api_scheduler_disable():
    res = _run_schtasks(["/delete", "/tn", SCHEDULED_TASK_NAME, "/f"])
    if res["success"]:
        log.info("[Scheduler] 定时任务已删除")
        return jsonify({"success": True, "msg": "定时任务已关闭"})
    else:
        return jsonify({"success": False, "msg": res["output"]})


def main():
    log.info("========== 启动 Web 服务 ==========")
    users = list_users()
    log.info(f"已加载 {len(users)} 个用户")
    for u in users:
        log.info(f"  - {u['username']} (UID={u['uid']}) cookie={u['cookie_file']}")

    print("启动服务: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()
