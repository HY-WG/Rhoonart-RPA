# -*- coding: utf-8 -*-
"""D-2 Lambda 엔트리포인트 — 저작권 소명 공문 요청 (CS) 백오피스 API.

트리거: API Gateway HTTP Proxy (모든 /api/* 경로)
ASGI 어댑터: Mangum (FastAPI ↔ Lambda event/context)

엔드포인트:
  POST /api/relief-requests              신규 구제 신청 접수 + 관리자 Slack 알림
  GET  /api/admin/relief-requests        신청 목록 조회
  GET  /api/admin/relief-requests/{id}   신청 상세 조회
  POST /api/admin/relief-requests/{id}/send-mails  권리사 메일 발송

환경 변수:
  SLACK_BOT_TOKEN          Slack Bot OAuth Token
  SLACK_RELIEF_CHANNEL     신규 신청 알림 채널 ID (예: #저작권소명-알림)
  GOOGLE_CREDENTIALS_FILE  서비스 계정 키 파일 (기본: credentials.json)
  RIGHTS_HOLDER_SHEET_ID   권리사 연락처 시트 ID
                           (1JZ0eLnvMgpjAehpxRfPN2RiG6Pd22EidnnG8tmAvlKQ)
  RIGHTS_HOLDER_GID        권리사 탭 GID (기본: 240557957)
  SENDER_EMAIL             발신 이메일 주소 (hoyoungy2@gmail.com)
  RELIEF_DB_TYPE           저장소 유형: "memory" (기본, 개발) / "supabase" (운영)
  SUPABASE_URL             Supabase 프로젝트 URL (RELIEF_DB_TYPE=supabase 시 필수)
  SUPABASE_KEY             Supabase service_role 키 (RELIEF_DB_TYPE=supabase 시 필수)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 환경 변수 ──────────────────────────────────────────────────────────────────
SLACK_TOKEN       = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_RELIEF_CH   = os.environ.get("SLACK_RELIEF_CHANNEL", "")
RELIEF_DB_TYPE    = os.environ.get("RELIEF_DB_TYPE", "memory")
# ──────────────────────────────────────────────────────────────────────────────

from src.backoffice.app import build_app
from src.backoffice.dependencies import build_demo_service
from src.core.notifiers.slack_notifier import SlackNotifier
from src.core.logger import CoreLogger

log = CoreLogger(__name__)


def _build_slack_notifier():
    """Slack 알림 클라이언트 생성. 환경변수 미설정 시 None 반환."""
    if not SLACK_TOKEN or not SLACK_RELIEF_CH:
        log.info("[D-2] Slack 환경변수 미설정 — 알림 비활성화")
        return None
    return SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_RELIEF_CH)


def _build_service():
    """저장소 유형에 따라 ReliefRequestService 생성.

    RELIEF_DB_TYPE=memory   → InMemoryReliefRequestRepository (개발/테스트)
    RELIEF_DB_TYPE=supabase → SupabaseReliefRequestRepository (운영)
    """
    if RELIEF_DB_TYPE == "supabase":
        try:
            from supabase import create_client  # type: ignore
            from src.core.repositories.supabase_relief_repository import (
                SupabaseReliefRequestRepository,
                SupabaseRightsHolderDirectory,
            )
            from src.core.notifiers.email_notifier import EmailNotifier
            from src.services.relief_request_service import ReliefRequestService

            supabase_url = os.environ["SUPABASE_URL"]
            supabase_key = os.environ["SUPABASE_KEY"]
            client = create_client(supabase_url, supabase_key)

            repo      = SupabaseReliefRequestRepository(client)
            directory = SupabaseRightsHolderDirectory(client)
            email_notifier = EmailNotifier(
                sender_email=os.environ.get("SENDER_EMAIL", ""),
                use_ses=os.environ.get("USE_SES", "false").lower() == "true",
                # AWS_REGION / SMTP_* は EmailNotifier が os.getenv() で直接読み込むため
                # コンストラクタ引数として渡す必要はない
            )

            log.info("[D-2] Supabase 연결 완료 (%s)", supabase_url)
            return ReliefRequestService(
                repo=repo,
                rights_holder_directory=directory,
                email_notifier=email_notifier,
            )
        except ImportError as exc:
            log.warning("[D-2] supabase 패키지 없음 — InMemory로 폴백 (%s)", exc)
        except KeyError as exc:
            log.warning("[D-2] 환경변수 %s 미설정 — InMemory로 폴백", exc)
        except Exception as exc:
            log.error("[D-2] Supabase 연결 실패 — InMemory로 폴백: %s", exc)

    return build_demo_service()


# FastAPI 앱 (Lambda cold start 시 1회 초기화)
_service        = _build_service()
_slack_notifier = _build_slack_notifier()
_app            = build_app(service=_service, slack_notifier=_slack_notifier)


def handler(event: dict, context) -> dict:
    """Lambda 핸들러 진입점.

    Mangum이 설치된 경우 API Gateway HTTP Proxy 이벤트를 FastAPI로 라우팅.
    Mangum 미설치 시 에러 메시지 반환.
    """
    try:
        from mangum import Mangum
        asgi_handler = Mangum(_app, lifespan="off")
        return asgi_handler(event, context)
    except ImportError:
        log.error("[D-2] mangum 패키지가 설치되지 않았습니다. `pip install mangum`")
        return {
            "statusCode": 500,
            "body": '{"detail": "mangum not installed"}',
            "headers": {"Content-Type": "application/json"},
        }


# 로컬 테스트: uvicorn lambda.d2_relief_request_handler:_app --reload
if __name__ == "__main__":
    from dotenv import load_dotenv
    import uvicorn  # type: ignore
    load_dotenv()
    uvicorn.run(_app, host="0.0.0.0", port=8002, reload=False)
