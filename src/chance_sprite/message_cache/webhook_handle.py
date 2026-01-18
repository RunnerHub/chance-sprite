from dataclasses import dataclass


@dataclass(frozen=True)
class WebhookHandle:
    message_id: int
    webhook_id: int
    webhook_token: str
    expires_at: int
    original_target: int | None
