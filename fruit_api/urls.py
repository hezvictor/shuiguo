# fruit_api/urls.py
from django.urls import include, path

from . import views

app_name = 'fruit_api'
# Example ASGI startup:
# daphne -b 0.0.0.0 -p 8000 shuiguo.asgi:application

urlpatterns = [
    # API endpoints
    path(
        'api/',
        include(
            [
                # User
                path('csrf/', views.csrf_cookie_view, name='api_csrf_cookie'),
                path('register/', views.register_view, name='api_register'),
                path('login/', views.api_login_view, name='api_login'),
                path('logout/', views.api_logout_view, name='api_logout'),
                path('user_info/', views.get_user_info, name='user_info'),
                path('update_profile/', views.update_profile, name='update_profile'),
                path('change_password/', views.change_password, name='change_password'),

                # Classification / ripeness
                path('predict/', views.predict_view, name='predict'),
                path('predict_with_ripeness/', views.predict_with_ripeness, name='predict_with_ripeness'),
                path('predict_ripeness_by_type/', views.predict_ripeness_by_type, name='predict_ripeness_by_type'),

                # YOLO detection / report
                path('image-detection/tasks/', views.create_image_detection_task_view, name='image_detection_tasks'),
                path('yolo_detect/', views.yolo_detect_with_boxes, name='yolo_detect'),
                path('yolo_detect_info/', views.yolo_detect_info, name='yolo_detect_info'),
                path('yolo_report/', views.yolo_report, name='yolo_report'),
                path('yolo_detect_with_boxes/', views.yolo_detect_with_boxes, name='yolo_detect_with_boxes'),

                # Diameter measurement
                path('measure/infer/', views.measure_infer, name='measure_infer'),
                path('measure/distance/', views.measure_distance, name='measure_distance'),
                path('measure/diameter/', views.measure_fruit_diameter, name='measure_fruit_diameter'),

                # Stereo camera
                path('camera/status/', views.camera_status, name='camera_status'),
                path('camera/registry/', views.camera_registry_get, name='camera_registry_get'),
                path('camera/registry/scan/', views.camera_registry_scan, name='camera_registry_scan'),
                path('camera/registry/select/', views.camera_registry_select, name='camera_registry_select'),
                path('camera/probe/', views.camera_probe, name='camera_probe'),
                path('camera/device-frame/<int:camera_index>/', views.camera_device_frame, name='camera_device_frame'),
                path('camera/calibration/status/', views.camera_calibration_status, name='camera_calibration_status'),
                path('camera/calibration/capture/', views.camera_calibration_capture, name='camera_calibration_capture'),
                path('camera/calibration/run/', views.camera_calibration_run, name='camera_calibration_run'),
                path('camera/start/', views.camera_start, name='camera_start'),
                path('camera/stop/', views.camera_stop, name='camera_stop'),
                path('camera/stream/', views.camera_stream, name='camera_stream'),
                path('camera/capture/', views.camera_capture, name='camera_capture'),
                path('camera/capture/save/', views.camera_capture_stage_save, name='camera_capture_stage_save'),
                path('camera/captures/', views.camera_capture_list, name='camera_capture_list'),
                path('camera/captures/download/', views.camera_capture_download, name='camera_capture_download'),
                path('camera/captures/<str:record_id>/', views.camera_capture_delete, name='camera_capture_delete'),
                path('camera/measure/', views.camera_measure_current, name='camera_measure_current'),
                path('measure/runtime-status/', views.measure_runtime_status, name='measure_runtime_status'),

                # Console
                path('console/overview/', views.console_overview, name='console_overview'),
                path('console/recent/', views.console_recent, name='console_recent'),
                path('console/system-status/', views.console_system_status, name='console_system_status'),

                # Detection history
                path('detection/history/', views.DetectionHistoryListView.as_view(), name='detection_history'),
                path('detection/history/<int:pk>/', views.DetectionHistoryDetailView.as_view(), name='detection_history_detail'),

                # Realtime report save
                path('realtime/detect/current-frame/', views.realtime_detect_current_frame, name='realtime_detect_current_frame'),
                path('realtime/save_report/', views.save_realtime_report, name='save_realtime_report'),
            ]
        ),
    ),
]
