import re

from django.conf import settings
from rest_framework import serializers

from .models import DetectionHistory
from .services.history_normalization_service import normalize_history_detail, normalize_history_summary


class DetectionHistorySerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    detail_data = serializers.SerializerMethodField()
    detection_type_display = serializers.CharField(source="get_detection_type_display", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    report_url = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()
    source_entries = serializers.SerializerMethodField()

    class Meta:
        model = DetectionHistory
        fields = [
            "id",
            "user",
            "user_name",
            "detection_type",
            "detection_type_display",
            "title",
            "status",
            "status_display",
            "created_at",
            "input_count",
            "options",
            "summary",
            "detail_data",
            "artifacts",
            "cover_image",
            "cover_image_url",
            "report_file",
            "report_url",
            "source_entries",
        ]

    @staticmethod
    def _media_url(value):
        if not value:
            return None
        if isinstance(value, str) and (
            value.startswith("http://") or value.startswith("https://") or value.startswith("/media/")
        ):
            return value
        return f"{settings.MEDIA_URL.rstrip('/')}/{value.lstrip('/')}"

    def get_report_url(self, obj):
        return self._media_url(obj.report_file)

    def get_cover_image_url(self, obj):
        return self._media_url(obj.cover_image)

    def get_title(self, obj):
        raw_title = (obj.title or "").strip()
        if not raw_title:
            return raw_title
        return re.sub(r"\s\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", "", raw_title)

    def get_summary(self, obj):
        return normalize_history_summary(obj)

    def get_detail_data(self, obj):
        return normalize_history_detail(obj)

    def get_source_entries(self, obj):
        detail_data = normalize_history_detail(obj)
        items = detail_data.get("items", []) if isinstance(detail_data, dict) else []
        entries = []
        seen = set()

        for item in items:
            if not isinstance(item, dict):
                continue

            archive_name = item.get("archive_name")
            item_type = item.get("item_type")
            display_name = item.get("display_name")
            original_image = self._media_url(item.get("original_image"))

            if archive_name:
                key = ("archive", archive_name)
                if key in seen:
                    continue
                seen.add(key)
                entries.append(
                    {
                        "label": archive_name,
                        "kind": "archive",
                        "url": None,
                        "item_type": item_type,
                    }
                )
                continue

            if item_type == "image" and display_name:
                key = ("image", display_name, original_image)
                if key in seen:
                    continue
                seen.add(key)
                entries.append(
                    {
                        "label": display_name,
                        "kind": "image",
                        "url": original_image,
                        "item_type": item_type,
                    }
                )
                continue

            if display_name:
                key = ("group", display_name, item_type)
                if key in seen:
                    continue
                seen.add(key)
                entries.append(
                    {
                        "label": display_name,
                        "kind": "group",
                        "url": None,
                        "item_type": item_type,
                    }
                )

        return entries


class DetectionHistoryListSerializer(DetectionHistorySerializer):
    class Meta(DetectionHistorySerializer.Meta):
        fields = [
            "id",
            "user",
            "user_name",
            "detection_type",
            "detection_type_display",
            "title",
            "status",
            "status_display",
            "created_at",
            "input_count",
            "options",
            "summary",
            "cover_image",
            "cover_image_url",
            "report_file",
            "report_url",
            "source_entries",
        ]


class ImageDetectionTaskCreateSerializer(serializers.Serializer):
    detect_ripeness = serializers.BooleanField(required=False, default=False)
    detect_classification = serializers.BooleanField(required=False, default=True)
    detect_diameter = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        request = self.context["request"]
        single_inputs = request.FILES.getlist("single_inputs")
        diameter_inputs = request.FILES.getlist("diameter_inputs")
        mixed_inputs = request.FILES.getlist("mixed_inputs")

        if not single_inputs and not diameter_inputs and not mixed_inputs:
            raise serializers.ValidationError("请至少上传单图输入、果径图片输入或混合输入。")

        if attrs.get("detect_ripeness"):
            attrs["detect_classification"] = True

        attrs["single_input_count"] = len(single_inputs)
        attrs["diameter_input_count"] = len(diameter_inputs)
        attrs["mixed_input_count"] = len(mixed_inputs)
        return attrs


class ImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()


class TypeUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()
    type = serializers.ChoiceField(choices=["mango", "banana", "strawberry"])


class StereoDiameterSerializer(serializers.Serializer):
    left_image = serializers.ImageField(required=False)
    right_image = serializers.ImageField(required=False)
    image = serializers.ImageField(required=False)
    split_mode = serializers.ChoiceField(
        choices=["left_right", "top_bottom"],
        required=False,
        default="left_right",
    )
    conf = serializers.FloatField(required=False, min_value=0.01, max_value=1.0, default=0.25)
    save_vis = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        image = attrs.get("image")
        left = attrs.get("left_image")
        right = attrs.get("right_image")
        if image is not None:
            return attrs
        if left is None or right is None:
            raise serializers.ValidationError("请提供单张双目图像 image，或同时提供 left_image 和 right_image。")
        return attrs


class StereoCameraStartSerializer(serializers.Serializer):
    source_mode = serializers.ChoiceField(choices=["single", "dual"], required=False, default="single")
    camera_index = serializers.IntegerField(required=False, min_value=0, default=0)
    left_camera_index = serializers.IntegerField(required=False, min_value=0, default=0)
    right_camera_index = serializers.IntegerField(required=False, min_value=0, default=1)
    frame_width = serializers.IntegerField(required=False, min_value=1)
    frame_height = serializers.IntegerField(required=False, min_value=1)
    fps = serializers.IntegerField(required=False, min_value=1, max_value=120)
    split_mode = serializers.ChoiceField(choices=["left_right", "top_bottom"], required=False, default="left_right")
    backend = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):
        if attrs.get("source_mode") == "dual":
            left_index = attrs.get("left_camera_index", 0)
            right_index = attrs.get("right_camera_index", 1)
            if left_index == right_index:
                raise serializers.ValidationError("双摄模式下 left_camera_index 和 right_camera_index 不能相同。")
        return attrs


