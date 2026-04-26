from django.contrib.auth.models import User
from django.db import models


class DetectionHistory(models.Model):
    DETECTION_TYPE_CHOICES = [
        ('image', 'Image Detection'),
        ('video', 'Video Detection'),
        ('realtime', 'Realtime Detection'),
        ('diameter', 'Diameter Measurement'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='User')
    detection_type = models.CharField(max_length=10, choices=DETECTION_TYPE_CHOICES, verbose_name='Detection Type')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    summary = models.JSONField(default=dict, verbose_name='Summary')
    report_file = models.CharField(max_length=500, blank=True, null=True, verbose_name='Report File Path')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Detection History'
        verbose_name_plural = 'Detection History'

    def __str__(self):
        return f"{self.user.username} - {self.get_detection_type_display()} - {self.created_at}"


class VideoProcessingTask(models.Model):
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]

    task_id = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='Task ID')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='User')
    original_file_name = models.CharField(max_length=255, verbose_name='Original File Name')
    input_path = models.CharField(max_length=500, verbose_name='Input File Path')
    output_path = models.CharField(max_length=500, verbose_name='Output File Path')
    process_fps = models.PositiveIntegerField(default=5, verbose_name='Process FPS')

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='processing', verbose_name='Status')
    progress = models.PositiveIntegerField(default=0, verbose_name='Progress')
    processed_frames = models.PositiveIntegerField(default=0, verbose_name='Processed Frames')
    total_frames = models.PositiveIntegerField(default=0, verbose_name='Total Frames')
    frame_rate = models.FloatField(default=0, verbose_name='Frame Rate')
    video_width = models.PositiveIntegerField(default=0, verbose_name='Video Width')
    video_height = models.PositiveIntegerField(default=0, verbose_name='Video Height')
    message = models.CharField(max_length=255, default='任务已创建', verbose_name='Message')
    error = models.TextField(null=True, blank=True, verbose_name='Error')

    report_data = models.JSONField(null=True, blank=True, verbose_name='Report Data')
    report_file = models.CharField(max_length=500, null=True, blank=True, verbose_name='Report File')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Video Processing Task'
        verbose_name_plural = 'Video Processing Task'

    def __str__(self):
        return f'{self.task_id} ({self.status})'
