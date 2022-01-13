# Generated by Django 3.2.6 on 2022-01-13 18:09

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("newsfeed", "0021_alter_post_scope"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notice",
            name="senders",
            field=models.ManyToManyField(
                null=True, related_name="sent_notices", to=settings.AUTH_USER_MODEL
            ),
        ),
    ]