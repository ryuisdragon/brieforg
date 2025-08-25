#!/usr/bin/env python3
"""
統一的會話管理器
整合企劃專案和受眾分析的會話管理
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from models.unified_models import SessionData, ProjectData, ChatMessage, MessageRole

logger = logging.getLogger(__name__)


class UnifiedSessionManager:
    """統一的會話管理器"""

    def __init__(self, sessions_dir: str = "sessions"):
        """初始化會話管理器"""
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(exist_ok=True)
        self.active_sessions: Dict[str, SessionData] = {}

    def create_session(self, user_id: Optional[str] = None) -> SessionData:
        """創建新會話"""
        try:
            session_id = str(uuid.uuid4())

            session_data = SessionData(
                session_id=session_id,
                user_id=user_id,
                project_data=ProjectData(),
                chat_history=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status="active",
            )

            # 保存到記憶體
            self.active_sessions[session_id] = session_data

            # 保存到檔案
            self._save_session_to_file(session_data)

            logger.info(f"創建新會話: {session_id}")
            return session_data

        except Exception as e:
            logger.error(f"創建會話失敗: {e}")
            raise

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """獲取會話"""
        try:
            # 先從記憶體中查找
            if session_id in self.active_sessions:
                return self.active_sessions[session_id]

            # 從檔案中載入
            session_data = self._load_session_from_file(session_id)
            if session_data:
                self.active_sessions[session_id] = session_data
                return session_data

            return None

        except Exception as e:
            logger.error(f"獲取會話失敗: {e}")
            return None

    def update_session(
        self,
        session_id: str,
        project_data: Optional[ProjectData] = None,
        chat_message: Optional[ChatMessage] = None,
    ) -> bool:
        """更新會話"""
        try:
            session_data = self.get_session(session_id)
            if not session_data:
                logger.warning(f"會話不存在: {session_id}")
                return False

            # 更新專案數據
            if project_data:
                session_data.project_data = project_data

            # 添加聊天訊息
            if chat_message:
                session_data.chat_history.append(chat_message)

            # 更新時間戳
            session_data.updated_at = datetime.now()

            # 保存到記憶體
            self.active_sessions[session_id] = session_data

            # 保存到檔案
            self._save_session_to_file(session_data)

            logger.info(f"更新會話: {session_id}")
            return True

        except Exception as e:
            logger.error(f"更新會話失敗: {e}")
            return False

    def add_chat_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """添加聊天訊息"""
        try:
            chat_message = ChatMessage(
                role=role,
                content=content,
                message_type=message_type,
                timestamp=datetime.now(),
                metadata=metadata,
            )

            return self.update_session(session_id, chat_message=chat_message)

        except Exception as e:
            logger.error(f"添加聊天訊息失敗: {e}")
            return False

    def get_chat_history(self, session_id: str) -> List[ChatMessage]:
        """獲取聊天歷史"""
        try:
            session_data = self.get_session(session_id)
            if session_data:
                return session_data.chat_history
            return []

        except Exception as e:
            logger.error(f"獲取聊天歷史失敗: {e}")
            return []

    def get_project_data(self, session_id: str) -> Optional[ProjectData]:
        """獲取專案數據"""
        try:
            session_data = self.get_session(session_id)
            if session_data:
                return session_data.project_data
            return None

        except Exception as e:
            logger.error(f"獲取專案數據失敗: {e}")
            return None

    def update_project_data(self, session_id: str, project_data: ProjectData) -> bool:
        """更新專案數據"""
        try:
            return self.update_session(session_id, project_data=project_data)

        except Exception as e:
            logger.error(f"更新專案數據失敗: {e}")
            return False

    def list_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出會話"""
        try:
            sessions = []

            # 掃描會話目錄
            for session_file in self.sessions_dir.glob("*.json"):
                try:
                    session_data = self._load_session_from_file(session_file.stem)
                    if session_data:
                        # 如果指定了用戶ID，只返回該用戶的會話
                        if user_id is None or session_data.user_id == user_id:
                            sessions.append(
                                {
                                    "session_id": session_data.session_id,
                                    "user_id": session_data.user_id,
                                    "created_at": session_data.created_at.isoformat(),
                                    "updated_at": session_data.updated_at.isoformat(),
                                    "status": session_data.status,
                                    "project_summary": self._get_project_summary(
                                        session_data.project_data
                                    ),
                                    "message_count": len(session_data.chat_history),
                                }
                            )
                except Exception as e:
                    logger.warning(f"載入會話檔案失敗: {session_file}, 錯誤: {e}")
                    continue

            # 按更新時間排序
            sessions.sort(key=lambda x: x["updated_at"], reverse=True)

            return sessions

        except Exception as e:
            logger.error(f"列出會話失敗: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """刪除會話"""
        try:
            # 從記憶體中移除
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]

            # 刪除檔案
            session_file = self.sessions_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()

            logger.info(f"刪除會話: {session_id}")
            return True

        except Exception as e:
            logger.error(f"刪除會話失敗: {e}")
            return False

    def close_session(self, session_id: str) -> bool:
        """關閉會話"""
        try:
            session_data = self.get_session(session_id)
            if session_data:
                session_data.status = "closed"
                return self.update_session(session_id)
            return False

        except Exception as e:
            logger.error(f"關閉會話失敗: {e}")
            return False

    def _save_session_to_file(self, session_data: SessionData) -> bool:
        """保存會話到檔案"""
        try:
            session_file = self.sessions_dir / f"{session_data.session_id}.json"

            # 轉換為可序列化的格式
            session_dict = session_data.dict()
            session_dict["created_at"] = session_data.created_at.isoformat()
            session_dict["updated_at"] = session_data.updated_at.isoformat()

            # 處理聊天歷史的時間戳
            for msg in session_dict["chat_history"]:
                msg["timestamp"] = msg["timestamp"].isoformat()

            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session_dict, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            logger.error(f"保存會話到檔案失敗: {e}")
            return False

    def _load_session_from_file(self, session_id: str) -> Optional[SessionData]:
        """從檔案載入會話"""
        try:
            session_file = self.sessions_dir / f"{session_id}.json"

            if not session_file.exists():
                return None

            with open(session_file, "r", encoding="utf-8") as f:
                session_dict = json.load(f)

            # 轉換時間戳
            session_dict["created_at"] = datetime.fromisoformat(
                session_dict["created_at"]
            )
            session_dict["updated_at"] = datetime.fromisoformat(
                session_dict["updated_at"]
            )

            # 處理聊天歷史的時間戳
            for msg in session_dict["chat_history"]:
                msg["timestamp"] = datetime.fromisoformat(msg["timestamp"])

            return SessionData(**session_dict)

        except Exception as e:
            logger.error(f"從檔案載入會話失敗: {e}")
            return None

    def _get_project_summary(self, project_data: ProjectData) -> str:
        """獲取專案摘要"""
        try:
            summary = []

            if project_data.project_attributes.industry:
                summary.append(f"產業: {project_data.project_attributes.industry}")
            if project_data.project_attributes.campaign:
                summary.append(f"主題: {project_data.project_attributes.campaign}")
            if project_data.time_budget.budget:
                summary.append(f"預算: {project_data.time_budget.budget}")

            return " | ".join(summary) if summary else "專案尚未開始"

        except Exception as e:
            logger.error(f"獲取專案摘要失敗: {e}")
            return "專案資訊不完整"

    def cleanup_old_sessions(self, days: int = 7) -> int:
        """清理舊會話，依據 updated_at 與 days 參數判斷。

        - days <= 0: 不清理，直接返回 0
        - 其餘：刪除 updated_at 早於 (現在 - days) 的會話檔案
        """
        try:
            from datetime import timezone, timedelta

            if days <= 0:
                return 0

            cleanup_count = 0
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            for session_file in self.sessions_dir.glob("*.json"):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    updated_str = data.get("updated_at") or data.get("created_at")
                    if updated_str:
                        try:
                            updated_dt = datetime.fromisoformat(updated_str)
                        except Exception:
                            updated_dt = None
                    else:
                        updated_dt = None

                    if updated_dt is None:
                        # 後備：使用檔案修改時間
                        updated_dt = datetime.fromtimestamp(
                            session_file.stat().st_mtime, tz=timezone.utc
                        )

                    # 補上時區（假設為 UTC）
                    if updated_dt.tzinfo is None:
                        from datetime import timezone as _tz

                        updated_dt = updated_dt.replace(tzinfo=_tz.utc)

                    if updated_dt < cutoff:
                        session_file.unlink()
                        cleanup_count += 1
                        logger.info(f"清理舊會話檔案: {session_file}")

                except Exception as e:
                    logger.warning(f"檢查會話檔案失敗: {session_file}, 錯誤: {e}")
                    continue

            logger.info(f"清理完成，共刪除 {cleanup_count} 個舊會話檔案")
            return cleanup_count

        except Exception as e:
            logger.error(f"清理舊會話失敗: {e}")
            return 0

    def get_session_statistics(self) -> Dict[str, Any]:
        """獲取會話統計資訊"""
        try:
            total_sessions = len(list(self.sessions_dir.glob("*.json")))
            active_sessions = len(self.active_sessions)

            # 統計專案類型
            project_types = {}
            for session_data in self.active_sessions.values():
                industry = session_data.project_data.project_attributes.industry
                if industry:
                    project_types[industry] = project_types.get(industry, 0) + 1

            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "project_types": project_types,
                "last_cleanup": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"獲取會話統計資訊失敗: {e}")
            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "project_types": {},
                "error": str(e),
            }
