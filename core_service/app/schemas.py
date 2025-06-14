from pydantic import BaseModel, Field
from typing import List, Optional

class QueryInput(BaseModel):
    phone_number: str
    question: str
    user_name: Optional[str] = None
    conversation_id: Optional[str] = None

class ChatHistoryEntry(BaseModel):
    q: str
    a: str

class ConversationResponse(BaseModel):
    conversation_id: str
    answer: str
    chat_history: List[ChatHistoryEntry] = []