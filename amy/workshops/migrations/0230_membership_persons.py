# Generated by Django 2.2.17 on 2021-02-14 13:06

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0001_initial'),
        ('workshops', '0229_membership_M2M_organisations'),
    ]

    operations = [
        migrations.AddField(
            model_name='membership',
            name='persons',
            field=models.ManyToManyField(blank=True, related_name='memberships', through='fiscal.MembershipTask', to=settings.AUTH_USER_MODEL),
        ),
    ]
