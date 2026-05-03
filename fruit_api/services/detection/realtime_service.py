import json
import os
import uuid
from typing import Dict

from django.conf import settings

from fruit_api.models import DetectionHistory
from fruit_api.services.label_map_service import translate_label_map, translate_nested_ripeness_counts


class RealtimePayloadError(Exception):
    pass


def validate_realtime_payload(data: Dict) -> None:
    required_keys = ['total_targets', 'fruit_counts', 'ripeness_counts']
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise RealtimePayloadError(f'缺少必要字段: {", ".join(missing)}')


def build_realtime_summary(data: Dict) -> Dict:
    summary = {
        'total_targets': int(data.get('total_targets') or 0),
        'fruit_counts': translate_label_map(data.get('fruit_counts') or {}, label_type='fruit'),
        'ripeness_counts': translate_nested_ripeness_counts(data.get('ripeness_counts') or {}),
    }
    for key in [
        'mode',
        'interval_ms',
        'sample_count',
        'valid_measurements',
        'statistics',
        'camera_profile',
        'runtime_device',
    ]:
        if key in data:
            summary[key] = data.get(key)
    return summary


def save_realtime_report_file(summary: Dict) -> str:
    report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_filename = f'reports/realtime_report_{uuid.uuid4().hex}.json'
    report_path = os.path.join(settings.MEDIA_ROOT, report_filename)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return report_filename


def create_realtime_history(user, summary: Dict, report_filename: str, detail_data: Dict) -> None:
    mode = summary.get('mode') or 'single'
    DetectionHistory.objects.create(
        user=user,
        detection_type='realtime',
        title=f'实时检测会话({mode})',
        options={
            'mode': mode,
            'interval_ms': summary.get('interval_ms'),
            'camera_profile': summary.get('camera_profile'),
        },
        summary=summary,
        detail_data=detail_data,
        report_file=report_filename,
    )


def save_realtime_report(user, data: Dict) -> Dict:
    validate_realtime_payload(data)
    summary = build_realtime_summary(data)
    report_filename = save_realtime_report_file(summary)
    create_realtime_history(
        user,
        summary,
        report_filename,
        {
            'session_report': data,
        },
    )

    return {
        'status': 'success',
        'message': '报告已保存',
        'report_file': report_filename,
    }
