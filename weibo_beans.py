from dataclasses import dataclass, field
from typing import List, Optional, Any


def _safe_init(cls, data: dict):
    """Instantiate a dataclass from dict, ignoring extra keys."""
    fields = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in fields}
    return cls(**filtered)


@dataclass
class QRInfo:
    qr_code: str = ""
    qr_url: str = ""


@dataclass
class WeiBoQRImgBean:
    retcode: int = 0
    data: Optional["WeiBoQRImgData"] = None

    @staticmethod
    def from_json(obj: dict) -> "WeiBoQRImgBean":
        d = obj.get("data")
        return WeiBoQRImgBean(
            retcode=obj.get("retcode", 0),
            data=_safe_init(WeiBoQRImgData, d) if d else None,
        )


@dataclass
class WeiBoQRImgData:
    qrid: str = ""
    image: str = ""


@dataclass
class WeiBoVerifyBean:
    retcode: int = 0
    msg: str = ""
    data: Optional["WeiBoVerifyData"] = None

    @staticmethod
    def from_json(obj: dict) -> "WeiBoVerifyBean":
        d = obj.get("data")
        return WeiBoVerifyBean(
            retcode=obj.get("retcode", 0),
            msg=obj.get("msg", ""),
            data=_safe_init(WeiBoVerifyData, d) if d else None,
        )


@dataclass
class WeiBoVerifyData:
    alt: str = ""


@dataclass
class LoginBean:
    retcode: str = ""
    uid: str = ""
    nick: str = ""
    crossDomainUrlList: List[str] = field(default_factory=list)


@dataclass
class UserBean:
    result: bool = False
    userInfo: Optional["UserInfo"] = None

    @staticmethod
    def from_json(obj: dict) -> "UserBean":
        u = obj.get("userInfo") or obj.get("userinfo")
        return UserBean(
            result=obj.get("result", False),
            userInfo=_safe_init(UserInfo, u) if u else None,
        )


@dataclass
class UserInfo:
    displayname: str = ""
    uniqueid: str = ""


@dataclass
class CHListBean:
    data: Optional["CHListData"] = None

    @staticmethod
    def from_json(obj: dict) -> "CHListBean":
        d = obj.get("data")
        if not d:
            return CHListBean()
        lst = d.get("list", [])
        return CHListBean(
            data=CHListData(
                max_page=d.get("max_page", 0),
                list=[_safe_init(ChList, item) for item in lst],
            )
        )


@dataclass
class CHListData:
    max_page: int = 0
    list: List["ChList"] = field(default_factory=list)


@dataclass
class ChList:
    oid: str = ""
    title: str = ""


@dataclass
class CheckinOkBean:
    code: str = ""
    msg: str = ""
    data: Optional["CheckinData"] = None

    @staticmethod
    def from_json(obj: dict) -> "CheckinOkBean":
        d = obj.get("data")
        return CheckinOkBean(
            code=str(obj.get("code", "")),
            msg=obj.get("msg", ""),
            data=_safe_init(CheckinData, d) if d else None,
        )


@dataclass
class CheckinData:
    alert_title: str = ""
    alert_subtitle: str = ""
    alert_activity: str = ""


@dataclass
class CheckinBean:
    code: int = 0
    msg: str = ""