class StereoCameraMeasureSerializer(serializers.Serializer):
    conf = serializers.FloatField(required=False, min_value=0.01, max_value=1.0, default=0.25)
    save_vis = serializers.BooleanField(required=False, default=True)
    save_as_image_task = serializers.BooleanField(required=False, default=False)
    detect_classification = serializers.BooleanField(required=False, default=True)
    detect_ripeness = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs.get("detect_ripeness") and not attrs.get("detect_classification"):
            attrs["detect_classification"] = True
        return attrs


class StereoCalibrationCaptureSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=False, allow_blank=False)


class StereoCalibrationRunSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=False, allow_blank=False)
    cols = serializers.IntegerField(required=False, min_value=3, max_value=32, default=9)
    rows = serializers.IntegerField(required=False, min_value=3, max_value=32, default=6)
    square_mm = serializers.FloatField(required=False, min_value=0.1, default=25.0)
    min_pairs = serializers.IntegerField(required=False, min_value=4, max_value=64, default=8)
    activate = serializers.BooleanField(required=False, default=True)


class CameraRegistrySelectionSerializer(serializers.Serializer):
    single_camera_index = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    dual_left_camera_index = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    dual_right_camera_index = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    preview_camera_indices = serializers.ListField(
        child=serializers.IntegerField(min_value=0),
        required=False,
        allow_empty=True,
    )
    backend = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):
        left_index = attrs.get("dual_left_camera_index")
        right_index = attrs.get("dual_right_camera_index")
        if (left_index is None) ^ (right_index is None):
            raise serializers.ValidationError("dual_left_camera_index 和 dual_right_camera_index 需要同时为空或同时填写。")
        if left_index is not None and right_index is not None and left_index == right_index:
            raise serializers.ValidationError("dual_left_camera_index 和 dual_right_camera_index 不能相同。")
        return attrs

class CameraCaptureSerializer(serializers.Serializer):
    camera_indices = serializers.ListField(
        child=serializers.IntegerField(min_value=0),
        required=False,
        allow_empty=False,
    )
    capture_mode = serializers.ChoiceField(choices=["auto", "single", "dual"], required=False, default="auto")
    left_camera_index = serializers.IntegerField(required=False, min_value=0)
    right_camera_index = serializers.IntegerField(required=False, min_value=0)
    backend = serializers.CharField(required=False, allow_blank=False)
    persist = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        if attrs.get("capture_mode") == "dual":
            left_index = attrs.get("left_camera_index")
            right_index = attrs.get("right_camera_index")
            if left_index is not None and right_index is not None and left_index == right_index:
                raise serializers.ValidationError("双摄拍照时 left_camera_index 和 right_camera_index 不能相同。")
        return attrs


class CameraCaptureDownloadSerializer(serializers.Serializer):
    record_ids = serializers.ListField(child=serializers.CharField(), allow_empty=False)


class CameraCaptureStageSaveSerializer(serializers.Serializer):
    stage_ids = serializers.ListField(child=serializers.CharField(), allow_empty=False)


class RealtimeCurrentFrameDetectSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["single", "dual", "hybrid"])
    camera_index = serializers.IntegerField(required=False, min_value=0)
    left_camera_index = serializers.IntegerField(required=False, min_value=0)
    right_camera_index = serializers.IntegerField(required=False, min_value=0)
    conf = serializers.FloatField(required=False, min_value=0.01, max_value=1.0, default=0.25)
    detect_classification = serializers.BooleanField(required=False, default=True)
    detect_ripeness = serializers.BooleanField(required=False, default=False)
    detect_diameter = serializers.BooleanField(required=False, default=False)
    backend = serializers.CharField(required=False, allow_blank=False)
    frame_data_url = serializers.CharField(required=False, allow_blank=False)
    session_id = serializers.CharField(required=False, allow_blank=False)
    collect_sample = serializers.BooleanField(required=False, default=False)
    target_group_count = serializers.IntegerField(required=False, min_value=1, max_value=500, default=10)
    interval_ms = serializers.IntegerField(required=False, min_value=500, max_value=600000)

    def validate(self, attrs):
        mode = attrs.get("mode")
        if attrs.get("detect_ripeness") and not attrs.get("detect_classification"):
            attrs["detect_classification"] = True
        if mode == "single":
            attrs["detect_diameter"] = False
            if not attrs.get("detect_classification"):
                raise serializers.ValidationError("单摄实时检测至少需要开启水果种类检测。")
        if mode == "dual":
            attrs["detect_diameter"] = True
            left_index = attrs.get("left_camera_index")
            right_index = attrs.get("right_camera_index")
            if left_index is not None and right_index is not None and left_index == right_index:
                raise serializers.ValidationError("双摄实时检测时左右相机不能相同。")
        if mode == "hybrid":
            attrs["detect_diameter"] = True
            if not attrs.get("detect_classification"):
                raise serializers.ValidationError("混合模式至少需要开启水果种类检测。")
            left_index = attrs.get("left_camera_index")
            right_index = attrs.get("right_camera_index")
            if left_index is not None and right_index is not None and left_index == right_index:
                raise serializers.ValidationError("混合模式下左右相机不能相同。")
        return attrs


class MeasurePointSerializer(serializers.Serializer):
    x = serializers.IntegerField(min_value=0)
    y = serializers.IntegerField(min_value=0)


class MeasureInferSerializer(serializers.Serializer):
    FORBIDDEN_FIELDS = ("left_image_path", "right_image_path", "calib_path", "ckpt_path")
    left_image = serializers.ImageField(required=False)
    right_image = serializers.ImageField(required=False)
    valid_iters = serializers.IntegerField(required=False, min_value=1, max_value=128, default=16)
    save_color = serializers.BooleanField(required=False, default=True)
    save_npy = serializers.BooleanField(required=False, default=True)
    request_id = serializers.CharField(required=False, allow_blank=False)
    return_debug = serializers.BooleanField(required=False, default=False)
    detect_conf = serializers.FloatField(required=False, min_value=0.01, max_value=1.0, default=0.25)

    def validate(self, attrs):
        forbidden = [field for field in self.FORBIDDEN_FIELDS if field in self.initial_data]
        if forbidden:
            raise serializers.ValidationError({field: "已禁用本地路径输入，请改为上传双目图像文件。" for field in forbidden})
        left_file = attrs.get("left_image")
        right_file = attrs.get("right_image")
        if left_file is None or right_file is None:
            raise serializers.ValidationError("上传模式下必须同时提供 left_image 和 right_image。")
        return attrs


class MeasureDistanceSerializer(serializers.Serializer):
    FORBIDDEN_FIELDS = ("disp_npy_path", "calib_path")
    inference_id = serializers.CharField(required=True, allow_blank=False)
    point1 = MeasurePointSerializer(required=False)
    point2 = MeasurePointSerializer(required=False)
    patch_size = serializers.IntegerField(required=False, min_value=1, max_value=51, default=5)
    distance_unit = serializers.ChoiceField(required=False, choices=["mm", "m"], default="mm")
    save_annotated = serializers.BooleanField(required=False, default=True)
    request_id = serializers.CharField(required=False, allow_blank=False)
    target_index = serializers.IntegerField(required=False, min_value=0)
    measure_all_targets = serializers.BooleanField(required=False, default=False)
    bbox = serializers.ListField(child=serializers.IntegerField(), required=False, min_length=4, max_length=4)
    return_debug = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        forbidden = [field for field in self.FORBIDDEN_FIELDS if field in self.initial_data]
        if forbidden:
            raise serializers.ValidationError({field: "已禁用本地路径输入，请改为使用 inference_id。" for field in forbidden})
        has_points = attrs.get("point1") is not None or attrs.get("point2") is not None
        has_bbox = attrs.get("bbox") is not None
        has_target_mode = attrs.get("measure_all_targets") or attrs.get("target_index") is not None

        if has_points:
            if attrs.get("point1") is None or attrs.get("point2") is None:
                raise serializers.ValidationError("点位测量必须同时提供 point1 和 point2。")
            return attrs

        if has_bbox:
            return attrs

        if has_target_mode:
            return attrs

        attrs["measure_all_targets"] = True
        return attrs

        if has_bbox:
            return attrs

        if has_target_mode:
            return attrs

        attrs["measure_all_targets"] = True
        return attrs


