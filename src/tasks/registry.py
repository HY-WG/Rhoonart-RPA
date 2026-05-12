"""Central task handler registry.

Maps task IDs (e.g. "A-2") to their ITaskHandler instances.

Usage in routes
---------------
    from src.tasks.registry import TASK_REGISTRY
    from src.api.dependencies import invoke_lambda

    handler = TASK_REGISTRY.get(task_id.upper())
    if not handler:
        raise HTTPException(404, detail=f"unknown task: {task_id}")
    return handler.execute(payload, invoker=invoke_lambda)

Adding a new task
-----------------
1. Create ``src/tasks/<id_lower>_handler.py`` with a class implementing ITaskHandler.
2. Import and add an instance to ``_HANDLERS`` below.
"""
from __future__ import annotations

from src.core.interfaces.task_handler import ITaskHandler
from src.tasks.a2_handler import A2TaskHandler
from src.tasks.a3_handler import A3TaskHandler
from src.tasks.b2_handler import B2TaskHandler
from src.tasks.c1_handler import C1TaskHandler
from src.tasks.c2_handler import C2TaskHandler
from src.tasks.c3_handler import C3TaskHandler
from src.tasks.c4_handler import C4TaskHandler
from src.tasks.d3_handler import D3TaskHandler

_HANDLERS: list[ITaskHandler] = [
    A2TaskHandler(),
    A3TaskHandler(),
    B2TaskHandler(),
    C1TaskHandler(),
    C2TaskHandler(),
    C3TaskHandler(),
    C4TaskHandler(),
    D3TaskHandler(),
]

TASK_REGISTRY: dict[str, ITaskHandler] = {
    handler.meta.task_id: handler
    for handler in _HANDLERS
}


def list_all_tasks() -> list[dict[str, str]]:
    """Return a list of all registered task metadata dicts.

    Each dict contains ``task_id``, ``task_name``, and ``lambda_module`` so the
    admin UI can enumerate available tasks without hard-coding them.
    """
    return [
        {
            "task_id": handler.meta.task_id,
            "task_name": handler.meta.task_name,
            "lambda_module": handler.meta.lambda_module,
        }
        for handler in _HANDLERS
    ]
