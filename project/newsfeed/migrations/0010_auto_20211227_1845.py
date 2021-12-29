# Generated by Django 3.2.6 on 2021-12-27 18:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0009_auto_20211227_0035"),
    ]

    operations = [
        migrations.AlterField(
            model_name="comment",
            name="file",
            field=models.FileField(
                blank=True,
                upload_to="user/<django.db.models.fields.related.ForeignKey>/<django.db.models.fields.related.ForeignKey>/%Y/%m/%d/<django.db.models.fields.AutoField>/",
            ),
        ),
        migrations.AlterField(
            model_name="post",
            name="file",
            field=models.FileField(
                blank=True,
                upload_to="user/<django.db.models.fields.related.ForeignKey>/<django.db.models.fields.related.ForeignKey>/%Y/%m/%d/<django.db.models.fields.AutoField>/",
            ),
        ),
    ]