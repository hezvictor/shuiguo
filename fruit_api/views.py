"""Compatibility export layer for route imports.

Business views are split across modules under fruit_api/views_modules.
"""

from fruit_api.views_modules.auth_views import (  # noqa: F401
    api_login_view,
    api_logout_view,
    change_password,
    csrf_cookie_view,
    get_user_info,
    register_view,
    update_profile,
)
from fruit_api.views_modules.camera_views import (  # noqa: F401
    camera_calibration_capture,
    camera_calibration_run,
    camera_calibration_status,
    camera_device_frame,
    camera_probe,
    camera_measure_current,
    measure_runtime_status,
    camera_start,
    camera_status,
    camera_stop,
    camera_stream,
)
from fruit_api.views_modules.camera_registry_views import (  # noqa: F401
    camera_registry_get,
    camera_registry_scan,
    camera_registry_select,
)
from fruit_api.views_modules.camera_capture_views import (  # noqa: F401
    camera_capture,
    camera_capture_delete,
    camera_capture_list,
    camera_capture_download,
    camera_capture_stage_delete,
    camera_capture_stage_save,
)
from fruit_api.views_modules.console_views import (  # noqa: F401
    console_overview,
    console_recent,
    console_system_status,
)
from fruit_api.views_modules.detect_views import (  # noqa: F401
    create_image_detection_task_view,
    predict_ripeness_by_type,
    predict_view,
    predict_with_ripeness,
    yolo_detect_info,
    yolo_detect_with_boxes,
    yolo_report,
)
from fruit_api.views_modules.diameter_views import (  # noqa: F401
    get_diameter_service,
    measure_distance,
    measure_infer,
    measure_fruit_diameter,
)
from fruit_api.views_modules.history_views import (  # noqa: F401
    DetectionHistoryDetailView,
    DetectionHistoryListView,
)
from fruit_api.views_modules.realtime_views import save_realtime_report  # noqa: F401
from fruit_api.views_modules.realtime_runtime_views import realtime_detect_current_frame  # noqa: F401

__all__ = [
    'register_view',
    'api_login_view',
    'api_logout_view',
    'csrf_cookie_view',
    'update_profile',
    'change_password',
    'get_user_info',
    'camera_device_frame',
    'camera_calibration_capture',
    'camera_calibration_run',
    'camera_calibration_status',
    'camera_registry_get',
    'camera_registry_scan',
    'camera_registry_select',
    'camera_capture',
    'camera_capture_delete',
    'camera_capture_list',
    'camera_capture_download',
    'camera_capture_stage_delete',
    'camera_capture_stage_save',
    'camera_probe',
    'camera_status',
    'camera_start',
    'camera_stop',
    'camera_stream',
    'camera_measure_current',
    'measure_runtime_status',
    'console_overview',
    'console_recent',
    'console_system_status',
    'predict_view',
    'predict_with_ripeness',
    'predict_ripeness_by_type',
    'create_image_detection_task_view',
    'yolo_detect_with_boxes',
    'yolo_detect_info',
    'yolo_report',
    'measure_infer',
    'measure_distance',
    'measure_fruit_diameter',
    'DetectionHistoryListView',
    'DetectionHistoryDetailView',
    'save_realtime_report',
    'realtime_detect_current_frame',
]
