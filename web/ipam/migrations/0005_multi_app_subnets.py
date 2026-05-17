# Generated for multi-app subnets (Task 3)

import django.db.models.deletion
from django.db import migrations, models


def migrate_data(apps, schema_editor):
    Assignment = apps.get_model("ipam", "Assignment")
    IPAssignment = apps.get_model("ipam", "IPAssignment")
    for a in Assignment.objects.all():
        if a.application_id:
            a.applications.add(a.application_id)
        if a.gateway:
            IPAssignment.objects.create(
                assignment=a,
                address=str(a.gateway),
                application_id=a.application_id,
                is_gateway=True,
            )


def reverse_data(apps, schema_editor):
    Assignment = apps.get_model("ipam", "Assignment")
    IPAssignment = apps.get_model("ipam", "IPAssignment")
    for a in Assignment.objects.all():
        first_app = a.applications.order_by("name").first()
        if first_app is not None:
            a.application_id = first_app.id
        gw = IPAssignment.objects.filter(assignment=a, is_gateway=True).first()
        if gw is not None:
            a.gateway = gw.address
        a.save()


class Migration(migrations.Migration):

    dependencies = [
        ("ipam", "0004_remove_pool_block_prefix"),
    ]

    operations = [
        migrations.AddField(
            model_name="assignment",
            name="applications",
            field=models.ManyToManyField(
                related_name="assignments", to="ipam.application"
            ),
        ),
        migrations.CreateModel(
            name="IPAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("address", models.GenericIPAddressField()),
                ("is_gateway", models.BooleanField(default=False)),
                ("label", models.CharField(blank=True, max_length=100)),
                ("notes", models.TextField(blank=True)),
                (
                    "assignment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ip_assignments",
                        to="ipam.assignment",
                    ),
                ),
                (
                    "application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ip_assignments",
                        to="ipam.application",
                    ),
                ),
            ],
            options={
                "ordering": ["address"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("assignment", "address"),
                        name="ip_unique_per_assignment",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("is_gateway", True)),
                        fields=("assignment",),
                        name="ip_one_gateway_per_assignment",
                    ),
                ],
            },
        ),
        migrations.RunPython(migrate_data, reverse_code=reverse_data),
        migrations.RemoveField(
            model_name="assignment",
            name="application",
        ),
        migrations.RemoveField(
            model_name="assignment",
            name="gateway",
        ),
    ]
