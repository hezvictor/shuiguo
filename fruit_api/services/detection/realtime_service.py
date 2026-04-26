import json
import os
import uuid
from typing import Dict

from django.conf import settings

from fruit_api.models import DetectionHistory


class RealtimePayloadError(Exception):
    pass


def validate_realtime_payload(data: Dict) -> None:
    required_keys = ['total_targets', 'fruit_counts', 'ripeness_counts']
    if not all(k in data for k in required_keys):
        raise RealtimePayloadError('缺少必要字段')


def build_realtime_summary(data: Dict) -> Dict:
    return {
        'total_targets': data['total_targets'],
        'fruit_counts': data['fruit_counts'],
        'ripeness_counts': data['ripeness_counts'],
    }


def save_realtime_report_file(summary: Dict) -> str:
    report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_filename = f'reports/realtime_report_{uuid.uuid4().hex}.json'
    report_path = os.path.join(settings.MEDIA_ROOT, report_filename)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return report_filename


def create_realtime_history(user, summary: Dict, report_filename: str) -> None:
    DetectionHistory.objects.create(
        user=user,
        detection_type='realtime',
        summary=summary,
        report_file=report_filename,
    )


def save_realtime_report(user, data: Dict) -> Dict:
    validate_realtime_payload(data)
    summary = build_realtime_summary(data)
    report_filename = save_realtime_report_file(summary)
    create_realtime_history(user, summary, report_filename)

    return {
        'status': 'success',
        'message': '报告已保存',
        'report_file': report_filename,
    }
