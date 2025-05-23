from typing import TypedDict, Optional

class EndpointConfig(TypedDict):
    uuid: str
    redirect: bool
    alias: Optional[str]
    actions: bool
    cors: bool
    expiry: Optional[str]  # or Optional[datetime] if parsed
    timeout: int
    listen: int
    premium: bool
    user_id: Optional[str]
    password: bool
    ip: str
    user_agent: str
    default_content: str
    default_status: int
    default_content_type: str
    request_limit: Optional[int]
    description: Optional[str]
    created_at: str  # can be datetime
    updated_at: str  # can be datetime
