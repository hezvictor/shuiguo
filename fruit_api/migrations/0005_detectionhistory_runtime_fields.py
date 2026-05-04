from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fruit_api", "0004_videoprocessingtask"),
    ]

    operations = [
        migrations.AddField(
            model_name="detectionhistory",
            name="artifacts",
            field=models.JSONField(blank=True, default=dict, verbose_name="Artifacts"),
        ),
        migrations.AddField(
            model_name="detectionhistory",
            name="cover_image",
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name="Cover Image Path"),
        ),
        migrations.AddField(
            model_name="detectionhistory",
            name="detail_data",
            field=models.JSONField(blank=True, default=dict, verbose_name="Detail Data"),
        ),
        migrations.AddField(
            model_name="detectionhistory",
            name="input_count",
            field=models.PositiveIntegerField(default=0, verbose_name="Input Count"),
        ),
        migrations.AddField(
            model_name="detectionhistory",
            name="options",
            field=models.JSONField(blank=True, default=dict, verbose_name="Detection Options"),
        ),
        migrations.AddField(
            model_name="detectionhistory",
            name="status",
            field=models.CharField(
                choices=[("completed", "Completed"), ("partial", "Partial Success"), ("failed", "Failed")],
                default="completed",
                max_length=16,
                verbose_name="Status",
            ),
        ),
        migrations.AddField(
            model_name="detectionhistory",
            name="title",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Title"),
        ),
        migrations.AlterField(
            model_name="detectionhistory",
            name="detection_type",
            field=models.CharField(
                choices=[
                    ("image", "Image Detection"),
                    ("realtime", "Realtime Detection"),
                    ("diameter", "Diameter Measurement"),
                ],
                max_length=10,
                verbose_name="Detection Type",
            ),
        ),
    ]
