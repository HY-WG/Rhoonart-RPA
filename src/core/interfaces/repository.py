from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from ...models import (
    Creator, OnboardingStatus,
    WorkRequest, RequestStatus,
    ChannelStat, RightsHolder,
    Lead, LeadFilter,
    LogEntry,
    NaverClipApplicant,
    ReliefRequest,
    ReliefRequestItem,
    ReliefRequestStatus,
    MailTemplate,
    OutboundMail,
    UploadedDocument,
    RightsHolderContact,
)


class ICreatorRepository(ABC):
    @abstractmethod
    def get_new_contracts(self, since: datetime) -> list[Creator]: ...

    @abstractmethod
    def update_onboarding_status(self, creator_id: str, status: OnboardingStatus) -> None: ...


class IWorkRequestRepository(ABC):
    @abstractmethod
    def get_request_by_message_ts(self, message_ts: str) -> Optional[WorkRequest]: ...

    @abstractmethod
    def save_request(self, request: WorkRequest) -> None: ...

    @abstractmethod
    def update_request_status(self, request_id: str, status: RequestStatus) -> None: ...


class INaverClipRepository(ABC):
    @abstractmethod
    def create_applicant(self, applicant: NaverClipApplicant) -> NaverClipApplicant: ...

    @abstractmethod
    def list_applicants(self) -> list[NaverClipApplicant]: ...

    @abstractmethod
    def get_applicants_by_month(self, year: int, month: int) -> list[NaverClipApplicant]: ...


class IPerformanceRepository(ABC):
    @abstractmethod
    def get_content_list(self) -> list[tuple[str, str]]:
        """(식별코드, 콘텐츠명) 튜플 목록 반환."""
        ...

    @abstractmethod
    def upsert_channel_stats(self, stats: list[ChannelStat]) -> int: ...

    @abstractmethod
    def get_rights_holders(self) -> list[RightsHolder]:
        """'작품 관리' 탭에서 권리사 목록(이메일, 대시보드 URL 포함) 반환."""
        ...


class ILeadRepository(ABC):
    @abstractmethod
    def upsert_leads(self, leads: list[Lead]) -> int: ...

    @abstractmethod
    def get_leads_for_email(self, filters: LeadFilter) -> list[Lead]: ...

    @abstractmethod
    def update_lead_email_status(self, channel_id: str, status: str) -> None: ...


class ILogRepository(ABC):
    @abstractmethod
    def write_log(self, entry: LogEntry) -> None: ...


class IReliefRequestRepository(ABC):
    @abstractmethod
    def list_requests(
        self,
        status: Optional[ReliefRequestStatus] = None,
    ) -> list[ReliefRequest]: ...

    @abstractmethod
    def get_request(self, request_id: str) -> Optional[ReliefRequest]: ...

    @abstractmethod
    def save_request(self, request: ReliefRequest) -> None: ...

    @abstractmethod
    def update_request(self, request: ReliefRequest) -> None: ...

    @abstractmethod
    def list_request_items(self, request_id: str) -> list[ReliefRequestItem]: ...

    @abstractmethod
    def replace_request_items(self, request_id: str, items: list[ReliefRequestItem]) -> None: ...

    @abstractmethod
    def get_mail_template(self, template_key: str) -> Optional[MailTemplate]: ...

    @abstractmethod
    def save_mail_template(self, template: MailTemplate) -> None: ...

    @abstractmethod
    def list_outbound_mails(self, request_id: str) -> list[OutboundMail]: ...

    @abstractmethod
    def save_outbound_mail(self, mail: OutboundMail) -> None: ...

    @abstractmethod
    def save_uploaded_document(self, document: UploadedDocument) -> None: ...


class IRightsHolderDirectory(ABC):
    @abstractmethod
    def resolve_contacts(self, work_titles: list[str]) -> list[RightsHolderContact]: ...
