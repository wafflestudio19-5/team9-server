# Generated by Django 3.2.6 on 2021-12-01 20:38

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0003_auto_20211201_1519'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='friends',
            field=models.ManyToManyField(blank=True, related_name='_user_user_friends_+', to=settings.AUTH_USER_MODEL),
        ),
    ]