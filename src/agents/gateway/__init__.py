"""Input Gateway 패키지."""
from .classifier import classify_http_request, classify_slack_event
from .gateway import InputGateway
from .models import TaskEnvelope, TriggerType
from .parsers import (
    parse_cold_email,
    parse_http_weekly_report,
    parse_lead_filter,
    parse_manual,
    parse_slack_work_approval,
)

__all__ = [
    "TaskEnvelope",
    "TriggerType",
    "InputGateway",
    "classify_slack_event",
    "classify_http_request",
    "parse_slack_work_approval",
    "parse_http_weekly_report",
    "parse_lead_filter",
    "parse_cold_email",
    "parse_manual",
]
