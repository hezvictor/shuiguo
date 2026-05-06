from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List

from django.conf import settings

from fruit_api.exceptions import AppError


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
        return CameraRegistryState(
            selection={
                "single_camera_index": None,
                "dual_left_camera_index": None,
                "dual_right_camera_index": None,
                "preview_camera_indices": [],
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

    @staticmethod
    def _normalize_selection(payload: Dict[str, Any] | None) -> Dict[str, Any]:
        defaults = CameraRegistryService._default_state().selection
        current = dict(payload or {})
        selection = {
            "single_camera_index": current.get("single_camera_index"),
            "dual_left_camera_index": current.get("dual_left_camera_index"),
            "dual_right_camera_index": current.get("dual_right_camera_index"),
            "preview_camera_indices": list(current.get("preview_camera_indices") or []),
            "backend": current.get("backend", defaults.get("backend", "")) or "",
        }
        for key in ("single_camera_index", "dual_left_camera_index", "dual_right_camera_index"):
            if selection[key] is not None:
                selection[key] = int(selection[key])
        return selection

    @staticmethod
    def _normalize_last_scan(payload: Dict[str, Any] | None) -> Dict[str, Any]:
        defaults = CameraRegistryService._default_state().last_scan
        current = dict(payload or {})
        return {
            "backend": current.get("backend", defaults["backend"]) or "",
            "max_index": int(current.get("max_index") or defaults["max_index"]),
            "results": list(current.get("results") or []),
            "pair_results": list(current.get("pair_results") or []),
            "device_catalog": list(current.get("device_catalog") or []),
            "opened_count": int(current.get("opened_count") or 0),
            "recommended_dual_pair": current.get("recommended_dual_pair"),
            "updated_at": current.get("updated_at"),
        }

    @staticmethod
    def _readable_results(last_scan: Dict[str, Any]) -> List[Dict[str, Any]]:
        readable = []
        for item in last_scan.get("results") or []:
            if not item.get("opened"):
                continue
            if "read_ok" in item and not item.get("read_ok"):
                continue
            readable.append(item)
        return readable

    @classmethod
    def _build_capabilities(cls, *, selection: Dict[str, Any], last_scan: Dict[str, Any]) -> Dict[str, Any]:
        readable_results = cls._readable_results(last_scan)
        readable_indices = [int(item["camera_index"]) for item in readable_results if item.get("camera_index") is not None]
        readable_index_set = set(readable_indices)
        scan_completed = bool(last_scan.get("updated_at") or last_scan.get("results") or last_scan.get("max_index"))
        readable_count = len(readable_indices)

        single_index = selection.get("single_camera_index")
        dual_left = selection.get("dual_left_camera_index")
        dual_right = selection.get("dual_right_camera_index")

        single_configured = single_index is not None
        dual_configured = dual_left is not None and dual_right is not None

        if not scan_completed:
            single_reason = "camera_not_scanned"
            single_message = "尚未扫描摄像头，请先到摄像头拍照与配置页扫描并保存默认单摄配置。"
            single_available = False
        elif readable_count <= 0:
            single_reason = "camera_not_detected"
            single_message = "当前未检测到可用摄像头，实时检测暂不可用。"
            single_available = False
        elif not single_configured:
            single_reason = "single_camera_not_configured"
            single_message = "尚未配置默认单摄像头，实时检测暂不可用。"
            single_available = False
        elif int(single_index) not in readable_index_set:
            single_reason = "configured_camera_not_available"
            single_message = "默认单摄像头当前不可用，请重新扫描并检查摄像头配置。"
            single_available = False
        else:
            single_reason = None
            single_message = "默认单摄像头已配置，可使用水果种类和熟度实时检测。"
            single_available = True

        if not scan_completed:
            dual_reason = "camera_not_scanned"
            dual_message = "尚未扫描摄像头，请先扫描并配置双目摄像头。"
            dual_available = False
        elif readable_count < 2:
            dual_reason = "dual_camera_requires_two_devices"
            dual_message = "双目摄像头测果径需要 2 台摄像头，当前测量果径暂不可用。"
            dual_available = False
        elif not dual_configured:
            dual_reason = "dual_camera_not_configured"
            dual_message = "尚未配置默认双目摄像头，果径实时检测暂不可用。"
            dual_available = False
        elif int(dual_left) == int(dual_right):
            dual_reason = "invalid_dual_camera_selection"
            dual_message = "默认双目摄像头配置无效，左右摄像头不能相同。"
            dual_available = False
        elif int(dual_left) not in readable_index_set or int(dual_right) not in readable_index_set:
            dual_reason = "configured_camera_not_available"
            dual_message = "默认双目摄像头当前不可用，请重新扫描并检查双摄配置。"
            dual_available = False
        else:
            dual_reason = None
            dual_message = "默认双目摄像头已配置，可使用果径实时检测。"
            dual_available = True

        return {
            "scan_completed": scan_completed,
            "readable_camera_count": readable_count,
            "readable_camera_indices": readable_indices,
            "single": {
                "configured": single_configured,
                "available": single_available,
                "reason_code": single_reason,
                "message": single_message,
            },
            "dual": {
                "configured": dual_configured,
                "available": dual_available,
                "reason_code": dual_reason,
                "message": dual_message,
            },
            "realtime": {
                "classification_available": single_available,
                "ripeness_available": single_available,
                "diameter_available": dual_available,
                "hybrid_available": dual_available,
            },
        }

    @classmethod
    def _with_capabilities(cls, state: CameraRegistryState) -> Dict[str, Any]:
        payload = state.to_dict()
        payload["capabilities"] = cls._build_capabilities(
            selection=payload.get("selection") or {},
            last_scan=payload.get("last_scan") or {},
        )
        return payload

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
            selection=self._normalize_selection(payload.get("selection")),
            last_scan=self._normalize_last_scan(payload.get("last_scan")),
            suggested_intervals=self._normalize_suggested_intervals(payload.get("suggested_intervals")),
        )

    def _save_unlocked(self, state: CameraRegistryState) -> Dict[str, Any]:
        path = self._index_path()
        payload = state.to_dict()
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._with_capabilities(self._load_unlocked())

    def update_scan(self, scan_payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            state = self._load_unlocked()
            state.last_scan = {
                **state.last_scan,
                **dict(scan_payload or {}),
            }
            state.last_scan["updated_at"] = state.last_scan.get("updated_at") or time.time()
            state.suggested_intervals = self._normalize_suggested_intervals(state.suggested_intervals)
            self._save_unlocked(state)
            return self._with_capabilities(state)

    def update_selection(self, selection_payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            state = self._load_unlocked()
            selection = dict(state.selection)
            selection.update(dict(selection_payload or {}))
            selection.setdefault("preview_camera_indices", [])
            state.selection = self._normalize_selection(selection)
            state.suggested_intervals = self._normalize_suggested_intervals(state.suggested_intervals)
            self._save_unlocked(state)
            return self._with_capabilities(state)

    def validate_realtime_mode(
        self,
        *,
        mode: str,
        camera_index: int | None = None,
        left_camera_index: int | None = None,
        right_camera_index: int | None = None,
    ) -> Dict[str, Any]:
        snapshot = self.snapshot()
        selection = snapshot.get("selection") or {}
        capabilities = snapshot.get("capabilities") or {}
        readable_indices = set(capabilities.get("readable_camera_indices") or [])

        if mode == "single":
            resolved_camera_index = camera_index if camera_index is not None else selection.get("single_camera_index")
            single = capabilities.get("single") or {}
            if not single.get("available"):
                raise AppError(
                    message=single.get("message") or "默认单摄像头不可用。",
                    code=single.get("reason_code") or "single_camera_not_configured",
                    status_code=400,
                )
            if resolved_camera_index is None or int(resolved_camera_index) not in readable_indices:
                raise AppError(
                    message="默认单摄像头当前不可用，请重新扫描并检查摄像头配置。",
                    code="configured_camera_not_available",
                    status_code=400,
                )
            return {"camera_index": int(resolved_camera_index)}

        resolved_left = left_camera_index if left_camera_index is not None else selection.get("dual_left_camera_index")
        resolved_right = right_camera_index if right_camera_index is not None else selection.get("dual_right_camera_index")
        dual = capabilities.get("dual") or {}
        if not dual.get("available"):
            raise AppError(
                message=dual.get("message") or "默认双目摄像头不可用。",
                code=dual.get("reason_code") or "dual_camera_not_configured",
                status_code=400,
            )
        if resolved_left is None or resolved_right is None:
            raise AppError(
                message="尚未配置默认双目摄像头，果径实时检测暂不可用。",
                code="dual_camera_not_configured",
                status_code=400,
            )
        if int(resolved_left) == int(resolved_right):
            raise AppError(
                message="默认双目摄像头配置无效，左右摄像头不能相同。",
                code="invalid_dual_camera_selection",
                status_code=400,
            )
        if int(resolved_left) not in readable_indices or int(resolved_right) not in readable_indices:
            raise AppError(
                message="默认双目摄像头当前不可用，请重新扫描并检查双摄配置。",
                code="configured_camera_not_available",
                status_code=400,
            )
        return {
            "left_camera_index": int(resolved_left),
            "right_camera_index": int(resolved_right),
        }


_camera_registry_service: CameraRegistryService | None = None


def get_camera_registry_service() -> CameraRegistryService:
    global _camera_registry_service
    if _camera_registry_service is None:
        _camera_registry_service = CameraRegistryService()
    return _camera_registry_service
