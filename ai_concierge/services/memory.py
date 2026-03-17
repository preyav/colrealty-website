from ai_concierge.models import AIConversationMessage


def save_message(session_id: str, role: str, message: str, metadata: dict | None = None):
    return AIConversationMessage.objects.create(
        session_id=session_id,
        role=role,
        message=message,
        metadata=metadata or {},
    )


def get_recent_messages(session_id: str, limit: int = 12):
    return AIConversationMessage.objects.filter(session_id=session_id).order_by("-created_at")[:limit][::-1]
