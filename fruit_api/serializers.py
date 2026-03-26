from rest_framework import serializers
from .models import DetectionHistory

class DetectionHistorySerializer(serializers.ModelSerializer):
    detection_type_display = serializers.CharField(source='get_detection_type_display', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = DetectionHistory
        fields = ['id', 'user', 'user_name', 'detection_type', 'detection_type_display',
                  'created_at', 'summary', 'report_file']
class ImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()

class TypeUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()
    type = serializers.ChoiceField(choices=['mango', 'banana', 'strawberry'])