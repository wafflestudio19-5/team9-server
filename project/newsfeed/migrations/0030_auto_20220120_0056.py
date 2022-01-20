# Generated by Django 3.2.6 on 2022-01-20 00:56

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('newsfeed', '0029_auto_20220117_0038'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='tagged_users',
            field=models.ManyToManyField(blank=True, related_name='tagged_comments', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='post',
            name='tagged_users',
            field=models.ManyToManyField(blank=True, related_name='tagged_posts', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='notice',
            name='created',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
