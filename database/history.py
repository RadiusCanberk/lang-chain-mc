from __future__ import annotations

from typing import List, Optional

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict
from sqlalchemy import delete, select
from sqlalchemy.orm.attributes import flag_modified

from database.db import SessionLocal
from database.models.chat_models import Chat, Message, User


class PersistentChatMessageHistory(BaseChatMessageHistory):
    """
    DB-backed, LangChain-compatible message history.

    Persistence:
      users(user_id) -> chats(user_id, chat_id) -> messages(chat_fk, payload)
    """

    def __init__(self, user_id: str, chat_id: str):
        self.user_id = user_id
        self.chat_id = chat_id

    def _ensure_user_and_chat(self) -> int:
        """User + Chat yoksa oluşturur, Chat.id (PK) döndürür."""
        with SessionLocal.begin() as db:
            user = db.get(User, self.user_id)
            if user is None:
                user = User(user_id=self.user_id)
                db.add(user)
                db.flush()

            stmt = select(Chat).where(Chat.user_id == self.user_id, Chat.chat_id == self.chat_id)
            chat = db.execute(stmt).scalars().first()
            if chat is None:
                chat = Chat(user_id=self.user_id, chat_id=self.chat_id)
                db.add(chat)
                db.flush()

            return chat.id

    @property
    def messages(self) -> List[BaseMessage]:
        with SessionLocal() as db:
            stmt = (
                select(Message.payload)
                .join(Chat, Chat.id == Message.chat_fk)
                .where(Chat.user_id == self.user_id, Chat.chat_id == self.chat_id)
                .order_by(Message.created_at.asc(), Message.id.asc())
            )
            rows = db.execute(stmt).all()
            payloads = [r[0] for r in rows]
            return messages_from_dict(payloads)

    def add_message(self, message: BaseMessage) -> None:
        chat_pk = self._ensure_user_and_chat()
        payload = message_to_dict(message)

        with SessionLocal.begin() as db:
            db.add(Message(chat_fk=chat_pk, payload=payload))

    def add_messages(self, messages: List[BaseMessage]) -> None:
        if not messages:
            return

        chat_pk = self._ensure_user_and_chat()
        rows = [Message(chat_fk=chat_pk, payload=message_to_dict(m)) for m in messages]

        with SessionLocal.begin() as db:
            db.add_all(rows)

    def delete_message_after(self, message_index: int) -> None:
        """Belirli bir indeksten sonraki tüm mesajları siler (indeks dahil)."""
        chat_pk = self._ensure_user_and_chat()
        with SessionLocal.begin() as db:
            # Önce o chat'e ait mesajları alıp, id'ye göre sıralayıp sonra siliyoruz
            stmt = select(Message.id).where(Message.chat_fk == chat_pk).order_by(Message.created_at.asc(), Message.id.asc())
            message_ids = db.execute(stmt).scalars().all()
            
            if message_index < len(message_ids):
                ids_to_delete = message_ids[message_index:]
                db.execute(delete(Message).where(Message.id.in_(ids_to_delete)))

    def update_message(self, message_index: int, new_content: str) -> None:
        """Belirli bir indeksteki mesajın içeriğini günceller."""
        chat_pk = self._ensure_user_and_chat()
        with SessionLocal.begin() as db:
            stmt = select(Message).where(Message.chat_fk == chat_pk).order_by(Message.created_at.asc(), Message.id.asc())
            messages = db.execute(stmt).scalars().all()
            
            if message_index < len(messages):
                msg = messages[message_index]
                payload = dict(msg.payload)
                payload["data"]["content"] = new_content
                msg.payload = payload
                flag_modified(msg, "payload")

    def clear(self) -> None:
        with SessionLocal.begin() as db:
            stmt_chat = select(Chat.id).where(Chat.user_id == self.user_id, Chat.chat_id == self.chat_id)
            chat_pk = db.execute(stmt_chat).scalars().first()
            if chat_pk is None:
                return

            db.execute(delete(Message).where(Message.chat_fk == chat_pk))


def get_session_history(user_id: str, chat_id: str) -> BaseChatMessageHistory:
    return PersistentChatMessageHistory(user_id=user_id, chat_id=chat_id)


def clear_history(user_id: str, chat_id: str):
    history = get_session_history(user_id, chat_id)
    history.clear()


def get_chat_pk(user_id: str, chat_id: str) -> Optional[int]:
    """Returns Chat.id (internal PK) if chat exists, otherwise None."""
    with SessionLocal() as db:
        stmt = select(Chat.id).where(Chat.user_id == user_id, Chat.chat_id == chat_id)
        return db.execute(stmt).scalars().first()