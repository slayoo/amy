# Generated by Django 2.2.13 on 2020-11-18 20:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workshops', '0222_workshoprequest_workshop_listed'),
    ]

    operations = [
        migrations.AddField(
            model_name='membership',
            name='agreement_link',
            field=models.URLField(blank=True, default='', help_text='Link to member agreement or folder in Google Drive', null=True, verbose_name='Link to member agreement'),
        ),
    ]
