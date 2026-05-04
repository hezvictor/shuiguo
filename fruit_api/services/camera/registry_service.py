from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Dict

from django.conf import settings


@dataclass
class CameraRegistryState:
    selection: Dict[str, Any]
    last_scan: Dict[str, Any]
    suggested_intervals: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selection": dict(self.selection),
            "last_scan": dict(self.last_scan),
            "suggested_intervals": dict(self.suggested_intervals),
        }


class CameraRegistryService:
    def __init__(self) -> None:
        self._lock = RLock()

    @staticmethod
    def _default_suggested_intervals() -> Dict[str, int]:
        return {
            "single_interval_ms": 2000,
            "dual_interval_ms": 6000,
        }

    @staticmethod
    def _index_path() -> Path:
        root = Path(settings.MEDIA_ROOT) / "camera_registry"
        root.mkdir(parents=True, exist_ok=True)
        return root / "registry.json"

    @staticmethod
    def _default_state() -> CameraRegistryState:
        config = getattr(settings, "CAMERA_CONFIG", {}) or {}
        single_index = int(config.get("camera_index", 0))
        left_index = int(config.get("left_camera_index", 0))
        right_index = int(config.get("right_camera_index", 1))
        return CameraRegistryState(
            selection={
                "single_camera_index": single_index,
                "dual_left_camera_index": left_index,
                "dual_right_camera_index": right_index,
                "preview_camera_indices": [single_index],
                "backend": config.get("backend", "") or "",
            },
            last_scan={
                "backend": config.get("backend", "") or "",
                "max_index": 0,
                "results": [],
                "pair_results": [],
                "device_catalog": [],
                "opened_count": 0,
                "recommended_dual_pair": None,
                "updated_at": None,
            },
            suggested_intervals={
                **CameraRegistryService._default_suggested_intervals(),
            },
        )

    @classmethod
    def _normalize_suggested_intervals(cls, payload: Dict[str, Any] | None) -> Dict[str, int]:
        defaults = cls._default_suggested_intervals()
        current = dict(payload or {})
        return {
            "single_interval_ms": max(int(current.get("single_interval_ms") or defaults["single_interval_ms"]), defaults["single_interval_ms"]),
            "dual_interval_ms": max(int(current.get("dual_interval_ms") or defaults["dual_interval_ms"]), defaults["dual_interval_ms"]),
        }

    def _load_unlocked(self) -> CameraRegistryState:
        path = self._index_path()
        if not path.exists():
            return self._default_state()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CameraRegistryState(
            selection=payload.get("selection") or self._default_state().selection,
            last_scan=payload.get("last_scan") or self._default_state().last_scan,
            suggested_intervals=self._normalize_suggested_intervals(payload.get("suggested_intervals")),
        )

    def _save_unlocked(self, state: CameraRegistryState) -> Dict[str, Any]:
        path = self._index_path()
        payload = state.to_dict()
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._load_unlocked().to_dict()

    def update_scan(self, scan_payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            state = self._load_unlocked()
            state.last_scan = {
                **state.last_scan,
                **dict(scan_payload or {}),
            }
            results = state.last_scan.get("results") or []
            readable = [item for item in results if item.get("opened")]
            if readable:
                state.selection["single_camera_index"] = int(readable[0]["camera_index"])
            recommended = state.last_scan.get("recommended_dual_pair")
            if recommended and len(recommended) == 2:
                state.selection["dual_left_camera_index"] = int(recommended[0])
                state.selection["dual_right_camera_index"] = int(recommended[1])
            if not state.selection.get("preview_camera_indices"):
                preview_indices = []
                if readable:
                    preview_indices = [int(readable[0]["camera_index"])]
                state.selection["preview_camera_indices"] = preview_indices
            state.suggested_intervals = self._normalize_suggested_intervals(state.suggested_intervals)
            return self._save_unlocked(state)

    def update_selection(self, selection_payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            state = self._load_unlocked()
            selection = dict(state.selection)
            selection.update({key: value for key, value in dict(selection_payload or {}).items() if value is not None})
            selection.setdefault("preview_camera_indices", [])
            state.selection = selection
            state.suggested_intervals = self._normalize_suggested_intervals(state.suggested_intervals)
            return self._save_unlocked(state)


_camera_registry_service: CameraRegistryService | None = None


def get_camera_registry_service() -> CameraRegistryService:
    global _camera_registry_service
    if _camera_registry_service is None:
        _camera_registry_service = CameraRegistryService()
    return _camera_registry_service
