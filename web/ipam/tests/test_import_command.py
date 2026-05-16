import pytest
from django.core.management import call_command
from io import StringIO
from pathlib import Path

from ipam.models import Assignment, Customer, Pool


FIXTURE = str(Path(__file__).parent / "fixtures" / "wiki_sample.txt")


@pytest.mark.django_db
def test_import_creates_customers_and_assignments():
    Pool.objects.create(name="Pool-217.61.248/23", cidr="217.61.248.0/23", block_prefix=30)
    Pool.objects.create(name="Pool-45/24", cidr="45.151.168.0/24")
    Pool.objects.create(name="Pool-185/24", cidr="185.91.196.0/24")
    Pool.objects.create(name="Pool-v6", cidr="2a05:ed80:100::/48")

    out = StringIO()
    call_command("import_wiki", FIXTURE, stdout=out)

    assert Customer.objects.filter(name="BINSS").exists()
    assert Assignment.objects.filter(cidr="217.61.249.0/28").exists()
    assert Assignment.objects.filter(cidr="185.91.196.6/32").exists()
    assert "angelegt" in out.getvalue().lower()


@pytest.mark.django_db
def test_import_is_idempotent():
    Pool.objects.create(name="Pool-217.61.248/23", cidr="217.61.248.0/23", block_prefix=30)
    Pool.objects.create(name="Pool-45/24", cidr="45.151.168.0/24")
    Pool.objects.create(name="Pool-185/24", cidr="185.91.196.0/24")
    Pool.objects.create(name="Pool-v6", cidr="2a05:ed80:100::/48")

    call_command("import_wiki", FIXTURE)
    n_first = Assignment.objects.count()
    call_command("import_wiki", FIXTURE)
    n_second = Assignment.objects.count()

    assert n_first == n_second


@pytest.mark.django_db
def test_import_skips_entries_with_no_matching_pool(tmp_path, capsys):
    txt = tmp_path / "wiki.txt"
    txt.write_text("==== Orphan ====\n8.8.8.0/24\n")
    out = StringIO()
    call_command("import_wiki", str(txt), stdout=out)
    assert Assignment.objects.count() == 0
    assert "übersprungen" in out.getvalue().lower() or "skip" in out.getvalue().lower()
