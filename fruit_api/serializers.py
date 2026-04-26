from rest_framework import serializers

from .models import DetectionHistory


class DetectionHistorySerializer(serializers.ModelSerializer):
    detection_type_display = serializers.CharField(source="get_detection_type_display", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = DetectionHistory
        fields = [
            "id",
            "user",
            "user_name",
            "detection_type",
            "detection_type_display",
            "created_at",
            "summary",
            "report_file",
        ]


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


class StereoCalibrationCaptureSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=False, allow_blank=False)


class StereoCalibrationRunSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=False, allow_blank=False)
    cols = serializers.IntegerField(required=False, min_value=3, max_value=32, default=9)
    rows = serializers.IntegerField(required=False, min_value=3, max_value=32, default=6)
    square_mm = serializers.FloatField(required=False, min_value=0.1, default=25.0)
    min_pairs = serializers.IntegerField(required=False, min_value=4, max_value=64, default=8)
    activate = serializers.BooleanField(required=False, default=True)


class MeasurePointSerializer(serializers.Serializer):
    x = serializers.IntegerField(min_value=0)
    y = serializers.IntegerField(min_value=0)


class MeasureInferSerializer(serializers.Serializer):
    left_image = serializers.ImageField(required=False)
    right_image = serializers.ImageField(required=False)
    left_image_path = serializers.CharField(required=False, allow_blank=False)
    right_image_path = serializers.CharField(required=False, allow_blank=False)
    calib_path = serializers.CharField(required=False, allow_blank=False)
    ckpt_path = serializers.CharField(required=False, allow_blank=False)
    valid_iters = serializers.IntegerField(required=False, min_value=1, max_value=128, default=16)
    save_color = serializers.BooleanField(required=False, default=True)
    save_npy = serializers.BooleanField(required=False, default=True)
    request_id = serializers.CharField(required=False, allow_blank=False)
    return_debug = serializers.BooleanField(required=False, default=False)
    detect_conf = serializers.FloatField(required=False, min_value=0.01, max_value=1.0, default=0.25)

    def validate(self, attrs):
        left_file = attrs.get("left_image")
        right_file = attrs.get("right_image")
        left_path = attrs.get("left_image_path")
        right_path = attrs.get("right_image_path")

        has_files = left_file is not None or right_file is not None
        has_paths = bool(left_path or right_path)

        if has_files and has_paths:
            raise serializers.ValidationError("left/right 图像只能选择一种输入方式：上传文件或本地路径。")
        if has_files:
            if left_file is None or right_file is None:
                raise serializers.ValidationError("上传模式下必须同时提供 left_image 和 right_image。")
            return attrs
        if has_paths:
            if not left_path or not right_path:
                raise serializers.ValidationError("路径模式下必须同时提供 left_image_path 和 right_image_path。")
            return attrs
        raise serializers.ValidationError("请提供 left_image + right_image，或 left_image_path + right_image_path。")


class MeasureDistanceSerializer(serializers.Serializer):
    inference_id = serializers.CharField(required=False, allow_blank=False)
    disp_npy_path = serializers.CharField(required=False, allow_blank=False)
    calib_path = serializers.CharField(required=False, allow_blank=False)
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
        inference_id = attrs.get("inference_id")
        disp_npy_path = attrs.get("disp_npy_path")
        if not inference_id and not disp_npy_path:
            raise serializers.ValidationError("请提供 inference_id 或 disp_npy_path。")

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
            if not inference_id:
                raise serializers.ValidationError("按 YOLO 框测量时必须提供 inference_id。")
            return attrs

        attrs["measure_all_targets"] = True
        if not inference_id:
            raise serializers.ValidationError("默认按 YOLO 框测量时必须提供 inference_id。")
        return attrs
