# Generated by Django 3.2.6 on 2022-01-01 16:31

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("newsfeed", "0014_alter_notification_content"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notice",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("content", models.CharField(blank=True, max_length=100)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("isChecked", models.BooleanField(default=False)),
                ("url", models.CharField(max_length=1000)),
                (
                    "comment",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notices",
                        to="newsfeed.comment",
                    ),
                ),
                (
                    "post",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notices",
                        to="newsfeed.post",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.DeleteModel(
            name="Notification",
        ),
    ]
