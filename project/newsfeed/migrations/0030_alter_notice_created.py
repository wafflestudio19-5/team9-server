# Generated by Django 3.2.6 on 2022-01-20 01:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0029_auto_20220117_0038"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notice",
            name="created",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
