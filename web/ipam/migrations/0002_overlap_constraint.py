from django.db import migrations


SQL_FORWARD = """
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE ipam_assignment
ADD CONSTRAINT ipam_assignment_no_overlap
EXCLUDE USING gist (
    pool_id WITH =,
    cidr inet_ops WITH &&
);
"""

SQL_REVERSE = """
ALTER TABLE ipam_assignment
DROP CONSTRAINT IF EXISTS ipam_assignment_no_overlap;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("ipam", "0001_initial"),
    ]
    operations = [
        migrations.RunSQL(SQL_FORWARD, reverse_sql=SQL_REVERSE),
    ]
