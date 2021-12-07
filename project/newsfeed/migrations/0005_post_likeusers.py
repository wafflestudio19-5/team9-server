# Generated by Django 3.2.6 on 2021-12-06 01:09

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("newsfeed", "0004_alter_post_author"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="likeusers",
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL),
        ),
    ]
