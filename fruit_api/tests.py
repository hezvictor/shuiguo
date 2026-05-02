import base64
import io
import os
import shutil
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_timezone
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
from fruit_api.services.detection.image_batch_service import create_image_detection_task
from fruit_api.services.detection.upload_resolver_service import UploadResolveError, resolve_image_detection_inputs
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

    def test_csrf_cookie_endpoint_sets_cookie(self):
        resp = self.client.get('/api/csrf/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('csrftoken', resp.cookies)

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

    def test_history_list_returns_source_entries_for_image_records(self):
        row = DetectionHistory.objects.create(
            user=self.user,
            detection_type='image',
            summary={'x': 1},
            detail_data={
                'items': [
                    {
                        'item_type': 'image',
                        'display_name': 'apple.png',
                        'original_image': 'image_tasks/task-1/apple.png',
                        'archive_name': None,
                    },
                    {
                        'item_type': 'image',
                        'display_name': 'left.png',
                        'original_image': 'image_tasks/task-1/left.png',
                        'archive_name': 'camera_capture_bundle_20260502_180402.zip',
                    },
                    {
                        'item_type': 'image',
                        'display_name': 'right.png',
                        'original_image': 'image_tasks/task-1/right.png',
                        'archive_name': 'camera_capture_bundle_20260502_180402.zip',
                    },
                ]
            },
        )

        resp = self.client.get('/api/detection/history/?detection_type=image')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        payload = resp.data.get('results', resp.data)
        current = next(item for item in payload if item['id'] == row.id)
        self.assertEqual(
            current['source_entries'],
            [
                {
                    'label': 'apple.png',
                    'kind': 'image',
                    'url': '/media/image_tasks/task-1/apple.png',
                    'item_type': 'image',
                },
                {
                    'label': 'camera_capture_bundle_20260502_180402.zip',
                    'kind': 'archive',
                    'url': None,
                    'item_type': 'image',
                },
            ],
        )

    def test_history_delete_also_removes_report_file(self):
        td = os.path.join(settings.BASE_DIR, 'media', 'test_history_delete')
        shutil.rmtree(td, ignore_errors=True)
        os.makedirs(td, exist_ok=True)
        try:
            rel = 'reports/test_report.json'
            abs_path = os.path.join(td, rel)
            cover_rel = 'image_tasks/task-1/cover.jpg'
            cover_abs = os.path.join(td, cover_rel)
            artifact_rel = 'image_tasks/task-1/report.xlsx'
            artifact_abs = os.path.join(td, artifact_rel)
            task_root_rel = 'image_tasks/task-1'
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            os.makedirs(os.path.dirname(cover_abs), exist_ok=True)
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write('{}')
            with open(cover_abs, 'wb') as f:
                f.write(b'cover')
            with open(artifact_abs, 'wb') as f:
                f.write(b'artifact')

            row = DetectionHistory.objects.create(
                user=self.user,
                detection_type='image',
                summary={'x': 1},
                cover_image=cover_rel,
                report_file=rel,
                artifacts={'excel_report': artifact_rel},
                detail_data={'task_root': task_root_rel},
            )

            with override_settings(MEDIA_ROOT=td):
                resp = self.client.delete(f'/api/detection/history/{row.id}/')

            self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
            self.assertFalse(os.path.exists(abs_path))
            self.assertFalse(os.path.exists(cover_abs))
            self.assertFalse(os.path.exists(artifact_abs))
            self.assertFalse(os.path.exists(os.path.join(td, task_root_rel)))
        finally:
            shutil.rmtree(td, ignore_errors=True)


class ImageDetectionTaskApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='image_task_user', password='pass1234')
        self.client.force_authenticate(user=self.user)

    def _image_file(self, name, color=(120, 160, 200)):
        buffer = io.BytesIO()
        Image.new('RGB', (16, 16), color=color).save(buffer, format='PNG')
        return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')

    def _zip_file(self, name, files):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            for path, content in files.items():
                archive.writestr(path, content)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type='application/zip')

    @patch('fruit_api.views_modules.detect_views.create_image_detection_task')
    @patch('fruit_api.views_modules.detect_views.apps.get_app_config')
    def test_create_image_detection_task_success(self, mock_get_app_config, mock_create_task):
        mock_app_cfg = Mock()
        mock_app_cfg.ensure_models_loaded = Mock()
        mock_get_app_config.return_value = mock_app_cfg

        history = DetectionHistory(
            id=99,
            user=self.user,
            detection_type='image',
            title='图片检测任务',
            status='completed',
            input_count=2,
            summary={'total_targets': 3},
            detail_data={'items': []},
            artifacts={'excel_report': 'image_tasks/task-1/report.xlsx'},
            cover_image='image_tasks/task-1/cover.jpg',
            report_file='image_tasks/task-1/report.xlsx',
        )
        mock_create_task.return_value = history

        resp = self.client.post(
            '/api/image-detection/tasks/',
            {
                'detect_ripeness': 'true',
                'single_inputs': [self._image_file('normal.png')],
                'diameter_inputs': [self._image_file('apple_left.png'), self._image_file('apple_right.png')],
            },
            format='multipart',
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['history_id'], 99)
        self.assertEqual(resp.data['task_status'], 'completed')
        self.assertEqual(resp.data['report_file'], 'image_tasks/task-1/report.xlsx')
        mock_create_task.assert_called_once()

    def test_create_image_detection_task_requires_inputs(self):
        resp = self.client.post(
            '/api/image-detection/tasks/',
            {
                'detect_ripeness': 'false',
            },
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['status'], 'error')

    @patch('fruit_api.views_modules.detect_views.create_image_detection_task')
    @patch('fruit_api.views_modules.detect_views.apps.get_app_config')
    def test_create_image_detection_task_supports_zip_inputs(self, mock_get_app_config, mock_create_task):
        mock_app_cfg = Mock()
        mock_app_cfg.ensure_models_loaded = Mock()
        mock_get_app_config.return_value = mock_app_cfg

        history = DetectionHistory(
            id=100,
            user=self.user,
            detection_type='image',
            title='图片检测任务',
            status='completed',
            input_count=3,
            summary={'total_targets': 3},
            detail_data={'items': []},
            artifacts={'excel_report': 'image_tasks/task-zip/report.xlsx'},
            cover_image='image_tasks/task-zip/cover.jpg',
            report_file='image_tasks/task-zip/report.xlsx',
        )
        mock_create_task.return_value = history

        single_buffer = io.BytesIO()
        Image.new('RGB', (16, 16), color=(123, 100, 90)).save(single_buffer, format='PNG')
        single_content = single_buffer.getvalue()

        diameter_left = io.BytesIO()
        Image.new('RGB', (16, 16), color=(0, 255, 0)).save(diameter_left, format='PNG')
        diameter_right = io.BytesIO()
        Image.new('RGB', (16, 16), color=(0, 0, 255)).save(diameter_right, format='PNG')

        resp = self.client.post(
            '/api/image-detection/tasks/',
            {
                'detect_ripeness': 'true',
                'single_inputs': [
                    self._zip_file(
                        'single_batch.zip',
                        {
                            'single_batch/a.png': single_content,
                            'single_batch/sub/b.png': single_content,
                        },
                    )
                ],
                'diameter_inputs': [
                    self._zip_file(
                        'diameter_batch.zip',
                        {
                            'diameter_batch/group1/apple_left.png': diameter_left.getvalue(),
                            'diameter_batch/group1/apple_right.png': diameter_right.getvalue(),
                        },
                    )
                ],
            },
            format='multipart',
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        mock_create_task.assert_called_once()
        kwargs = mock_create_task.call_args.kwargs
        self.assertEqual(len(kwargs['standard_images']), 2)
        self.assertEqual(len(kwargs['diameter_groups']), 1)
        self.assertTrue(kwargs['options']['detect_ripeness'])
        self.assertTrue(kwargs['options']['detect_diameter'])

    def test_create_image_detection_task_rejects_direct_diameter_file_without_side_name(self):
        resp = self.client.post(
            '/api/image-detection/tasks/',
            {
                'diameter_inputs': [self._image_file('apple.png')],
            },
            format='multipart',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['status'], 'error')
        self.assertIn('left', resp.data['error'].lower())

    def test_create_image_detection_task_rejects_invalid_diameter_zip_structure(self):
        image_content = self._image_file('tmp.png').read()
        resp = self.client.post(
            '/api/image-detection/tasks/',
            {
                'diameter_inputs': [
                    self._zip_file(
                        'bad_diameter.zip',
                        {
                            'bad_diameter/apple_left.png': image_content,
                            'bad_diameter/apple_right.png': image_content,
                        },
                    )
                ],
            },
            format='multipart',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['status'], 'error')
        self.assertIn('一级目录', resp.data['error'])

    def test_create_image_detection_task_rejects_diameter_zip_missing_right_image(self):
        image_content = self._image_file('tmp.png').read()
        resp = self.client.post(
            '/api/image-detection/tasks/',
            {
                'diameter_inputs': [
                    self._zip_file(
                        'missing_right.zip',
                        {
                            'missing_right/group1/apple_left.png': image_content,
                            'missing_right/group1/readme.txt': b'ignore',
                        },
                    )
                ],
            },
            format='multipart',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['status'], 'error')
        self.assertIn('只能包含图片文件', resp.data['error'])

    def test_create_image_detection_task_service_supports_standard_image_without_diameter(self):
        media_root = os.path.join(settings.BASE_DIR, 'media', 'test_image_task_service')
        shutil.rmtree(media_root, ignore_errors=True)
        os.makedirs(media_root, exist_ok=True)
        try:
            with override_settings(MEDIA_ROOT=media_root):
                with patch(
                    'fruit_api.services.detection.image_batch_service.yolo_targets',
                    return_value=[{'bbox': [1, 1, 12, 12], 'label': 'fruit', 'confidence': 0.91}],
                ), patch(
                    'fruit_api.services.detection.image_batch_service.classify_fruit_crop',
                    return_value={'predicted_class': 'apple', 'confidence': 0.87},
                ), patch(
                    'fruit_api.services.detection.image_batch_service.classify_ripeness_for_fruit_crop',
                    return_value={'predicted_class': 'ripe', 'confidence': 0.74},
                ):
                    history = create_image_detection_task(
                        user=self.user,
                        standard_images=[
                            {
                                'display_name': 'single.png',
                                'file_name': 'single.png',
                                'content': self._image_file('single.png').read(),
                                'input_source': 'direct_upload',
                                'archive_name': None,
                                'archive_path': None,
                            }
                        ],
                        diameter_groups=[],
                        options={
                            'detect_classification': True,
                            'detect_ripeness': True,
                            'detect_diameter': False,
                        },
                        app_config=Mock(),
                    )
        finally:
            shutil.rmtree(media_root, ignore_errors=True)

        self.assertEqual(history.status, 'completed')
        self.assertEqual(history.summary['total_targets'], 1)
        self.assertTrue(history.report_file.endswith('.xlsx'))
        self.assertEqual(history.detail_data['items'][0]['targets'][0]['diameter'], None)

    @patch('fruit_api.views_modules.detect_views.apps.get_app_config')
    def test_create_image_detection_task_zip_inputs_end_to_end(self, mock_get_app_config):
        mock_app_cfg = Mock()
        mock_app_cfg.ensure_models_loaded = Mock()
        mock_app_cfg.yolo_model = Mock()
        mock_get_app_config.return_value = mock_app_cfg

        measure_service = Mock()
        measure_service.run_full_measurement.return_value = {
            'status': 'success',
            'message': '果径测量完成',
            'measurement': {
                'targets': [
                    {
                        'label': 'fruit',
                        'confidence': 0.95,
                        'bbox': [1, 1, 10, 10],
                        'distance': 66.2,
                        'distance_unit': 'mm',
                        'distance_mm': 66.2,
                        'point1': {'x': 1, 'y': 5},
                        'point2': {'x': 10, 'y': 5},
                        'status': 'ok',
                    }
                ],
                'result_json_path': None,
                'csv_path': None,
            },
            'inference': {'rectified_left_path': None},
            'targets': [
                {
                    'label': 'fruit',
                    'confidence': 0.95,
                    'bbox': [1, 1, 10, 10],
                    'distance': 66.2,
                    'distance_unit': 'mm',
                    'distance_mm': 66.2,
                    'point1': {'x': 1, 'y': 5},
                    'point2': {'x': 10, 'y': 5},
                    'status': 'ok',
                }
            ],
            'total_targets': 1,
            'valid_measurements': 1,
            'statistics': {'avg_distance_mm': 66.2, 'min_distance_mm': 66.2, 'max_distance_mm': 66.2},
            'visualization_file': None,
        }

        media_root = os.path.join(settings.BASE_DIR, 'media', 'test_image_task_api_e2e')
        shutil.rmtree(media_root, ignore_errors=True)
        os.makedirs(media_root, exist_ok=True)
        try:
            with override_settings(MEDIA_ROOT=media_root):
                with patch(
                    'fruit_api.services.detection.image_batch_service.yolo_targets',
                    return_value=[{'bbox': [1, 1, 12, 12], 'label': 'fruit', 'confidence': 0.91}],
                ), patch(
                    'fruit_api.services.detection.image_batch_service.classify_fruit_crop',
                    return_value={'predicted_class': 'apple', 'confidence': 0.87},
                ), patch(
                    'fruit_api.services.detection.image_batch_service.classify_ripeness_for_fruit_crop',
                    return_value={'predicted_class': 'ripe', 'confidence': 0.74},
                ), patch(
                    'fruit_api.services.detection.image_batch_service.get_diameter_service',
                    return_value=measure_service,
                ):
                    image_content = self._image_file('tmp.png').read()
                    resp = self.client.post(
                        '/api/image-detection/tasks/',
                        {
                            'detect_ripeness': 'true',
                            'single_inputs': [
                                self._zip_file(
                                    'single_batch.zip',
                                    {
                                        'single_batch/a.png': image_content,
                                    },
                                )
                            ],
                            'diameter_inputs': [
                                self._zip_file(
                                    'diameter_batch.zip',
                                    {
                                        'diameter_batch/group1/apple_left.png': image_content,
                                        'diameter_batch/group1/apple_right.png': image_content,
                                    },
                                )
                            ],
                        },
                        format='multipart',
                    )

            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
            history = DetectionHistory.objects.get(id=resp.data['history_id'])
            self.assertEqual(history.status, 'completed')
            self.assertEqual(history.input_count, 2)
            self.assertEqual(len(history.detail_data['items']), 2)
            self.assertTrue(history.report_file.endswith('.xlsx'))
        finally:
            shutil.rmtree(media_root, ignore_errors=True)


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

    @patch('fruit_api.views_modules.camera_views.probe_camera_indices')
    def test_camera_probe_returns_device_names(self, mock_probe):
        mock_probe.return_value = {
            'backend': 'CAP_DSHOW',
            'max_index': 4,
            'results': [
                {
                    'camera_index': 1,
                    'opened': True,
                    'device_name': 'USB 2.0 Camera',
                    'device_name_inferred': True,
                },
                {
                    'camera_index': 2,
                    'opened': True,
                    'device_name': 'USB 2.0 Camera',
                    'device_name_inferred': True,
                },
            ],
            'pair_results': [
                {
                    'left_camera_index': 1,
                    'right_camera_index': 2,
                    'simultaneous_ok': True,
                    'left_device_name': 'USB 2.0 Camera',
                    'right_device_name': 'USB 2.0 Camera',
                }
            ],
            'device_catalog': [
                {'device_name': 'USB 2.0 Camera', 'device_status': 'OK'},
                {'device_name': 'USB 2.0 Camera', 'device_status': 'OK'},
            ],
            'opened_count': 2,
            'recommended_dual_pair': [1, 2],
        }

        resp = self.client.get('/api/camera/probe/?max_index=4')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['results'][0]['device_name'], 'USB 2.0 Camera')
        self.assertEqual(resp.data['pair_results'][0]['left_device_name'], 'USB 2.0 Camera')

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

    @patch('fruit_api.views_modules.camera_views.create_image_detection_task_from_camera_measurement')
    @patch('fruit_api.views_modules.camera_views.measure_and_save_history')
    @patch('fruit_api.views_modules.camera_views.apps.get_app_config')
    @patch('fruit_api.views_modules.camera_views.get_stereo_camera_service')
    def test_camera_measure_current_can_link_image_task(
        self,
        mock_get_service,
        mock_get_app_config,
        mock_measure_and_save_history,
        mock_create_image_task,
    ):
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
            'statistics': {},
            'visualization_url': None,
            'visualization_file': None,
            'measurement': {'inference_id': 'camera-infer-2'},
            'inference': {'rectified_left_path': None},
        }
        mock_create_image_task.return_value = DetectionHistory(
            id=123,
            user=self.user,
            detection_type='image',
            title='双目实时检测任务',
            report_file='image_tasks/camera/report.xlsx',
            cover_image='image_tasks/camera/cover.png',
        )

        resp = self.client.post(
            '/api/camera/measure/',
            {
                'conf': 0.25,
                'save_vis': True,
                'save_as_image_task': True,
                'detect_classification': True,
                'detect_ripeness': False,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['linked_image_history']['id'], 123)
        mock_create_image_task.assert_called_once()

    @patch('fruit_api.views_modules.camera_registry_views.get_camera_registry_service')
    def test_camera_registry_get_success(self, mock_get_registry_service):
        mock_get_registry_service.return_value.snapshot.return_value = {
            'selection': {'single_camera_index': 0},
            'last_scan': {'results': []},
            'suggested_intervals': {'single_interval_ms': 1500, 'dual_interval_ms': 5000},
        }

        resp = self.client.get('/api/camera/registry/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['selection']['single_camera_index'], 0)

    @patch('fruit_api.views_modules.camera_registry_views.get_camera_registry_service')
    @patch('fruit_api.views_modules.camera_registry_views.probe_camera_indices')
    def test_camera_registry_scan_success(self, mock_probe_camera_indices, mock_get_registry_service):
        mock_probe_camera_indices.return_value = {
            'backend': 'CAP_DSHOW',
            'max_index': 8,
            'results': [{'camera_index': 0, 'opened': True}],
            'pair_results': [],
            'device_catalog': [],
            'opened_count': 1,
            'recommended_dual_pair': None,
        }
        mock_get_registry_service.return_value.update_scan.return_value = {
            'selection': {'single_camera_index': 0},
            'last_scan': {'results': [{'camera_index': 0, 'opened': True}]},
            'suggested_intervals': {'single_interval_ms': 1500, 'dual_interval_ms': 5000},
        }

        resp = self.client.post('/api/camera/registry/scan/', {'max_index': 8}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['selection']['single_camera_index'], 0)
        mock_probe_camera_indices.assert_called_once()

    @patch('fruit_api.views_modules.camera_registry_views.get_camera_registry_service')
    def test_camera_registry_select_success(self, mock_get_registry_service):
        mock_get_registry_service.return_value.update_selection.return_value = {
            'selection': {
                'single_camera_index': 1,
                'dual_left_camera_index': 1,
                'dual_right_camera_index': 2,
                'preview_camera_indices': [1, 2],
            },
            'last_scan': {'results': []},
            'suggested_intervals': {'single_interval_ms': 1500, 'dual_interval_ms': 5000},
        }

        resp = self.client.post(
            '/api/camera/registry/select/',
            {
                'single_camera_index': 1,
                'dual_left_camera_index': 1,
                'dual_right_camera_index': 2,
                'preview_camera_indices': [1, 2],
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['selection']['preview_camera_indices'], [1, 2])

    @patch('fruit_api.views_modules.camera_capture_views.get_camera_capture_service')
    def test_camera_capture_success(self, mock_get_capture_service):
        mock_get_capture_service.return_value.capture.return_value = {
            'persisted': True,
            'records': [
                {
                    'id': 'cap-1',
                    'capture_mode': 'single',
                    'files': [{'file_url': '/media/camera_captures/single/test.jpg'}],
                }
            ],
            'staged_groups': [],
        }

        resp = self.client.post('/api/camera/capture/', {'camera_indices': [0]}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['records'][0]['id'], 'cap-1')

    @patch('fruit_api.views_modules.camera_capture_views.get_camera_capture_service')
    def test_camera_capture_stage_success(self, mock_get_capture_service):
        mock_get_capture_service.return_value.capture.return_value = {
            'persisted': False,
            'records': [],
            'staged_groups': [
                {
                    'stage_id': 'stage-1',
                    'capture_mode': 'dual',
                    'files': [{'role': 'left', 'file_name': 'left.jpg'}, {'role': 'right', 'file_name': 'right.jpg'}],
                }
            ],
        }

        resp = self.client.post('/api/camera/capture/', {'camera_indices': [0, 1], 'persist': False}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['persisted'])
        self.assertEqual(resp.data['staged_groups'][0]['stage_id'], 'stage-1')

    @patch('fruit_api.views_modules.camera_capture_views.get_camera_capture_service')
    def test_camera_capture_stage_save_returns_bundle_record(self, mock_get_capture_service):
        mock_get_capture_service.return_value.save_staged.return_value = {
            'id': 'bundle-1',
            'capture_mode': 'bundle',
            'group_count': 3,
            'archive_name': 'camera_capture_bundle_20260502_160000.zip',
            'archive_file_url': '/media/camera_captures/bundles/20260502/camera_capture_bundle_20260502_160000.zip',
        }

        resp = self.client.post('/api/camera/capture/save/', {'stage_ids': ['s1', 's2', 's3']}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['record']['capture_mode'], 'bundle')
        self.assertEqual(resp.data['record']['group_count'], 3)

    @patch('fruit_api.views_modules.camera_capture_views.get_camera_capture_service')
    def test_camera_capture_delete_success(self, mock_get_capture_service):
        resp = self.client.delete('/api/camera/captures/record-1/')

        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        mock_get_capture_service.return_value.delete_record.assert_called_once_with(
            user_id=self.user.id,
            record_id='record-1',
        )

    @patch('fruit_api.views_modules.camera_capture_views.get_camera_capture_service')
    def test_camera_capture_download_returns_zip(self, mock_get_capture_service):
        mock_get_capture_service.return_value.build_zip_bytes.return_value = {
            'file_name': 'captures.zip',
            'content': b'zip-content',
            'record_count': 2,
        }

        resp = self.client.post('/api/camera/captures/download/', {'record_ids': ['a', 'b']}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/zip')


class RealtimeRuntimeApiTests(ErrorPayloadAssertMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='realtime_rt_user', password='pass1234')
        self.client.force_authenticate(user=self.user)

    @patch('fruit_api.views_modules.realtime_runtime_views.run_single_camera_realtime_detection')
    @patch('fruit_api.views_modules.realtime_runtime_views.apps.get_app_config')
    def test_realtime_detect_current_frame_single_success(self, mock_get_app_config, mock_run_single):
        mock_app_cfg = Mock()
        mock_app_cfg.ensure_models_loaded = Mock()
        mock_get_app_config.return_value = mock_app_cfg
        mock_run_single.return_value = {
            'status': 'success',
            'mode': 'single',
            'camera_index': 0,
            'targets': [],
            'summary': {'total_targets': 0, 'fruit_counts': {}, 'ripeness_counts': {}},
            'annotated_image_url': '/media/realtime_frames/one.jpg',
            'suggested_interval_ms': 1500,
        }

        resp = self.client.post('/api/realtime/detect/current-frame/', {'mode': 'single'}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['mode'], 'single')
        mock_run_single.assert_called_once()

    @patch('fruit_api.views_modules.realtime_runtime_views.run_single_preview_frame_realtime_detection')
    @patch('fruit_api.views_modules.realtime_runtime_views.run_single_camera_realtime_detection')
    @patch('fruit_api.views_modules.realtime_runtime_views.apps.get_app_config')
    def test_realtime_detect_current_frame_single_uses_preview_frame_when_provided(
        self,
        mock_get_app_config,
        mock_run_single,
        mock_run_single_preview,
    ):
        mock_app_cfg = Mock()
        mock_app_cfg.ensure_models_loaded = Mock()
        mock_get_app_config.return_value = mock_app_cfg
        mock_run_single_preview.return_value = {
            'status': 'success',
            'mode': 'single',
            'camera_index': 2,
            'targets': [],
            'summary': {'total_targets': 0, 'fruit_counts': {}, 'ripeness_counts': {}},
            'annotated_image_url': '/media/realtime_frames/preview.jpg',
            'suggested_interval_ms': 1500,
            'frame_source': 'preview',
        }

        resp = self.client.post(
            '/api/realtime/detect/current-frame/',
            {
                'mode': 'single',
                'camera_index': 2,
                'frame_data_url': 'data:image/jpeg;base64,ZmFrZQ==',
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['frame_source'], 'preview')
        mock_run_single_preview.assert_called_once()
        mock_run_single.assert_not_called()

    @patch('fruit_api.views_modules.realtime_runtime_views.run_dual_camera_realtime_detection')
    @patch('fruit_api.views_modules.realtime_runtime_views.apps.get_app_config')
    def test_realtime_detect_current_frame_dual_success(self, mock_get_app_config, mock_run_dual):
        mock_app_cfg = Mock()
        mock_app_cfg.ensure_models_loaded = Mock()
        mock_get_app_config.return_value = mock_app_cfg
        mock_run_dual.return_value = {
            'status': 'success',
            'mode': 'dual',
            'left_camera_index': 1,
            'right_camera_index': 2,
            'targets': [],
            'summary': {'total_targets': 0, 'valid_measurements': 0, 'fruit_counts': {}, 'ripeness_counts': {}, 'statistics': {}},
            'annotated_image_url': '/media/diameter_tmp/dual.jpg',
            'suggested_interval_ms': 5000,
        }

        resp = self.client.post('/api/realtime/detect/current-frame/', {'mode': 'dual'}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['mode'], 'dual')
        mock_run_dual.assert_called_once()

    @patch('fruit_api.views_modules.realtime_runtime_views.run_hybrid_camera_realtime_detection')
    @patch('fruit_api.views_modules.realtime_runtime_views.apps.get_app_config')
    def test_realtime_detect_current_frame_hybrid_success(self, mock_get_app_config, mock_run_hybrid):
        mock_app_cfg = Mock()
        mock_app_cfg.ensure_models_loaded = Mock()
        mock_get_app_config.return_value = mock_app_cfg
        mock_run_hybrid.return_value = {
            'status': 'success',
            'mode': 'hybrid',
            'camera_index': 0,
            'left_camera_index': 1,
            'right_camera_index': 2,
            'targets': [],
            'summary': {
                'total_targets': 0,
                'valid_measurements': 0,
                'fruit_counts': {},
                'ripeness_counts': {},
                'statistics': {},
            },
            'annotated_image_url': '/media/realtime_frames/hybrid.jpg',
            'suggested_interval_ms': 5000,
        }

        resp = self.client.post(
            '/api/realtime/detect/current-frame/',
            {
                'mode': 'hybrid',
                'detect_classification': True,
                'detect_diameter': True,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['mode'], 'hybrid')
        mock_run_hybrid.assert_called_once()

    def test_realtime_detect_current_frame_single_requires_classification(self):
        resp = self.client.post(
            '/api/realtime/detect/current-frame/',
            {
                'mode': 'single',
                'detect_classification': False,
                'detect_ripeness': False,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_error_payload(resp)

    def test_realtime_detect_current_frame_hybrid_requires_classification(self):
        resp = self.client.post(
            '/api/realtime/detect/current-frame/',
            {
                'mode': 'hybrid',
                'detect_classification': False,
                'detect_ripeness': False,
                'detect_diameter': True,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_error_payload(resp)

    @patch('fruit_api.views_modules.realtime_runtime_views.run_dual_camera_realtime_detection')
    @patch('fruit_api.views_modules.realtime_runtime_views.apps.get_app_config')
    def test_realtime_detect_current_frame_dual_forces_diameter(self, mock_get_app_config, mock_run_dual):
        mock_app_cfg = Mock()
        mock_app_cfg.ensure_models_loaded = Mock()
        mock_get_app_config.return_value = mock_app_cfg
        mock_run_dual.return_value = {
            'status': 'success',
            'mode': 'dual',
            'left_camera_index': 1,
            'right_camera_index': 2,
            'targets': [],
            'summary': {'total_targets': 0, 'valid_measurements': 0, 'fruit_counts': {}, 'ripeness_counts': {}, 'statistics': {}},
            'annotated_image_url': '/media/diameter_tmp/dual.jpg',
            'suggested_interval_ms': 5000,
        }

        resp = self.client.post(
            '/api/realtime/detect/current-frame/',
            {
                'mode': 'dual',
                'detect_classification': False,
                'detect_diameter': False,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_run_dual.assert_called_once()


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


class ConsoleApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='console_user', password='pass1234')
        self.other_user = User.objects.create_user(username='console_other', password='pass1234')
        self.client.force_authenticate(user=self.user)

    def _create_history(self, *, user=None, detection_type='image', summary=None, created_at=None, report_file=None):
        row = DetectionHistory.objects.create(
            user=user or self.user,
            detection_type=detection_type,
            summary=summary or {},
            report_file=report_file,
        )
        if created_at is not None:
            DetectionHistory.objects.filter(pk=row.pk).update(created_at=created_at)
            row.refresh_from_db()
        return row

    def _create_video_task(self, *, user=None, task_id='task-1', status_name='processing', created_at=None, updated_at=None):
        task = VideoProcessingTask.objects.create(
            task_id=task_id,
            user=user or self.user,
            original_file_name=f'{task_id}.mp4',
            input_path=f'E:\\tmp\\{task_id}_input.mp4',
            output_path=f'E:\\tmp\\{task_id}_output.mp4',
            process_fps=5,
            status=status_name,
            progress=100 if status_name == 'completed' else 20,
            processed_frames=12,
            total_frames=60,
            frame_rate=25.0,
            video_width=1920,
            video_height=1080,
            message='ok',
        )
        if created_at is not None:
            updated_at = updated_at or created_at
            VideoProcessingTask.objects.filter(pk=task.pk).update(created_at=created_at, updated_at=updated_at)
            task.refresh_from_db()
        return task

    def test_console_overview_uses_requested_timezone_for_custom_range(self):
        before_range = datetime(2026, 4, 26, 15, 59, 59, tzinfo=dt_timezone.utc)
        start_of_day = datetime(2026, 4, 26, 16, 0, 0, tzinfo=dt_timezone.utc)
        end_of_day = datetime(2026, 4, 27, 15, 59, 59, tzinfo=dt_timezone.utc)
        after_range = datetime(2026, 4, 27, 16, 0, 0, tzinfo=dt_timezone.utc)

        self._create_history(
            detection_type='image',
            created_at=before_range,
            summary={'total_targets': 99, 'fruit_counts': {'apple': 99}},
        )
        self._create_history(
            detection_type='image',
            created_at=start_of_day,
            summary={
                'total_targets': 3,
                'fruit_counts': {'apple': 2, 'banana': 1},
                'ripeness_counts': {'banana': {'ripe': 1}},
            },
            report_file='reports/image.json',
        )
        self._create_history(
            detection_type='diameter',
            created_at=end_of_day,
            summary={
                'total_targets': 4,
                'valid_measurements': 2,
                'statistics': {
                    'avg_diameter_mm': 60.0,
                    'min_diameter_mm': 55.0,
                    'max_diameter_mm': 66.0,
                },
            },
            report_file='diameter/result.png',
        )
        self._create_history(
            user=self.other_user,
            detection_type='video',
            created_at=start_of_day,
            summary={'total_targets': 77},
        )
        self._create_history(
            detection_type='realtime',
            created_at=after_range,
            summary={'total_targets': 88},
        )

        self._create_video_task(task_id='task-completed', status_name='completed', created_at=start_of_day)
        self._create_video_task(task_id='task-processing', status_name='processing', created_at=end_of_day)
        self._create_video_task(user=self.other_user, task_id='task-other', status_name='error', created_at=start_of_day)

        resp = self.client.get(
            '/api/console/overview/?range_type=custom&start_date=2026-04-27&end_date=2026-04-27&timezone=Asia/Shanghai'
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['summary_cards']['detection_count'], 2)
        self.assertEqual(resp.data['summary_cards']['total_targets'], 7)
        self.assertEqual(resp.data['summary_cards']['image_detection_count'], 1)
        self.assertEqual(resp.data['summary_cards']['diameter_detection_count'], 1)
        self.assertEqual(resp.data['summary_cards']['valid_diameter_measurements'], 2)
        self.assertEqual(resp.data['summary_cards']['avg_targets_per_record'], 3.5)
        self.assertEqual(resp.data['trends']['daily_detection_trend'][0]['count'], 2)
        self.assertEqual(resp.data['trends']['daily_target_trend'][0]['count'], 7)
        self.assertEqual(resp.data['trends']['daily_type_trend'][0]['image'], 1)
        self.assertEqual(resp.data['trends']['daily_type_trend'][0]['diameter'], 1)
        self.assertEqual(resp.data['trends']['daily_avg_diameter_trend'][0]['avg_diameter_mm'], 60.0)
        self.assertEqual(resp.data['analysis']['fruit_ranking'][0], {'fruit': 'apple', 'count': 2})
        self.assertEqual(resp.data['analysis']['ripeness_distribution'][0], {'fruit': 'banana', 'ripeness': 'ripe', 'count': 1})
        self.assertEqual(resp.data['diameter_analysis']['measure_count'], 1)
        self.assertEqual(resp.data['diameter_analysis']['total_targets'], 4)
        self.assertEqual(resp.data['diameter_analysis']['valid_measurements'], 2)
        self.assertEqual(resp.data['diameter_analysis']['success_rate'], 50.0)
        self.assertEqual(resp.data['diameter_analysis']['avg_diameter_mm'], 60.0)
        self.assertEqual(resp.data['diameter_analysis']['min_diameter_mm'], 55.0)
        self.assertEqual(resp.data['diameter_analysis']['max_diameter_mm'], 66.0)
        self.assertEqual(resp.data['video_task_summary']['total'], 2)
        self.assertEqual(resp.data['video_task_summary']['completed'], 1)
        self.assertEqual(resp.data['video_task_summary']['processing'], 1)

    def test_console_recent_returns_latest_items(self):
        base_time = datetime(2026, 4, 27, 8, 0, 0, tzinfo=dt_timezone.utc)
        for index in range(12):
            created_at = base_time + timedelta(minutes=index)
            self._create_history(
                detection_type='diameter' if index % 2 else 'image',
                created_at=created_at,
                summary={'total_targets': index + 1},
                report_file=f'reports/{index}.json',
            )

        for index in range(6):
            created_at = base_time + timedelta(minutes=index)
            self._create_video_task(
                task_id=f'task-{index}',
                status_name='completed' if index % 2 == 0 else 'processing',
                created_at=created_at,
                updated_at=created_at + timedelta(minutes=30),
            )

        resp = self.client.get(
            '/api/console/recent/?range_type=custom&start_date=2026-04-27&end_date=2026-04-28&timezone=UTC'
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['recent_histories']), 10)
        self.assertEqual(len(resp.data['recent_video_tasks']), 5)
        self.assertEqual(resp.data['recent_histories'][0]['summary']['total_targets'], 12)
        self.assertEqual(resp.data['recent_video_tasks'][0]['task_id'], 'task-5')

    @patch('fruit_api.services.console_service.get_stereo_calibration_service')
    @patch('fruit_api.services.console_service.get_measure_runtime_status')
    @patch('fruit_api.services.console_service.get_stereo_camera_service')
    def test_console_system_status_aggregates_existing_services(
        self,
        mock_get_camera_service,
        mock_get_runtime_status,
        mock_get_calibration_service,
    ):
        mock_get_camera_service.return_value.status.return_value = {
            'active': True,
            'config': {'source_mode': 'single', 'camera_index': 0},
            'last_open_error': None,
            'last_frame_ts': 123.0,
            'consecutive_failures': 0,
        }
        mock_get_runtime_status.return_value = {
            'preferred_device': 'auto',
            'device_type': 'cuda',
            'cuda_available': True,
            'model_loaded': True,
        }
        mock_get_calibration_service.return_value.session_status.return_value = {
            'session_id': '20260427_083000',
            'pair_count': 12,
            'pairs': [],
            'result': {'used_pairs': 12},
        }

        resp = self.client.get('/api/console/system-status/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['backend_health']['status'], 'ok')
        self.assertTrue(resp.data['camera_status']['active'])
        self.assertEqual(resp.data['camera_status']['stream_url'], '/api/camera/stream/')
        self.assertEqual(resp.data['measure_runtime_status']['device_type'], 'cuda')
        self.assertIn('calib_path', resp.data['measure_runtime_status'])
        self.assertEqual(resp.data['calibration_status']['session_id'], '20260427_083000')

    def test_console_overview_rejects_invalid_detection_type(self):
        resp = self.client.get('/api/console/overview/?detection_type=invalid')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['status'], 'error')


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
    def _image_bytes(self, color=(120, 160, 200)):
        buffer = io.BytesIO()
        Image.new('RGB', (8, 8), color=color).save(buffer, format='PNG')
        return buffer.getvalue()

    def _upload(self, name, content, content_type='image/png'):
        return SimpleUploadedFile(name, content, content_type=content_type)

    def _zip_upload(self, name, files):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            for path, content in files.items():
                archive.writestr(path, content)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type='application/zip')

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

    @patch('fruit_api.services.camera.stereo_camera_service._list_windows_camera_devices')
    @patch('fruit_api.services.camera.stereo_camera_service._require_cv2')
    def test_probe_camera_indices_enriches_device_names(self, mock_require_cv2, mock_list_devices):
        class FakeCapture:
            def __init__(self, index, _backend):
                self.index = index

            def isOpened(self):
                return self.index in {1, 2}

            def read(self):
                if self.index in {1, 2}:
                    return True, np.zeros((480, 640, 3), dtype=np.uint8)
                return False, None

            def get(self, _prop):
                return 30.0

            def release(self):
                return None

        mock_require_cv2.return_value = SimpleNamespace(
            CAP_ANY=0,
            CAP_PROP_FPS=5,
            VideoCapture=lambda index, backend: FakeCapture(index, backend),
        )
        mock_list_devices.return_value = [
            {'device_name': 'USB 2.0 Camera A', 'device_status': 'OK'},
            {'device_name': 'USB 2.0 Camera B', 'device_status': 'OK'},
        ]

        from fruit_api.services.camera.stereo_camera_service import probe_camera_indices

        payload = probe_camera_indices(max_index=4, backend='CAP_ANY')

        opened = [item for item in payload['results'] if item['opened']]
        self.assertEqual(opened[0]['device_name'], 'USB 2.0 Camera A')
        self.assertEqual(opened[1]['device_name'], 'USB 2.0 Camera B')
        self.assertEqual(payload['pair_results'][0]['left_device_name'], 'USB 2.0 Camera A')

    @patch('fruit_api.services.camera.stereo_camera_service._list_windows_camera_devices')
    @patch('fruit_api.services.camera.stereo_camera_service._require_cv2')
    def test_probe_camera_indices_avoids_pairwise_camera_reopen(self, mock_require_cv2, mock_list_devices):
        constructed = []

        class FakeCapture:
            def __init__(self, index, backend):
                self.index = index
                self.backend = backend
                constructed.append((index, backend))

            def isOpened(self):
                return self.index in {0, 1, 2}

            def read(self):
                return True, np.ones((480, 640, 3), dtype=np.uint8)

            def get(self, _prop):
                return 30.0

            def set(self, *_args):
                return True

            def release(self):
                return None

        mock_require_cv2.return_value = SimpleNamespace(
            CAP_ANY=0,
            CAP_MSMF=1,
            CAP_DSHOW=2,
            CAP_PROP_FPS=5,
            CAP_PROP_FRAME_WIDTH=3,
            CAP_PROP_FRAME_HEIGHT=4,
            CAP_PROP_BUFFERSIZE=38,
            VideoCapture=lambda index, backend: FakeCapture(index, backend),
        )
        mock_list_devices.return_value = []

        from fruit_api.services.camera.stereo_camera_service import probe_camera_indices

        payload = probe_camera_indices(max_index=3, backend='CAP_ANY')

        self.assertEqual(len(constructed), 3)
        self.assertEqual(len(payload['pair_results']), 3)
        self.assertTrue(all(item['validation_mode'] == 'individual_probe' for item in payload['pair_results']))

    @patch('fruit_api.services.detection.realtime_pipeline_service._run_dual_realtime_detection_from_frames')
    @patch('fruit_api.services.detection.realtime_pipeline_service.capture_dual_camera_frames')
    @patch('fruit_api.services.detection.realtime_pipeline_service.get_cached_preview_frame_snapshot')
    @patch('fruit_api.services.detection.realtime_pipeline_service.get_camera_registry_service')
    def test_run_dual_camera_realtime_detection_reuses_cached_preview_frames(
        self,
        mock_get_registry_service,
        mock_get_cached_preview_frame_snapshot,
        mock_capture_dual_camera_frames,
        mock_run_dual_from_frames,
    ):
        mock_get_registry_service.return_value.snapshot.return_value = {
            'selection': {
                'dual_left_camera_index': 1,
                'dual_right_camera_index': 2,
                'backend': 'CAP_DSHOW',
            },
            'suggested_intervals': {
                'single_interval_ms': 1500,
                'dual_interval_ms': 5000,
            },
        }
        mock_get_cached_preview_frame_snapshot.return_value = {
            'config': {
                'mode': 'dual',
                'left_camera_index': 1,
                'right_camera_index': 2,
            },
            'captured_at': 123.456,
            'single_frame': None,
            'left_frame': np.zeros((12, 12, 3), dtype=np.uint8),
            'right_frame': np.ones((12, 12, 3), dtype=np.uint8),
        }
        mock_run_dual_from_frames.return_value = {'status': 'success', 'frame_source': 'preview'}

        from fruit_api.services.detection.realtime_pipeline_service import run_dual_camera_realtime_detection

        payload = run_dual_camera_realtime_detection(app_config=Mock())

        self.assertEqual(payload['frame_source'], 'preview')
        mock_capture_dual_camera_frames.assert_not_called()
        mock_run_dual_from_frames.assert_called_once()

    @patch('fruit_api.services.camera.capture_service.capture_dual_camera_frames')
    @patch('fruit_api.services.camera.capture_service.get_camera_registry_service')
    def test_camera_capture_service_stages_then_saves_bundle_zip(self, mock_get_registry_service, mock_capture_dual):
        media_root = os.path.join(settings.BASE_DIR, 'test_media', 'camera_capture_stage_save')
        shutil.rmtree(media_root, ignore_errors=True)
        os.makedirs(media_root, exist_ok=True)
        try:
            mock_get_registry_service.return_value.snapshot.return_value = {
                'selection': {
                    'preview_camera_indices': [0, 1],
                    'single_camera_index': 0,
                    'dual_left_camera_index': 0,
                    'dual_right_camera_index': 1,
                    'backend': '',
                }
            }
            mock_capture_dual.return_value = (
                np.zeros((24, 24, 3), dtype=np.uint8),
                np.ones((24, 24, 3), dtype=np.uint8) * 255,
            )

            from fruit_api.services.camera.capture_service import CameraCaptureService

            with override_settings(MEDIA_ROOT=media_root):
                service = CameraCaptureService()
                capture_payload = service.capture(
                    user_id=1,
                    camera_indices=[0, 1],
                    capture_mode='dual',
                    persist=False,
                )
                self.assertFalse(capture_payload['persisted'])
                self.assertEqual(len(capture_payload['staged_groups']), 1)

                stage_id = capture_payload['staged_groups'][0]['stage_id']
                record = service.save_staged(user_id=1, stage_ids=[stage_id])

                self.assertEqual(record['capture_mode'], 'bundle')
                self.assertEqual(record['group_count'], 1)

                archive_path = os.path.join(media_root, record['archive_file_path'].replace('/', os.sep))
                self.assertTrue(os.path.exists(archive_path))

                with zipfile.ZipFile(archive_path, 'r') as archive:
                    names = archive.namelist()

                group = record['groups'][0]
                expected_names = {
                    f"{group['group_name']}/{file_info['file_name']}"
                    for file_info in group['files']
                }
                self.assertEqual(set(names), expected_names)
        finally:
            shutil.rmtree(media_root, ignore_errors=True)

    def test_camera_capture_service_delete_record_removes_bundle_archive_and_index(self):
        media_root = os.path.join(settings.BASE_DIR, 'test_media', 'camera_capture_delete')
        shutil.rmtree(media_root, ignore_errors=True)
        os.makedirs(media_root, exist_ok=True)
        try:
            from fruit_api.services.camera.capture_service import CameraCaptureService

            with override_settings(MEDIA_ROOT=media_root):
                service = CameraCaptureService()
                archive_rel = 'camera_captures/bundles/20260502/test_bundle.zip'
                archive_path = os.path.join(media_root, archive_rel.replace('/', os.sep))
                os.makedirs(os.path.dirname(archive_path), exist_ok=True)
                with open(archive_path, 'wb') as handle:
                    handle.write(b'zip')

                service._save_index(
                    {
                        'records': [
                            {
                                'id': 'bundle-1',
                                'user_id': 1,
                                'archive_file_path': archive_rel,
                                'archive_name': 'test_bundle.zip',
                                'files': [],
                            }
                        ]
                    }
                )

                service.delete_record(user_id=1, record_id='bundle-1')

                self.assertFalse(os.path.exists(archive_path))
                self.assertEqual(service._load_index()['records'], [])
        finally:
            shutil.rmtree(media_root, ignore_errors=True)

    def test_validate_completed_task_raises_for_processing(self):
        task = SimpleNamespace(status='processing')
        with self.assertRaises(VideoTaskStateError):
            validate_completed_task(task)

    def test_resolve_image_detection_inputs_pairs_multiple_direct_diameter_groups(self):
        image_bytes = self._image_bytes()
        singles, groups = resolve_image_detection_inputs(
            single_inputs=[self._upload('single.png', image_bytes)],
            diameter_inputs=[
                self._upload('apple_left.png', image_bytes),
                self._upload('apple_right.png', image_bytes),
                self._upload('banana-left.png', image_bytes),
                self._upload('banana-right.png', image_bytes),
            ],
        )

        self.assertEqual(len(singles), 1)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]['input_source'], 'direct_upload')
        self.assertEqual(groups[0]['label'], 'apple')
        self.assertEqual(groups[1]['label'], 'banana')

    def test_resolve_image_detection_inputs_supports_single_zip_and_diameter_zip(self):
        image_bytes = self._image_bytes()
        singles, groups = resolve_image_detection_inputs(
            single_inputs=[
                self._zip_upload(
                    'single.zip',
                    {
                        'single/a.png': image_bytes,
                        'single/sub/b.png': image_bytes,
                        '__MACOSX/ignored.png': image_bytes,
                    },
                )
            ],
            diameter_inputs=[
                self._zip_upload(
                    'diameter.zip',
                    {
                        'diameter/group1/apple_left.png': image_bytes,
                        'diameter/group1/apple_right.png': image_bytes,
                        'diameter/group2/banana_left.png': image_bytes,
                        'diameter/group2/banana_right.png': image_bytes,
                    },
                )
            ],
        )

        self.assertEqual(len(singles), 2)
        self.assertTrue(all(item['input_source'] == 'zip_archive' for item in singles))
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]['archive_name'], 'diameter.zip')

    def test_resolve_image_detection_inputs_supports_nested_bundle_zip_for_diameter_inputs(self):
        image_bytes = self._image_bytes()
        inner_buffer = io.BytesIO()
        with zipfile.ZipFile(inner_buffer, 'w') as inner_archive:
            inner_archive.writestr('20260502_180402_group_01/20260502_180402_left.jpg', image_bytes)
            inner_archive.writestr('20260502_180402_group_01/20260502_180402_right.jpg', image_bytes)

        singles, groups = resolve_image_detection_inputs(
            single_inputs=[],
            diameter_inputs=[
                self._zip_upload(
                    'camera_captures_1777719490164.zip',
                    {
                        'camera_capture_bundle_20260502_180402_b78c90d1.zip': inner_buffer.getvalue(),
                    },
                )
            ],
        )

        self.assertEqual(singles, [])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['archive_name'], 'camera_captures_1777719490164.zip')
        self.assertEqual(groups[0]['left_name'], '20260502_180402_left.jpg')
        self.assertEqual(groups[0]['right_name'], '20260502_180402_right.jpg')

    def test_resolve_image_detection_inputs_rejects_illegal_archive_path(self):
        image_bytes = self._image_bytes()
        with self.assertRaises(UploadResolveError):
            resolve_image_detection_inputs(
                single_inputs=[
                    self._zip_upload(
                        'single.zip',
                        {
                            '../escape.png': image_bytes,
                        },
                    )
                ],
                diameter_inputs=[],
            )




