from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AppError(Exception):
    message: str
    code: str = "error"
    status_code: int = 400
    details: Dict[str, Any] | None = field(default=None)

    def __str__(self) -> str:
        return self.message


class AppNotFoundError(AppError):
    def __init__(self, message: str = "not found", *, details: Dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="not_found", status_code=404, details=details)


class FileLifecycleError(AppError):
    def __init__(self, message: str, *, details: Dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="file_lifecycle_error", status_code=400, details=details)
