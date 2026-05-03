from django.contrib.auth.models import User
from django.db import models


class DetectionHistory(models.Model):
    DETECTION_TYPE_CHOICES = [
        ('image', 'Image Detection'),
        ('realtime', 'Realtime Detection'),
        ('diameter', 'Diameter Measurement'),
    ]
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='User')
    detection_type = models.CharField(max_length=10, choices=DETECTION_TYPE_CHOICES, verbose_name='Detection Type')
    title = models.CharField(max_length=255, blank=True, default='', verbose_name='Title')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='completed', verbose_name='Status')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    input_count = models.PositiveIntegerField(default=0, verbose_name='Input Count')
    options = models.JSONField(default=dict, blank=True, verbose_name='Detection Options')
    summary = models.JSONField(default=dict, verbose_name='Summary')
    detail_data = models.JSONField(default=dict, blank=True, verbose_name='Detail Data')
    artifacts = models.JSONField(default=dict, blank=True, verbose_name='Artifacts')
    cover_image = models.CharField(max_length=500, blank=True, null=True, verbose_name='Cover Image Path')
    report_file = models.CharField(max_length=500, blank=True, null=True, verbose_name='Report File Path')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Detection History'
        verbose_name_plural = 'Detection History'

    def __str__(self):
        return f"{self.user.username} - {self.get_detection_type_display()} - {self.created_at}"
