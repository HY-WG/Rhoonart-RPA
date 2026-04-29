"""Approval Queue 단위 테스트."""
from __future__ import annotations

import pytest

from src.agents.approval.in_memory import InMemoryApprovalRepository
from src.agents.approval.models import ApprovalRecord, ApprovalRequest, ApprovalStatus
from src.agents.approval.queue import ApprovalQueue


# ── 픽스처 ────────────────────────────────────────────────────────────────

class _FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, recipient: str, message: str) -> None:
        self.sent.append({"recipient": recipient, "message": message})


def _make_request(task_id: str = "A-2") -> ApprovalRequest:
    return ApprovalRequest(
        trace_id="trc-test001",
        task_id=task_id,
        summary="테스트 승인 요청",
        risk_level="high",
        preview={"work_title": "테스트 작품", "channel_name": "테스트채널"},
        checkpoint={
            "trace_id": "trc-test001",
            "envelope": {
                "task_id": task_id,
                "envelope_id": "env-test001",
                "instruction": "테스트",
                "context": {},
            },
            "trace_steps": [],
            "pending_thought": {
                "reasoning": "테스트 이유",
                "selected_tool": "a2_work_approval",
                "tool_input": {"channel_name": "테스트채널", "work_title": "테스트 작품", "dry_run": True},
                "requires_approval": True,
                "risk_level": "high",
                "confidence": 0.9,
            },
        },
    )


@pytest.fixture()
def repo() -> InMemoryApprovalRepository:
    return InMemoryApprovalRepository()


@pytest.fixture()
def notifier() -> _FakeNotifier:
    return _FakeNotifier()


@pytest.fixture()
def queue(repo: InMemoryApprovalRepository, notifier: _FakeNotifier) -> ApprovalQueue:
    return ApprovalQueue(repo=repo, notifier=notifier)


# ── create ────────────────────────────────────────────────────────────────

def test_create_returns_approval_id(queue: ApprovalQueue) -> None:
    approval_id = queue.create(_make_request())
    assert approval_id.startswith("apv-")


def test_create_saves_pending_record(queue: ApprovalQueue, repo: InMemoryApprovalRepository) -> None:
    approval_id = queue.create(_make_request())
    record = repo.get(approval_id)
    assert record is not None
    assert record.status == ApprovalStatus.PENDING
    assert record.task_id == "A-2"


def test_create_sends_slack_notification(queue: ApprovalQueue, notifier: _FakeNotifier) -> None:
    queue.create(_make_request())
    assert len(notifier.sent) == 1
    sent = notifier.sent[0]
    assert sent["recipient"] == "#rpa-approvals"
    assert "승인 요청" in sent["message"]


def test_create_notification_failure_does_not_raise(
    repo: InMemoryApprovalRepository,
) -> None:
    """알림 실패가 create()를 막지 않아야 한다."""
    class BrokenNotifier:
        def send(self, **kwargs):
            raise RuntimeError("Slack down")

    queue = ApprovalQueue(repo=repo, notifier=BrokenNotifier())
    approval_id = queue.create(_make_request())  # 예외 없이 통과
    assert repo.get(approval_id) is not None


# ── get / list_pending ────────────────────────────────────────────────────

def test_get_existing(queue: ApprovalQueue) -> None:
    approval_id = queue.create(_make_request())
    record = queue.get(approval_id)
    assert record is not None
    assert record.approval_id == approval_id


def test_get_nonexistent_returns_none(queue: ApprovalQueue) -> None:
    assert queue.get("apv-nonexistent") is None


def test_list_pending(queue: ApprovalQueue) -> None:
    queue.create(_make_request("A-2"))
    queue.create(_make_request("B-2"))
    pending = queue.list_pending()
    assert len(pending) == 2
    assert all(r.status == ApprovalStatus.PENDING for r in pending)


# ── reject ────────────────────────────────────────────────────────────────

def test_reject_changes_status(queue: ApprovalQueue) -> None:
    approval_id = queue.create(_make_request())
    queue.reject(approval_id, decided_by="admin", note="부적절한 요청")
    record = queue.get(approval_id)
    assert record is not None
    assert record.status == ApprovalStatus.REJECTED
    assert record.decided_by == "admin"
    assert record.decision_note == "부적절한 요청"


