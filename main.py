import os
import tempfile
import uuid

from fastapi import FastAPI, Form, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy.orm import Session

import prompts
import storage
from auth import (
    build_google_auth_url,
    verify_state,
    exchange_code_for_userinfo,
    get_or_create_user,
    create_jwt,
    get_current_user,
)
from config import settings
from database import Base, engine, get_db, SessionLocal
from llm import extract_pdf_text, stream_response, summarize_text
from models import User, Conversation, Message, Document
from schemas import ChatRequest, ConversationCreate, ConversationOut, MessageOut, UserOut

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Document Summarizer API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"status": "running", "message": "Dokument API is running"}


# ──────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────

@app.get("/auth/google/login")
def google_login():
    return RedirectResponse(build_google_auth_url())


@app.get("/auth/google/callback")
def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    verify_state(state)
    userinfo = exchange_code_for_userinfo(code)
    user = get_or_create_user(db, userinfo)
    token = create_jwt(user)
    return RedirectResponse(f"{settings.FRONTEND_URL}#token={token}")


@app.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# ──────────────────────────────────────────────────────────
# Conversations
# ──────────────────────────────────────────────────────────

def _get_owned_conversation(db: Session, user: User, conversation_id: str) -> Conversation:
    convo = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return convo


def _messages_payload(convo: Conversation) -> list[dict]:
    """Convert ORM messages to plain dicts before closing the DB session."""
    return [{"role": m.role, "content": m.content} for m in convo.messages]


@app.get("/conversations", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


@app.post("/conversations", response_model=ConversationOut)
def create_conversation(
    body: ConversationCreate = ConversationCreate(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convo = Conversation(user_id=user.id, title=body.title or "New conversation")
    db.add(convo)
    db.commit()
    db.refresh(convo)
    db.add(Message(conversation_id=convo.id, role="system", content=prompts.SYSTEM_PROMPT["content"]))
    db.commit()
    return convo


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convo = _get_owned_conversation(db, user, conversation_id)
    return [m for m in convo.messages if m.role != "system"]


@app.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convo = _get_owned_conversation(db, user, conversation_id)
    for doc in convo.documents:
        try:
            storage.delete_pdf(doc.storage_key)
        except Exception:
            pass
    db.delete(convo)
    db.commit()
    return {"message": "Conversation deleted."}


# ──────────────────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────────────────

@app.post("/chat")
def chat_endpoint(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convo = _get_owned_conversation(db, user, request.conversation_id)

    # Save user message
    db.add(Message(conversation_id=convo.id, role="user", content=request.message))
    db.commit()
    db.refresh(convo)

    # Snapshot history as plain dicts NOW, before the session closes
    history = _messages_payload(convo)
    convo_id = convo.id

    def generate():
        answer = ""
        for token in stream_response(history):
            answer += token
            yield token
        # Use a brand-new session for the write-back because the request
        # session is closed by the time the generator finishes streaming.
        write_db = SessionLocal()
        try:
            write_db.add(Message(conversation_id=convo_id, role="assistant", content=answer))
            write_db.commit()
        finally:
            write_db.close()

    return StreamingResponse(generate(), media_type="text/plain")


# ──────────────────────────────────────────────────────────
# Upload
# ──────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_pdf(
    conversation_id: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    convo = _get_owned_conversation(db, user, conversation_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
        temp.write(await file.read())
        temp_path = temp.name

    try:
        text = extract_pdf_text(temp_path)

        storage_key = f"{user.id}/{conversation_id}/{uuid.uuid4()}-{file.filename}"
        storage.upload_pdf(temp_path, storage_key)

        db.add(Document(
            conversation_id=convo.id,
            filename=file.filename,
            storage_key=storage_key,
        ))
        summary_message = summarize_text(text)
        db.add(Message(
            conversation_id=convo.id,
            role=summary_message["role"],
            content=summary_message["content"],
        ))
        db.commit()
        db.refresh(convo)

        # Snapshot before streaming
        history = _messages_payload(convo)
        convo_id = convo.id

        def generate():
            answer = ""
            for token in stream_response(history):
                answer += token
                yield token
            write_db = SessionLocal()
            try:
                write_db.add(Message(conversation_id=convo_id, role="assistant", content=answer))
                write_db.commit()
            finally:
                write_db.close()

        return StreamingResponse(generate(), media_type="text/plain")
    finally:
        os.remove(temp_path)