# Generated by Django 3.2.6 on 2022-01-16 21:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0013_auto_20220105_1401"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]