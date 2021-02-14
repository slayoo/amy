# Generated by Django 2.2.17 on 2021-02-14 13:06

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


DEFAULT_ROLES = (
    ("default", "Default"),
)


def create_default_membership_person_roles(apps, schema_editor):
    """Create a default MembershipPersonRole."""
    MembershipPersonRole = apps.get_model("fiscal", "MembershipPersonRole")
    objects = [
        MembershipPersonRole(name=name, verbose_name=verbose_name)
        for name, verbose_name in DEFAULT_ROLES
    ]
    MembershipPersonRole.objects.bulk_create(objects)


def remove_default_membership_person_roles(apps, schema_editor):
    """Remove the default-created MembershipPersonRole."""
    MembershipPersonRole = apps.get_model("fiscal", "MembershipPersonRole")
    role_names = [name for name, _ in DEFAULT_ROLES]
    MembershipPersonRole.objects.filter(name__in=role_names).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workshops', '0229_membership_M2M_organisations'),
    ]

    operations = [
        migrations.CreateModel(
            name='MembershipPersonRole',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=40)),
                ('verbose_name', models.CharField(blank=True, default='', max_length=100)),
            ],
        ),
        migrations.RunPython(create_default_membership_person_roles, remove_default_membership_person_roles),
        migrations.CreateModel(
            name='MembershipTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('membership', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='workshops.Membership')),
                ('person', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='fiscal.MembershipPersonRole')),
            ],
            options={
                'ordering': ('role__name', 'membership'),
                'unique_together': {('membership', 'person', 'role')},
            },
        ),
    ]
