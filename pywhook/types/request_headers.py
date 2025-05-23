from typing import TypedDict, List

class RequestHeaders(TypedDict):
    accept_language: List[str]
    accept_encoding: List[str]
    sec_fetch_dest: List[str]
    sec_fetch_user: List[str]
    sec_fetch_mode: List[str]
    sec_fetch_site: List[str]
    accept: List[str]
    user_agent: List[str]
    upgrade_insecure_requests: List[str]
    sec_ch_ua_platform: List[str]
    sec_ch_ua_mobile: List[str]
    sec_ch_ua: List[str]
    host: List[str]
