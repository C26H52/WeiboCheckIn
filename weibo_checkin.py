import sys


def main():
    if len(sys.argv) < 2:
        print("请输入参数 login 或 checkin")
        print("login: 登录")
        print("checkin: 签到（推荐使用 python web_server.py）")
        return

    command = sys.argv[1]
    if command == "login":
        from weibo_login import do_login
        import weibo_login as wl
        import weibo_users as wu
        success, uid, username = do_login()
        if success and uid:
            cookie_file = f"cookies_{uid}.pkl"
            wu.add_user(uid, username, cookie_file)
            print(f"已保存用户: {username}")
    elif command == "checkin":
        from weibo_users import list_users
        from weibo_chaohua import set_cookie_file, start_checkin

        users = list_users()
        if not users:
            print("没有已登录用户，请先运行 login 或使用 Web 界面扫码")
            return

        for user in users:
            uid = user["uid"]
            username = user["username"]
            cookie_file = user["cookie_file"]
            print(f"\n=== {username} (UID={uid}) ===")
            set_cookie_file(cookie_file)
            result = start_checkin()
            print(f"总数={result['total']} 成功={result['success']} 失败={result['error']} 已签={result['yiqian']}")
    else:
        print("请输入参数 login 或 checkin")


if __name__ == "__main__":
    main()
