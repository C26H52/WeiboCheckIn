import sys


def main():
    if len(sys.argv) < 2:
        print("请输入参数 login 或 checkin")
        print("login: 登录")
        print("checkin: 签到（Web版推荐使用 python web_server.py）")
        return

    command = sys.argv[1]
    if command == "login":
        from weibo_login import verify_and_login
        verify_and_login()
    elif command == "checkin":
        from weibo_chaohua import start_checkin
        result = start_checkin()
        print(f"\n总数={result['total']} 成功={result['success']} 失败={result['error']} 已签={result['yiqian']}")
    else:
        print("请输入参数 login 或 checkin")


if __name__ == "__main__":
    main()
