from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from django.conf import settings

from fruit_api.services.camera.stereo_camera_service import _require_cv2


class CalibrationStateError(Exception):
    pass


class CalibrationExecutionError(Exception):
    pass


@dataclass
class StereoCalibrationConfig:
    cols: int = 9
    rows: int = 6
    square_mm: float = 25.0
    min_pairs: int = 8

    def to_payload(self) -> Dict[str, object]:
        return asdict(self)


class StereoCalibrationService:
    def __init__(self):
        self.root_dir = Path(settings.MEDIA_ROOT) / "stereo_calibration"
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.active_calib_path = Path(settings.MEASURE_CONFIG["CALIB_NPZ"])

    def _session_dir(self, session_id: str) -> Path:
        return self.root_dir / session_id

    def _session_meta_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "session.json"

    def _result_meta_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "result.json"

    def _ensure_session(self, session_id: Optional[str] = None) -> str:
        if session_id:
            session_dir = self._session_dir(session_id)
            if not session_dir.exists():
                raise CalibrationStateError(f"calibration session not found: {session_id}")
        else:
            session_id = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
            session_dir = self._session_dir(session_id)

        for name in ("left", "right", "preview"):
            (session_dir / name).mkdir(parents=True, exist_ok=True)

        meta_path = self._session_meta_path(session_id)
        if not meta_path.exists():
            meta_path.write_text(
                json.dumps(
                    {
                        "session_id": session_id,
                        "created_at": time.time(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return session_id

    @staticmethod
    def _imwrite_unicode(path: Path, image: np.ndarray) -> None:
        cv2 = _require_cv2()
        suffix = path.suffix or ".png"
        ok, encoded = cv2.imencode(suffix, image)
        if not ok:
            raise CalibrationExecutionError(f"failed to encode image: {path}")
        encoded.tofile(str(path))

    @staticmethod
    def _find_corners(image: np.ndarray, pattern_size: Tuple[int, int]):
        cv2 = _require_cv2()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        variants = [
            gray,
            cv2.equalizeHist(gray),
            255 - gray,
        ]
        flags = cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY
        for variant in variants:
            ok, corners = cv2.findChessboardCornersSB(variant, pattern_size, flags=flags)
            if ok and corners is not None:
                term = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-6)
                cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), term)
                return True, corners
        return False, None

    @staticmethod
    def _draw_corners(image: np.ndarray, pattern_size: Tuple[int, int], corners) -> np.ndarray:
        cv2 = _require_cv2()
        canvas = image.copy()
        cv2.drawChessboardCorners(canvas, pattern_size, corners, True)
        return canvas

    def _list_pairs(self, session_id: str) -> List[Tuple[int, Path, Path]]:
        session_dir = self._session_dir(session_id)
        left_files = sorted((session_dir / "left").glob("left_*.png"))
        right_files = sorted((session_dir / "right").glob("right_*.png"))
        right_map = {path.stem.replace("right_", ""): path for path in right_files}
        pairs: List[Tuple[int, Path, Path]] = []
        for left_path in left_files:
            index_key = left_path.stem.replace("left_", "")
            right_path = right_map.get(index_key)
            if right_path is None:
                continue
            pairs.append((int(index_key), left_path, right_path))
        return pairs

    def session_status(self, session_id: Optional[str] = None) -> Dict[str, object]:
        if not session_id:
            sessions = sorted([path.name for path in self.root_dir.iterdir() if path.is_dir()], reverse=True)
            session_id = sessions[0] if sessions else None
        if not session_id:
            return {"session_id": None, "pair_count": 0, "pairs": []}

        pairs = self._list_pairs(session_id)
        result_meta = {}
        result_path = self._result_meta_path(session_id)
        if result_path.exists():
            result_meta = json.loads(result_path.read_text(encoding="utf-8"))
        return {
            "session_id": session_id,
            "pair_count": len(pairs),
            "pairs": [
                {
                    "index": index,
                    "left_path": str(left_path),
                    "right_path": str(right_path),
                }
                for index, left_path, right_path in pairs
            ],
            "result": result_meta or None,
        }

    def capture_pair(self, left_frame: np.ndarray, right_frame: np.ndarray, session_id: Optional[str] = None) -> Dict[str, object]:
        cv2 = _require_cv2()
        session_id = self._ensure_session(session_id)
        pairs = self._list_pairs(session_id)
        next_index = (pairs[-1][0] + 1) if pairs else 1
        session_dir = self._session_dir(session_id)
        left_path = session_dir / "left" / f"left_{next_index:02d}.png"
        right_path = session_dir / "right" / f"right_{next_index:02d}.png"
        preview_path = session_dir / "preview" / f"pair_{next_index:02d}.jpg"

        self._imwrite_unicode(left_path, left_frame)
        self._imwrite_unicode(right_path, right_frame)

        preview = np.concatenate([left_frame, right_frame], axis=1)
        cv2.putText(
            preview,
            f"pair {next_index:02d}",
            (16, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        self._imwrite_unicode(preview_path, preview)

        payload = self.session_status(session_id)
        payload.update(
            {
                "captured_index": next_index,
                "preview_path": str(preview_path),
            }
        )
        return payload

    def run_calibration(
        self,
        *,
        session_id: str,
        config: StereoCalibrationConfig,
        activate: bool = True,
    ) -> Dict[str, object]:
        cv2 = _require_cv2()
        session_id = self._ensure_session(session_id)
        pairs = self._list_pairs(session_id)
        if len(pairs) < config.min_pairs:
            raise CalibrationStateError(
                f"not enough calibration pairs: {len(pairs)} < {config.min_pairs}"
            )

        pattern_size = (config.cols, config.rows)
        objp = np.zeros((config.rows * config.cols, 3), np.float32)
        objp[:, :2] = np.mgrid[0 : config.cols, 0 : config.rows].T.reshape(-1, 2)
        objp *= float(config.square_mm)

        objpoints: List[np.ndarray] = []
        imgpoints_left: List[np.ndarray] = []
        imgpoints_right: List[np.ndarray] = []
        used_pairs: List[int] = []
        rejected_pairs: List[int] = []
        image_size: Optional[Tuple[int, int]] = None

        debug_dir = self._session_dir(session_id) / "detected"
        debug_dir.mkdir(parents=True, exist_ok=True)

        for index, left_path, right_path in pairs:
            left_data = np.fromfile(str(left_path), dtype=np.uint8)
            right_data = np.fromfile(str(right_path), dtype=np.uint8)
            left_image = cv2.imdecode(left_data, cv2.IMREAD_COLOR)
            right_image = cv2.imdecode(right_data, cv2.IMREAD_COLOR)
            if left_image is None or right_image is None:
                rejected_pairs.append(index)
                continue
            if image_size is None:
                image_size = (left_image.shape[1], left_image.shape[0])

            ok_left, corners_left = self._find_corners(left_image, pattern_size)
            ok_right, corners_right = self._find_corners(right_image, pattern_size)
            if not (ok_left and ok_right and corners_left is not None and corners_right is not None):
                rejected_pairs.append(index)
                continue

            objpoints.append(objp.copy())
            imgpoints_left.append(corners_left)
            imgpoints_right.append(corners_right)
            used_pairs.append(index)

            debug_left = self._draw_corners(left_image, pattern_size, corners_left)
            debug_right = self._draw_corners(right_image, pattern_size, corners_right)
            debug_preview = np.concatenate([debug_left, debug_right], axis=1)
            self._imwrite_unicode(debug_dir / f"pair_{index:02d}.jpg", debug_preview)

        if image_size is None:
            raise CalibrationExecutionError("unable to read any calibration image pairs")
        if len(used_pairs) < config.min_pairs:
            raise CalibrationStateError(
                f"detected corners in only {len(used_pairs)} pairs; need at least {config.min_pairs}"
            )

        single_flags = cv2.CALIB_RATIONAL_MODEL
        rms_left, kl, dl, _, _ = cv2.calibrateCamera(
            objpoints,
            imgpoints_left,
            image_size,
            None,
            None,
            flags=single_flags,
        )
        rms_right, kr, dr, _, _ = cv2.calibrateCamera(
            objpoints,
            imgpoints_right,
            image_size,
            None,
            None,
            flags=single_flags,
        )

        stereo_flags = cv2.CALIB_FIX_INTRINSIC | cv2.CALIB_RATIONAL_MODEL
        criteria = (cv2.TERM_CRITERIA_MAX_ITER + cv2.TERM_CRITERIA_EPS, 100, 1e-6)
        stereo_rms, kl, dl, kr, dr, r, t, e, f = cv2.stereoCalibrate(
            objpoints,
            imgpoints_left,
            imgpoints_right,
            kl,
            dl,
            kr,
            dr,
            image_size,
            criteria=criteria,
            flags=stereo_flags,
        )
        rl, rr, pl, pr, q, _, _ = cv2.stereoRectify(
            kl,
            dl,
            kr,
            dr,
            image_size,
            r,
            t,
            flags=cv2.CALIB_ZERO_DISPARITY,
            alpha=0,
        )

        baseline_mm = float(np.linalg.norm(t.reshape(-1)))
        result_dir = self._session_dir(session_id) / "result"
        result_dir.mkdir(parents=True, exist_ok=True)
        calib_path = result_dir / "calib_stereo.npz"
        np.savez(
            str(calib_path),
            KL=kl,
            DL=dl,
            KR=kr,
            DR=dr,
            R=r,
            T=t,
            E=e,
            F=f,
            RL=rl,
            RR=rr,
            PL=pl,
            PR=pr,
            Q=q,
            image_size=np.array(image_size, dtype=np.int32),
            img_size=np.array(image_size, dtype=np.int32),
            w=int(image_size[0]),
            h=int(image_size[1]),
            baseline_mm=baseline_mm,
            cols=config.cols,
            rows=config.rows,
            square_mm=float(config.square_mm),
            rms_left=float(rms_left),
            rms_right=float(rms_right),
            stereo_rms=float(stereo_rms),
        )

        backup_path = None
        activated_path = None
        if activate:
            self.active_calib_path.parent.mkdir(parents=True, exist_ok=True)
            if self.active_calib_path.exists():
                backup_path = self.active_calib_path.with_name(
                    f"{self.active_calib_path.stem}.bak_{time.strftime('%Y%m%d_%H%M%S')}{self.active_calib_path.suffix}"
                )
                shutil.copy2(self.active_calib_path, backup_path)
            shutil.copy2(calib_path, self.active_calib_path)
            activated_path = self.active_calib_path

        payload = {
            "session_id": session_id,
            "used_pairs": used_pairs,
            "rejected_pairs": rejected_pairs,
            "image_width": int(image_size[0]),
            "image_height": int(image_size[1]),
            "rms_left": round(float(rms_left), 6),
            "rms_right": round(float(rms_right), 6),
            "stereo_rms": round(float(stereo_rms), 6),
            "baseline_mm": round(baseline_mm, 6),
            "output_calib_path": str(calib_path),
            "activated_calib_path": str(activated_path) if activated_path else None,
            "backup_calib_path": str(backup_path) if backup_path else None,
            "config": config.to_payload(),
        }
        self._result_meta_path(session_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return payload


_calibration_service: Optional[StereoCalibrationService] = None


def get_stereo_calibration_service() -> StereoCalibrationService:
    global _calibration_service
    if _calibration_service is None:
        _calibration_service = StereoCalibrationService()
    return _calibration_service
