from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OnboardingStatus(str, Enum):
    """온보딩 진행 상태.

    값(value)은 Google Sheets '크리에이터' 탭에 한국어로 그대로 저장됩니다.
    저장 형식을 변경하면 기존 시트 데이터가 깨지므로 절대 변경하지 마세요.
    UI 표시용 레이블이 필요하면 .label 프로퍼티를 사용하세요.
    """

    PENDING = "대기"
    SENT    = "발송완료"
    FAILED  = "발송실패"

    @property
    def label(self) -> str:
        """사람이 읽기 쉬운 표시 레이블."""
        _labels = {
            OnboardingStatus.PENDING: "대기",
            OnboardingStatus.SENT:    "발송 완료",
            OnboardingStatus.FAILED:  "발송 실패",
        }
        return _labels[self]


@dataclass
class Creator:
    creator_id: str
    name: str
    phone: str
    contract_date: datetime
    channel_url: Optional[str] = None
    email: Optional[str] = None
    onboarding_status: OnboardingStatus = OnboardingStatus.PENDING
    row_index: Optional[int] = None  # 시트 행 번호 (업데이트 시 사용)

    @classmethod
    def from_sheet_row(cls, row: dict, row_index: int) -> "Creator":
        return cls(
            creator_id=row.get("creator_id", ""),
            name=row.get("name", ""),
            phone=row.get("phone", ""),
            contract_date=datetime.fromisoformat(row["contract_date"]) if row.get("contract_date") else datetime.now(),
            channel_url=row.get("channel_url"),
            email=row.get("email"),
            onboarding_status=OnboardingStatus(row.get("onboarding_status", "대기")),
            row_index=row_index,
        )
