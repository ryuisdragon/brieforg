"""
DEPRECATED: 相容殼，所有模組請改用 `from services.session import manager`
"""

# deprecated shim - re-export 單例，避免雙實作
from services.session import manager as session_manager  # noqa: F401


def get_session(session_id):
    return session_manager.get_session(session_id)


def create_session(session_type: str, **kwargs):
    # 僅維持最小相容；建議改用新接口
    if session_type == "chat":
        return session_manager.create_chat_session(**kwargs).dict()
    elif session_type == "audience_coach":
        return session_manager.create_audience_coach_session(**kwargs).dict()
    return None


def update_session(session_id: str, **updates) -> bool:
    return session_manager.update_session(session_id, **updates)


def delete_session(session_id: str) -> bool:
    return session_manager.delete_session(session_id)


def list_sessions(session_type=None):
    return session_manager.list_sessions(session_type)
