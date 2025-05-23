from typing import TypedDict, Optional, List, Dict, Any
from .request_headers import RequestHeaders

class WebhookRequest(TypedDict):
    uuid: str
    type: str
    token_id: str
    team_id: Optional[str]
    ip: str
    hostname: str
    method: str
    user_agent: str
    content: str
    query: Dict[str, str]
    headers: RequestHeaders
    url: str
    size: int
    files: List[Any]
    created_at: str
    updated_at: str
    sorting: int
    custom_action_output: List[Any]
    custom_action_errors: List[Any]
    time: float