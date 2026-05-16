from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ipam", "0002_overlap_constraint"),
    ]

    operations = [
        migrations.RenameModel(old_name="Customer", new_name="Application"),
        migrations.RenameField(
            model_name="assignment",
            old_name="customer",
            new_name="application",
        ),
        migrations.AlterModelOptions(
            name="application",
            options={
                "ordering": ["name"],
                "verbose_name": "Anwendung",
                "verbose_name_plural": "Anwendungen",
            },
        ),
    ]
