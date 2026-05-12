"""Canonical module for SupabaseNaverRepository.

The implementation currently lives in ``supabase_b2_repository`` and is
re-exported here so callers can import from the semantically correct path.

Preferred import::

    from src.core.repositories.supabase_naver_repository import SupabaseNaverRepository

    # or via the package index
    from src.core.repositories import SupabaseNaverRepository

Moving the class body into this file is deferred to a future PR that will
also update ``lambda/`` and ``scripts/`` imports.
"""
from __future__ import annotations

from .supabase_b2_repository import (  # noqa: F401
    SupabaseNaverRepository,
    SupabaseB2Repository,
)

__all__ = ["SupabaseNaverRepository", "SupabaseB2Repository"]
