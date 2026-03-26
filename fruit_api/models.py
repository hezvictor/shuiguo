from django.db import models
from django.contrib.auth.models import User

class DetectionHistory(models.Model):
    DETECTION_TYPE_CHOICES = [
        ('image', '图片检测'),
        ('video', '视频检测'),
        ('realtime', '实时检测'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    detection_type = models.CharField(max_length=10, choices=DETECTION_TYPE_CHOICES, verbose_name='检测类型')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='检测时间')
    summary = models.JSONField(default=dict, verbose_name='摘要信息')
    report_file = models.CharField(max_length=500, blank=True, null=True, verbose_name='报告文件路径')
    # 可选：原始文件名、缩略图等，可根据需求扩展
    # original_file_name = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '检测历史'
        verbose_name_plural = '检测历史'

    def __str__(self):
        return f"{self.user.username} - {self.get_detection_type_display()} - {self.created_at}"