"""Browser 제어 패키지 (Playwright 기반, STUB 상태)."""
from .executor import BrowserExecutor
from .self_healing_locator import LocatorResult, LocatorSpec, SelfHealingLocator
from .session_manager import BrowserSessionExpiredError, BrowserSessionManager

__all__ = [
    "BrowserSessionManager",
    "BrowserSessionExpiredError",
    "SelfHealingLocator",
    "LocatorSpec",
    "LocatorResult",
    "BrowserExecutor",
]
