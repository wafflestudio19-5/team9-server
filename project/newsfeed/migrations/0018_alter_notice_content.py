# Generated by Django 3.2.6 on 2022-01-02 21:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0017_notice_senders"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notice",
            name="content",
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
