# Generated manually to add allow_off_network to InstructorProfile
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('presence_app', '0012_userprofile_friends_userprofile_privacy_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='instructorprofile',
            name='allow_off_network',
            field=models.BooleanField(default=False),
        ),
    ]
