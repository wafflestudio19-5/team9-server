# Generated by Django 3.2.6 on 2022-01-16 15:09

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('newsfeed', '0026_remove_notice_count'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='notice',
            name='comments',
        ),
        migrations.RemoveField(
            model_name='notice',
            name='senders',
        ),
        migrations.CreateModel(
            name='NoticeSender',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('count', models.PositiveIntegerField(default=0)),
                ('notice', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='senders', to='newsfeed.notice')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='noticesenders', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
