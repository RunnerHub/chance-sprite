from dataclasses import dataclass


@dataclass(frozen=True)
class WebhookHandle:
    message_id: int
    webhook_id: int
    expires_at: int
    original_target: int | None