def test_reject_nonexistent_raises(queue: ApprovalQueue) -> None:
    with pytest.raises(ValueError, match="찾을 수 없습니다"):
        queue.reject("apv-ghost", decided_by="admin")


def test_reject_already_processed_raises(queue: ApprovalQueue) -> None:
    approval_id = queue.create(_make_request())
    queue.reject(approval_id, decided_by="admin")
    with pytest.raises(ValueError, match="이미 처리된"):
        queue.reject(approval_id, decided_by="admin")


def test_reject_removes_from_pending(queue: ApprovalQueue) -> None:
    approval_id = queue.create(_make_request())
    queue.reject(approval_id, decided_by="admin")
    pending = queue.list_pending()
    assert all(r.approval_id != approval_id for r in pending)


# ── approve (dry_run 체크포인트) ──────────────────────────────────────────

def test_approve_nonexistent_raises(queue: ApprovalQueue) -> None:
    with pytest.raises(ValueError, match="찾을 수 없습니다"):
        queue.approve("apv-ghost", decided_by="admin")


def test_approve_already_rejected_raises(queue: ApprovalQueue) -> None:
    approval_id = queue.create(_make_request())
    queue.reject(approval_id, decided_by="admin")
    with pytest.raises(ValueError, match="이미 처리된"):
        queue.approve(approval_id, decided_by="admin")


def test_approve_dry_run_returns_result(queue: ApprovalQueue) -> None:
    """dry_run=True 체크포인트는 실제 외부 호출 없이 완료돼야 한다."""
    from src.agents.approval.in_memory import InMemoryApprovalRepository
    from src.agents.runtime.agent import FakeLLMClient
    from src.agents.repository import InMemoryAgentTraceRepository
    from src.agents.runtime.agent import RhoArtAgent
    from src.agents.tools.registry import ToolRegistry, RiskLevel
    from pydantic import BaseModel

    # 최소 ToolRegistry 구성
    mini_registry = ToolRegistry()

    class _EchoInput(BaseModel):
        message: str = "ok"
        dry_run: bool = True

    @mini_registry.register(
        name="a2_work_approval",
        description="테스트 도구",
        input_model=_EchoInput,
        risk_level=RiskLevel.LOW,
        requires_approval=False,
    )
    def _echo(inp: _EchoInput) -> dict:
        return {"status": "ok", "dry_run": inp.dry_run}

    trace_repo = InMemoryAgentTraceRepository()
    approval_repo = InMemoryApprovalRepository()
    fake_llm = FakeLLMClient([])  # finish로 폴백

    inner_queue = ApprovalQueue(
        repo=approval_repo,
        notifier=_FakeNotifier(),
        tool_registry=mini_registry,
    )
    agent = RhoArtAgent(
        tool_registry=mini_registry,
        approval_queue=inner_queue,
        trace_repo=trace_repo,
        llm_client=fake_llm,
        dry_run_override=True,
    )
    inner_queue._tools = mini_registry  # 재주입

    approval_id = inner_queue.create(_make_request())
    result = inner_queue.approve(approval_id, decided_by="admin")
    assert result is not None


# ── InMemoryApprovalRepository 직접 테스트 ────────────────────────────────

def test_repo_save_and_get() -> None:
    repo = InMemoryApprovalRepository()
    req = _make_request()
    record = ApprovalRecord.from_request(req)
    repo.save(record)
    fetched = repo.get(record.approval_id)
    assert fetched is not None
    assert fetched.approval_id == record.approval_id


def test_repo_update_status() -> None:
    repo = InMemoryApprovalRepository()
    req = _make_request()
    record = ApprovalRecord.from_request(req)
    repo.save(record)
    repo.update_status(record.approval_id, ApprovalStatus.REJECTED, decided_by="tester")
    fetched = repo.get(record.approval_id)
    assert fetched.status == ApprovalStatus.REJECTED
    assert fetched.decided_by == "tester"


def test_repo_save_execution_result() -> None:
    repo = InMemoryApprovalRepository()
    req = _make_request()
    record = ApprovalRecord.from_request(req)
    repo.save(record)
    repo.save_execution_result(record.approval_id, {"status": "completed"})
    fetched = repo.get(record.approval_id)
    assert fetched.status == ApprovalStatus.EXECUTED
    assert fetched.execution_result == {"status": "completed"}
