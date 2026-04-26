import base64
import io
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from fruit_api.models import DetectionHistory, VideoProcessingTask
from fruit_api.services.detection.detect_service import InvalidParamError, parse_selected_indices
from fruit_api.services.video.video_service import (
    VideoTaskStateError,
    create_video_task,
    process_video_task,
    progress_payload,
    validate_completed_task,
)


class ErrorPayloadAssertMixin:
    def assert_error_payload(self, response):
        self.assertIn('status', response.data)
        self.assertEqual(response.data['status'], 'error')
        self.assertIn('error', response.data)


class AuthApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='auth_user', password='pass1234', email='u@test.com')

    def test_register_success(self):
        resp = self.client.post('/api/register/', {'username': 'new_user', 'password': 'pass1234', 'email': 'a@b.com'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='new_user').exists())

    def test_register_duplicate_username(self):
        resp = self.client.post('/api/register/', {'username': 'auth_user', 'password': 'pass1234'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_login_invalid_password(self):
        resp = self.client.post('/api/login/', {'username': 'auth_user', 'password': 'wrong'})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_login_success_and_user_info(self):
        resp = self.client.post('/api/login/', {'username': 'auth_user', 'password': 'pass1234'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'success')

        info_resp = self.client.get('/api/user_info/')
        self.assertEqual(info_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(info_resp.data['username'], 'auth_user')

    def test_change_password_success(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/change_password/', {'old_password': 'pass1234', 'new_password': 'newpass123'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))


class DetectionHistoryApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u1', password='pass1234')
        self.other_user = User.objects.create_user(username='u2', password='pass1234')
        self.client.force_authenticate(user=self.user)

    def test_history_supports_detection_type_filter(self):
        DetectionHistory.objects.create(user=self.user, detection_type='image', summary={'k': 1})
        DetectionHistory.objects.create(user=self.user, detection_type='diameter', summary={'k': 2})
        DetectionHistory.objects.create(user=self.other_user, detection_type='diameter', summary={'k': 3})

        resp = self.client.get('/api/detection/history/?detection_type=diameter')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        payload = resp.data
        results = payload.get('results', payload)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['detection_type'], 'diameter')

    def test_history_detail_only_owner_can_access(self):
        row = DetectionHistory.objects.create(user=self.other_user, detection_type='image', summary={'x': 1})
        resp = self.client.get(f'/api/detection/history/{row.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_history_delete_also_removes_report_file(self):
        with tempfile.TemporaryDirectory() as td:
            rel = 'reports/test_report.json'
            abs_path = os.path.join(td, rel)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write('{}')

            row = DetectionHistory.objects.create(
                user=self.user,
                detection_type='image',
                summary={'x': 1},
                report_file=rel,
            )

            with override_settings(MEDIA_ROOT=td):
                resp = self.client.delete(f'/api/detection/history/{row.id}/')

            self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
            self.assertFalse(os.path.exists(abs_path))


class DiameterApiTests(ErrorPayloadAssertMixin, APITestCase):
    PNG_1X1 = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6p2xkAAAAASUVORK5CYII='
    )

    def setUp(self):
        self.user = User.objects.create_user(username='diameter_user', password='pass1234')
        self.client.force_authenticate(user=self.user)

    def _image_file(self, name):
        buffer = io.BytesIO()
        Image.new('RGB', (8, 8), color=(120, 160, 200)).save(buffer, format='PNG')
        return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')

    @patch('fruit_api.views_modules.diameter_views.run_measure_inference')
    @patch('fruit_api.views_modules.diameter_views.apps.get_app_config')
    def test_measure_infer_success(self, mock_get_app_config, mock_run_measure_inference):
        mock_app_cfg = Mock()
        mock_app_cfg.ensure_models_loaded = Mock()
        mock_app_cfg.yolo_model = Mock()
        mock_get_app_config.return_value = mock_app_cfg

        mock_run_measure_inference.return_value = {
            'success': True,
            'message': 'inference ok',
            'inference_id': 'infer-1',
            'disp_npy_path': 'E:\\tmp\\disp.npy',
            'calib_path': 'E:\\tmp\\calib.npz',
            'ckpt_path': 'E:\\tmp\\mix_all.pth',
            'left_image_path': 'E:\\tmp\\left.png',
            'right_image_path': 'E:\\tmp\\right.png',
            'rectified_left_path': 'E:\\tmp\\left_rect.png',
            'rectified_right_path': 'E:\\tmp\\right_rect.png',
            'disp_vis_path': 'E:\\tmp\\disp_color.png',
            'depth_npy_path': None,
            'image_width': 1280,
            'image_height': 720,
            'calib_summary': {'fx': 1.0, 'fy': 1.0, 'cx': 1.0, 'cy': 1.0, 'baseline': 1.0, 'baseline_unit': 'mm', 'q_exists': True},
            'time_ms': 123,
            'detections': [{'index': 0, 'label': 'apple', 'confidence': 0.95, 'bbox': [1, 2, 10, 12]}],
        }

        resp = self.client.post(
            '/api/measure/infer/',
            {
                'left_image': self._image_file('left.png'),
                'right_image': self._image_file('right.png'),
                'save_color': 'true',
            },
            format='multipart',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['success'])
        self.assertEqual(resp.data['inference_id'], 'infer-1')
        mock_run_measure_inference.assert_called_once()

    @patch('fruit_api.views_modules.diameter_views.run_measure_distance')
    def test_measure_distance_targets_success(self, mock_run_measure_distance):
        mock_run_measure_distance.return_value = {
            'success': True,
            'message': 'measure ok',
            'inference_id': 'infer-1',
            'targets': [
                {
                    'index': 0,
                    'label': 'apple',
                    'confidence': 0.95,
                    'bbox': [1, 2, 10, 12],
                    'distance': 66.2,
                    'distance_unit': 'mm',
                    'distance_mm': 66.2,
                    'point1': {'x': 1, 'y': 7, 'disp': 10.2, 'depth_m': 0.3, 'point_3d': {'X': 0.1, 'Y': 0.0, 'Z': 0.3}},
                    'point2': {'x': 10, 'y': 7, 'disp': 10.5, 'depth_m': 0.3, 'point_3d': {'X': 0.2, 'Y': 0.0, 'Z': 0.3}},
                    'status': 'ok',
                }
            ],
            'total_targets': 1,
            'valid_measurements': 1,
            'statistics': {'avg_distance_mm': 66.2, 'min_distance_mm': 66.2, 'max_distance_mm': 66.2},
            'annotated_image_path': 'E:\\tmp\\measure_targets.png',
            'annotated_image_url': '/media/diameter/measure_targets.png',
            'result_json_path': 'E:\\tmp\\measure_targets.json',
            'csv_path': 'E:\\tmp\\measure_targets.csv',
            'calib_path': 'E:\\tmp\\calib.npz',
            'disp_npy_path': 'E:\\tmp\\disp.npy',
            'patch_size': 5,
            'distance_unit': 'mm',
        }

        resp = self.client.post(
            '/api/measure/distance/',
            {
                'inference_id': 'infer-1',
                'measure_all_targets': True,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['success'])
        self.assertEqual(resp.data['valid_measurements'], 1)
        mock_run_measure_distance.assert_called_once()

    def test_measure_infer_missing_right_image(self):
        resp = self.client.post(
            '/api/measure/infer/',
            {
                'left_image': self._image_file('left_only.png'),
            },
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_error_payload(resp)
        self.assertIn('details', resp.data)

    def test_measure_distance_requires_inference_or_disp(self):
        resp = self.client.post('/api/measure/distance/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_error_payload(resp)

    @patch('fruit_api.views_modules.diameter_views.measure_and_save_history')
    @patch('fruit_api.views_modules.diameter_views.apps.get_app_config')
    def test_measure_diameter_legacy_route_still_works(self, mock_get_app_config, mock_measure_and_save_history):
        mock_app_cfg = Mock()
        mock_app_cfg.ensure_models_loaded = Mock()
        mock_app_cfg.yolo_model = Mock()
        mock_get_app_config.return_value = mock_app_cfg

        mock_measure_and_save_history.return_value = {
            'status': 'success',
            'message': '果径测量完成',
            'targets': [],
            'total_targets': 0,
            'valid_measurements': 0,
            'statistics': {'avg_distance_mm': None, 'min_distance_mm': None, 'max_distance_mm': None},
            'visualization_url': None,
            'visualization_file': None,
            'measurement': {'inference_id': 'infer-legacy'},
        }

        resp = self.client.post(
            '/api/measure/diameter/',
            {
                'left_image': self._image_file('left.png'),
                'right_image': self._image_file('right.png'),
            },
            format='multipart',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'success')


class RealtimeApiTests(ErrorPayloadAssertMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rt_user', password='pass1234')
        self.client.force_authenticate(user=self.user)

    def test_save_realtime_report_missing_fields(self):
        resp = self.client.post('/api/realtime/save_report/', {'total_targets': 1}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_error_payload(resp)

    def test_save_realtime_report_success(self):
        payload = {
            'total_targets': 2,
            'fruit_counts': {'apple': 2},
            'ripeness_counts': {'apple': {'ripe': 1, 'unripe': 1}},
        }
        resp = self.client.post('/api/realtime/save_report/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            DetectionHistory.objects.filter(user=self.user, detection_type='realtime').count(),
            1,
        )


class CameraApiTests(ErrorPayloadAssertMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='camera_user', password='pass1234')
        self.client.force_authenticate(user=self.user)

    @patch('fruit_api.views_modules.camera_views.get_stereo_camera_service')
    def test_camera_status_success(self, mock_get_service):
        mock_get_service.return_value.status.return_value = {
            'active': True,
            'config': {'source_mode': 'single', 'split_mode': 'left_right'},
            'last_open_error': None,
            'last_frame_ts': 123.0,
        }

        resp = self.client.get('/api/camera/status/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['active'])
        self.assertEqual(resp.data['stream_url'], '/api/camera/stream/')
        self.assertEqual(resp.data['preview_ws_path'], '/ws/camera/preview/')

    @patch('fruit_api.views_modules.camera_views.get_stereo_camera_service')
    def test_camera_start_success(self, mock_get_service):
        mock_get_service.return_value.open.return_value = {
            'active': True,
            'config': {'source_mode': 'single', 'split_mode': 'left_right'},
            'last_open_error': None,
            'last_frame_ts': 123.0,
        }

        resp = self.client.post(
            '/api/camera/start/',
            {
                'source_mode': 'single',
                'camera_index': 0,
                'split_mode': 'left_right',
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['active'])
        self.assertEqual(resp.data['preview_ws_path'], '/ws/camera/preview/')
        mock_get_service.return_value.open.assert_called_once()

    def test_camera_start_rejects_same_dual_indices(self):
        resp = self.client.post(
            '/api/camera/start/',
            {
                'source_mode': 'dual',
                'left_camera_index': 1,
                'right_camera_index': 1,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_error_payload(resp)

    @patch('fruit_api.views_modules.camera_views.measure_and_save_history')
    @patch('fruit_api.views_modules.camera_views.apps.get_app_config')
    @patch('fruit_api.views_modules.camera_views.get_stereo_camera_service')
    def test_camera_measure_current_success(self, mock_get_service, mock_get_app_config, mock_measure_and_save_history):
        mock_get_service.return_value.read_stereo_frames.return_value = (
            np.zeros((8, 8, 3), dtype=np.uint8),
            np.zeros((8, 8, 3), dtype=np.uint8),
            {'active': True},
        )

        mock_app_cfg = Mock()
        mock_app_cfg.ensure_models_loaded = Mock()
        mock_app_cfg.yolo_model = Mock()
        mock_get_app_config.return_value = mock_app_cfg

        mock_measure_and_save_history.return_value = {
            'status': 'success',
            'message': '果径测量完成',
            'targets': [],
            'total_targets': 0,
            'valid_measurements': 0,
            'statistics': {'avg_distance_mm': None, 'min_distance_mm': None, 'max_distance_mm': None},
            'visualization_url': None,
            'visualization_file': None,
            'measurement': {'inference_id': 'camera-infer-1'},
        }

        resp = self.client.post('/api/camera/measure/', {'conf': 0.25, 'save_vis': True}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'success')
        mock_measure_and_save_history.assert_called_once()


class VideoApiTests(ErrorPayloadAssertMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='video_user', password='pass1234')
        self.client.force_authenticate(user=self.user)

    def test_video_progress_not_found(self):
        resp = self.client.get('/api/video/progress/not-exists/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_error_payload(resp)

    def test_video_cleanup_not_found(self):
        resp = self.client.delete('/api/video/cleanup/not-exists/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_error_payload(resp)


class DetectApiErrorFormatTests(ErrorPayloadAssertMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='detect_user', password='pass1234')
        self.client.force_authenticate(user=self.user)

    def test_predict_requires_image_with_unified_error_schema(self):
        resp = self.client.post('/api/predict/', {}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_error_payload(resp)
        self.assertIn('details', resp.data)


class VideoServiceAdvancedTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='video_service_user', password='pass1234')

    def _video_file(self, name='demo.mp4', size=128):
        return SimpleUploadedFile(name, b'0' * size, content_type='video/mp4')

    @patch('fruit_api.services.video.video_service.VideoProcessingTask.objects.create')
    @patch('fruit_api.services.video.video_service.os.makedirs')
    @patch('fruit_api.services.video.video_service.open')
    @override_settings(MEDIA_ROOT=os.path.join(settings.BASE_DIR, 'test_media'))
    def test_create_video_task_concurrent_submit_generates_unique_ids(
        self,
        _mock_open,
        _mock_makedirs,
        mock_task_create,
    ):
        def fake_create(**kwargs):
            return SimpleNamespace(task_id=kwargs['task_id'])

        mock_task_create.side_effect = fake_create

        def create_one(idx):
            return create_video_task(self._video_file(name=f'v_{idx}.mp4'), process_fps=5, user_id=self.user.id).task_id

        with ThreadPoolExecutor(max_workers=8) as executor:
            task_ids = list(executor.map(create_one, range(24)))

        self.assertEqual(len(task_ids), len(set(task_ids)))
        self.assertEqual(mock_task_create.call_count, 24)

    @patch('fruit_api.services.video.video_service._process_frame', side_effect=lambda frame, *_: frame)
    @patch('fruit_api.services.video.video_service.cv2.VideoWriter')
    @patch('fruit_api.services.video.video_service.cv2.VideoCapture')
    @patch('fruit_api.services.video.video_service.apps.get_app_config')
    @override_settings(MEDIA_ROOT=os.path.join(settings.BASE_DIR, 'test_media'))
    def test_process_video_task_long_video_simulation_updates_progress(
        self,
        mock_get_app_config,
        mock_video_capture,
        mock_video_writer,
        _mock_process_frame,
    ):
        class FakeCapture:
            def __init__(self, total_frames=120):
                self.total_frames = total_frames
                self.cursor = 0

            def isOpened(self):
                return True

            def get(self, prop):
                cv2 = __import__('cv2')
                mapping = {
                    cv2.CAP_PROP_FRAME_COUNT: self.total_frames,
                    cv2.CAP_PROP_FPS: 30.0,
                    cv2.CAP_PROP_FRAME_WIDTH: 640,
                    cv2.CAP_PROP_FRAME_HEIGHT: 480,
                }
                return mapping.get(prop, 0)

            def read(self):
                if self.cursor >= self.total_frames:
                    return False, None
                self.cursor += 1
                return True, SimpleNamespace()

            def release(self):
                return None

        class FakeWriter:
            def write(self, _frame):
                return None

            def release(self):
                return None

        mock_get_app_config.return_value = Mock()
        mock_video_capture.return_value = FakeCapture()
        mock_video_writer.return_value = FakeWriter()

        task = VideoProcessingTask.objects.create(
            task_id='long-video-task',
            user=None,
            original_file_name='long.mp4',
            input_path=os.path.join(settings.MEDIA_ROOT, 'video_input', 'in.mp4'),
            output_path=os.path.join(settings.MEDIA_ROOT, 'video_output', 'out.mp4'),
            process_fps=5,
            status='processing',
        )

        process_video_task(task.task_id)
        task.refresh_from_db()

        self.assertEqual(task.status, 'completed')
        self.assertEqual(task.progress, 100)
        self.assertEqual(task.total_frames, 120)
        self.assertGreater(task.processed_frames, 0)
        self.assertIsInstance(task.report_data, dict)
        self.assertIn('total_targets', task.report_data)


class ServiceUnitTests(SimpleTestCase):
    def test_parse_selected_indices_none(self):
        self.assertIsNone(parse_selected_indices(None))

    def test_parse_selected_indices_invalid_json(self):
        with self.assertRaises(InvalidParamError):
            parse_selected_indices('not-json')

    def test_progress_payload_contains_report(self):
        task = SimpleNamespace(
            task_id='t1',
            original_file_name='a.mp4',
            status='completed',
            progress=100,
            processed_frames=10,
            total_frames=10,
            video_width=1920,
            video_height=1080,
            frame_rate=25,
            message='处理完成',
            report_data={'k': 1},
            report_file='reports/r.json',
        )
        payload = progress_payload(task)
        self.assertIn('report', payload)
        self.assertIn('report_file', payload)

    def test_validate_completed_task_raises_for_processing(self):
        task = SimpleNamespace(status='processing')
        with self.assertRaises(VideoTaskStateError):
            validate_completed_task(task)




