# Generated by Django 3.2.6 on 2022-01-15 02:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0024_merge_0022_alter_notice_senders_0023_post_is_sharing"),
    ]

    operations = [
        migrations.RenameField(
            model_name="notice",
            old_name="comment",
            new_name="parent_comment",
        ),
        migrations.AddField(
            model_name="notice",
            name="comments",
            field=models.ManyToManyField(null=True, to="newsfeed.Comment"),
        ),
    ]
