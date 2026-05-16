from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("ipam", "0003_rename_customer_to_application")]
    operations = [
        migrations.RemoveField(model_name="pool", name="block_prefix"),
    ]
