# Generated by Django 3.2.6 on 2021-12-24 21:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('newsfeed', '0003_auto_20211224_2145'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='mainpost',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='subposts', to='newsfeed.post'),
        ),
        migrations.AlterField(
            model_name='post',
            name='file',
            field=models.FileField(blank=True, upload_to='user/<django.db.models.fields.related.ForeignKey>/<django.db.models.fields.related.ForeignKey>/%Y/%m/%d/<django.db.models.fields.AutoField>/'),
        ),
    ]
