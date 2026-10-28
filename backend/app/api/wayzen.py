from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.assistant import ChatSession, PendingAction
from app.models.models import User
from app.rag import assistant
from app.rag.embeddings import get_embedder
from app.rag.tools import execute_action

router = APIRouter(prefix="/api/wayzen", tags=["wayzen"])


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=36)

    @field_validator("message")
    @classmethod
    def clean(cls, value: str):
        value = "".join(ch for ch in value if ch.isprintable() or ch in "\n\t").strip()
        if not value:
            raise ValueError("Message cannot be empty")
        return value


@router.get("/status")
def status():
    return {"mode": "full" if settings.llm_configured else "limited", "llm_provider": settings.LLM_PROVIDER or None,
            "embedding_model": get_embedder().model_id, "welcome": assistant.WELCOME,
            "suggested_questions": assistant.SUGGESTED_QUESTIONS}


@router.post("/chat")
def chat(payload: ChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return assistant.handle_message(db, user, payload.message, payload.session_id)


@router.get("/sessions")
def sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (db.query(ChatSession).filter(ChatSession.user_id == user.id)
            .order_by(ChatSession.updated_at.desc()).limit(20).all())
    return [{"id": s.id, "title": s.title, "updated_at": s.updated_at} for s in rows]


def _own_session(db: Session, user: User, session_id: str) -> ChatSession:
    chat = db.get(ChatSession, session_id)
    if chat is None or chat.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return chat


@router.get("/sessions/{session_id}")
def session_detail(session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chat = _own_session(db, user, session_id)
    actions = {a.id: a for a in db.query(PendingAction).filter(PendingAction.session_id == chat.id).all()}
    return {"id": chat.id, "title": chat.title, "messages": [
        assistant.message_out(m, [actions[m.pending_action_id]] if m.pending_action_id in actions else [])
        for m in chat.messages[-50:]]}


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_own_session(db, user, session_id))
    db.commit()


@router.post("/actions/{action_id}/confirm")
def confirm_action(action_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return execute_action(db, user, action_id)


@router.post("/actions/{action_id}/dismiss")
def dismiss_action(action_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    action = db.query(PendingAction).filter(PendingAction.id == action_id).with_for_update().first()
    if action is None or action.user_id != user.id:
        raise HTTPException(404, "Action not found")
    if action.status == "pending":
        action.status = "dismissed"
        db.commit()
    return assistant.action_out(action)
