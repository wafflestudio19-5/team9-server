# Generated by Django 3.2.6 on 2022-01-20 23:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0031_merge_20220120_2301"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="noticesender",
            name="notice",
        ),
        migrations.RemoveField(
            model_name="noticesender",
            name="user",
        ),
        migrations.DeleteModel(
            name="Notice",
        ),
        migrations.DeleteModel(
            name="NoticeSender",
        ),
    ]
