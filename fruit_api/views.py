"""Compatibility export layer for route imports.

Business views are split across modules under fruit_api/views_modules.
"""

from fruit_api.views_modules.auth_views import (  # noqa: F401
    api_login_view,
    api_logout_view,
    change_password,
    get_user_info,
    home_view,
    login_view,
    logout_view,
    register_view,
    update_profile,
)
from fruit_api.views_modules.camera_views import (  # noqa: F401
    camera_calibration_capture,
    camera_calibration_run,
    camera_calibration_status,
    camera_debug_page,
    camera_probe,
    camera_measure_current,
    measure_runtime_status,
    camera_start,
    camera_status,
    camera_stop,
    camera_stream,
)
from fruit_api.views_modules.console_views import (  # noqa: F401
    console_overview,
    console_recent,
    console_system_status,
)
from fruit_api.views_modules.detect_views import (  # noqa: F401
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
from fruit_api.views_modules.video_views import (  # noqa: F401
    VideoTask,
    process_video_task,
    video_cleanup,
    video_download,
    video_progress,
    video_report,
    video_tasks,
    video_upload,
)

__all__ = [
    'login_view',
    'home_view',
    'logout_view',
    'register_view',
    'api_login_view',
    'api_logout_view',
    'update_profile',
    'change_password',
    'get_user_info',
    'camera_debug_page',
    'camera_calibration_capture',
    'camera_calibration_run',
    'camera_calibration_status',
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
    'yolo_detect_with_boxes',
    'yolo_detect_info',
    'yolo_report',
    'measure_infer',
    'measure_distance',
    'measure_fruit_diameter',
    'DetectionHistoryListView',
    'DetectionHistoryDetailView',
    'VideoTask',
    'process_video_task',
    'video_tasks',
    'video_upload',
    'video_progress',
    'video_download',
    'video_cleanup',
    'video_report',
    'save_realtime_report',
]
