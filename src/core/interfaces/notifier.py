from abc import ABC, abstractmethod
from typing import Any, Optional


class INotifier(ABC):
    @abstractmethod
    def send(self, recipient: str, message: str, **kwargs: Any) -> bool: ...

    @abstractmethod
    def send_error(self, task_id: str, error: Exception, context: Optional[dict] = None) -> bool: ...
