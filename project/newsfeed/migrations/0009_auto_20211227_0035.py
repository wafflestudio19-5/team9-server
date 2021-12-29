# Generated by Django 3.2.6 on 2021-12-27 00:35

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("newsfeed", "0008_auto_20211225_0001"),
    ]

    operations = [
        migrations.AlterField(
            model_name="post",
            name="file",
            field=models.FileField(
                blank=True,
                upload_to="user/<django.db.models.fields.related.ForeignKey>/<django.db.models.fields.related.ForeignKey>/%Y/%m/%d/<built-in function id>/",
            ),
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("content", models.CharField(blank=True, max_length=1000)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("likes", models.PositiveIntegerField(default=0)),
                ("depth", models.PositiveIntegerField(default=0)),
                (
                    "file",
                    models.FileField(
                        blank=True,
                        upload_to="user/<django.db.models.fields.related.ForeignKey>/<django.db.models.fields.related.ForeignKey>/%Y/%m/%d/<built-in function id>/",
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("likeusers", models.ManyToManyField(to=settings.AUTH_USER_MODEL)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="newsfeed.comment",
                    ),
                ),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to="newsfeed.post",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]