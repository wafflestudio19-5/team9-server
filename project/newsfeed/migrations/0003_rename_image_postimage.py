# Generated by Django 3.2.6 on 2021-12-01 16:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('newsfeed', '0002_auto_20211201_1519'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Image',
            new_name='PostImage',
        ),
    ]
