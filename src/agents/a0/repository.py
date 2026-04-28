from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AdminInviteMail


class IAdminInviteInboxRepository(ABC):
    @abstractmethod
    def list_pending_invites(
        self,
        *,
        admin_email: str,
        subject_query: str,
    ) -> list[AdminInviteMail]: ...

    @abstractmethod
    def mark_processed(self, message_id: str) -> None: ...
