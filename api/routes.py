"""
統一的 API 路由定義
整合重複的端點，提供一致的接口
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from models.chat_models import ChatMessage, ChatTurnResponse, ChatSession
from models.base_models import IntakeRequest, ClarifyRequest
from models.project_models import ProjectRequest, ProjectResponse
from models.audience_models import AudienceCoachState
from services.session import manager as session_manager
from services.agent import agent as unified_agent
from agents.state_machine_agent import StateMachineAgent
from models.state_machine_models import ProjectSlots

# 導入選項生成路由
from .options_routes import router as options_router

# 創建路由器
router = APIRouter()

# 包含選項生成路由
router.include_router(options_router, prefix="/options", tags=["options"])


# ===== 狀態機硬控流程聊天端點 =====
@router.post("/chat/state-machine", response_model=Dict[str, Any])
async def state_machine_chat(payload: ChatMessage):
    """
    狀態機硬控流程聊天端點
    實現固定的槽位收集流程
    """
    try:
        # 創建或獲取會話
        if payload.session_id and session_manager.get_session(payload.session_id):
            session = session_manager.get_session(payload.session_id)
            # 從會話中獲取現有槽位數據
            current_slots_data = getattr(session, "project_slots", {})
            current_slots = (
                ProjectSlots(**current_slots_data)
                if current_slots_data
                else ProjectSlots()
            )
            is_new = False
        else:
            # 創建新會話和空槽位
            session = session_manager.create_session(user_id=payload.user_id)
            current_slots = ProjectSlots()
            is_new = True

        # 初始化狀態機代理
        from services.llm_client import LLMClient

        llm_client = LLMClient()
        state_machine_agent = StateMachineAgent(llm_client)

        # 處理用戶輸入
        response = await state_machine_agent.process_user_input(
            payload.message.strip(), current_slots
        )

        # 更新會話中的槽位數據
        updated_slots = response.slot_writes or {}
        for key, value in updated_slots.items():
            if hasattr(current_slots, key):
                setattr(current_slots, key, value)

        # 保存更新後的槽位到會話
        # 注意：這裡需要擴展update_session方法來支持project_slots等參數
        # 暫時使用現有的update_session方法
        session_manager.update_session(
            session.session_id, project_data=session.project_data  # 保持現有數據
        )

        return response.dict()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"狀態機聊天處理失敗: {str(e)}")


# ===== 統一的聊天端點 =====
@router.post("/chat/message", response_model=ChatTurnResponse)
async def chat_message(payload: ChatMessage):
    """
    統一的聊天端點
    整合原有的兩個 /chat/message 端點邏輯
    """
    try:
        # 創建或獲取會話
        if payload.session_id and session_manager.get_session(payload.session_id):
            session = session_manager.get_chat_session(payload.session_id)
            is_new = False
        else:
            session = session_manager.create_chat_session(
                user_id=payload.user_id, original_requirement=payload.message.strip()
            )
            is_new = True

        # 更新會話
        if not is_new and payload.message.strip():
            session.answers.append(payload.message.strip())
            session_manager.update_session(session.session_id, answers=session.answers)

        # 使用統一代理處理
        project_data = unified_agent.extract_project_data(session.original_requirement)

        # 計算完整性
        completeness = unified_agent.compute_completeness(project_data)

        # 生成回應
        if completeness["completeness_score"] < 0.8:
            # 需要更多資訊
            next_question = unified_agent.generate_clarification_questions(
                project_data, completeness["missing_keys"]
            )
            if next_question:
                message = f"請告訴我：{next_question[0]}"
            else:
                message = "請提供更多專案細節"

            status = "need_clarification"
        else:
            # 資訊完整，生成提案
            message = "您的需求資訊已經完整，我正在生成企劃提案..."
            status = "complete"

        # 更新會話
        session_manager.update_session(
            session.session_id,
            completeness_score=completeness["completeness_score"],
            missing_keys=completeness["missing_keys"],
            planning_project=project_data.dict(),
        )

        return ChatTurnResponse(
            session_id=session.session_id,
            role="assistant",
            message=message,
            status=status,
            completeness_score=completeness["completeness_score"],
            missing_keys=completeness["missing_keys"],
            asked_questions=session.asked_questions,
            next_question=next_question[0] if next_question else None,
            planning_project=project_data.dict(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"聊天處理失敗: {str(e)}")


# ===== 受眾教練端點 =====
@router.post("/audience-coach/chat", response_model=ChatTurnResponse)
async def audience_coach_chat(payload: ChatMessage):
    """
    受眾教練聊天端點
    整合受眾分析和策略生成功能
    """
    try:
        # 創建或獲取受眾教練會話
        if payload.session_id and session_manager.get_session(payload.session_id):
            session = session_manager.get_audience_coach_session(payload.session_id)
            is_new = False
        else:
            session = session_manager.create_audience_coach_session(
                user_id=payload.user_id, original_requirement=payload.message.strip()
            )
            is_new = True

        # 更新會話
        if not is_new and payload.message.strip():
            session.conversation_history.append(
                {"role": "user", "message": payload.message.strip()}
            )
            session_manager.update_session(
                session.session_id, conversation_history=session.conversation_history
            )

        # 使用統一代理處理
        project_data = unified_agent.extract_project_data(session.original_requirement)

        # 生成受眾洞察
        audience_insights = unified_agent.generate_audience_insights(project_data)

        # 生成受眾策略
        audience_strategy = unified_agent.generate_audience_strategy(project_data)

        # 計算完整性
        completeness = unified_agent.compute_completeness(project_data)

        # 生成回應
        if completeness["completeness_score"] < 0.8:
            message = f"基於您的需求，我已經分析了受眾特點。{audience_insights.interest_analysis}。請告訴我更多關於 {completeness['missing_keys'][0] if completeness['missing_keys'] else '專案細節'} 的資訊。"
            status = "need_clarification"
        else:
            message = f"您的受眾分析已完成！{audience_strategy.targeting_strategy}。建議使用 {', '.join(audience_strategy.channel_mix)} 等渠道觸達目標受眾。"
            status = "complete"

        # 更新會話
        session_manager.update_session(
            session.session_id,
            current_project_data=project_data.dict(),
            audience_insights=audience_insights.dict(),
            audience_strategy=audience_strategy.dict(),
            completeness_score=completeness["completeness_score"],
            missing_audience_info=completeness["missing_keys"],
        )

        return ChatTurnResponse(
            session_id=session.session_id,
            role="assistant",
            message=message,
            status=status,
            completeness_score=completeness["completeness_score"],
            missing_keys=completeness["missing_keys"],
            asked_questions=[],
            planning_project=project_data.dict(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"受眾教練處理失敗: {str(e)}")


# ===== 專案管理端點 =====
@router.post("/project/intake", response_model=ProjectResponse)
async def project_intake(payload: IntakeRequest):
    """統一的專案需求收集端點"""
    try:
        # 使用統一代理分析需求
        project_data = unified_agent.extract_project_data(payload.requirement)
        completeness = unified_agent.compute_completeness(project_data)

        return ProjectResponse(
            project_data=project_data,
            completeness_score=completeness["completeness_score"],
            missing_keys=completeness["missing_keys"],
            message="專案需求已成功收集",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"專案需求收集失敗: {str(e)}")


@router.post("/project/clarify", response_model=ProjectResponse)
async def project_clarify(payload: ClarifyRequest):
    """統一的專案澄清端點"""
    try:
        # 組合增強的需求描述
        enhanced_requirement = (
            f"{payload.original_requirement}\n\n補充資訊：\n"
            + "\n".join(f"- {ans}" for ans in payload.clarification_answers)
        )

        # 使用統一代理處理
        project_data = unified_agent.extract_project_data(enhanced_requirement)
        completeness = unified_agent.compute_completeness(project_data)

        return ProjectResponse(
            project_data=project_data,
            completeness_score=completeness["completeness_score"],
            missing_keys=completeness["missing_keys"],
            message="專案需求已成功澄清",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"專案澄清失敗: {str(e)}")


# ===== 會話管理端點 =====
@router.get("/chat/sessions")
async def list_sessions():
    """統一的會話列表端點"""
    try:
        sessions = session_manager.list_sessions()
        return {"total_sessions": len(sessions), "sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取會話列表失敗: {str(e)}")


@router.get("/chat/sessions/{session_id}")
async def get_session(session_id: str):
    """統一的會話詳情端點"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="會話不存在")
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取會話詳情失敗: {str(e)}")


@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str):
    """統一的會話刪除端點"""
    try:
        if not session_manager.delete_session(session_id):
            raise HTTPException(status_code=404, detail="會話不存在")
        return {"message": "會話已刪除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除會話失敗: {str(e)}")


# ===== 健康檢查端點 =====
@router.get("/health")
async def health_check():
    """健康檢查端點"""
    return {
        "status": "healthy",
        "service": "Unified Planning Assistant API",
        "version": "2.0.0",
        "session_count": session_manager.get_session_count(),
    }
