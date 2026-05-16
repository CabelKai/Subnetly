import logging
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from netaddr import IPNetwork

from ipam.models import Application, Assignment, Pool
from ipam.services.wiki_parser import parse


class Command(BaseCommand):
    help = "Parse a wiki dump and import applications + assignments."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the wiki text file")
        parser.add_argument(
            "--log-dir", default=".", help="Directory for the skip-log file"
        )

    def handle(self, *args, **opts):
        path = Path(opts["path"])
        text = path.read_text(encoding="utf-8")
        entries = parse(text)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(opts["log_dir"]) / f"import_wiki_{ts}.log"
        logger = logging.getLogger("import_wiki")
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        pools = list(Pool.objects.all())
        applications_new = 0
        applications_existing = 0
        assignments_new = 0
        assignments_existing = 0
        skipped = 0

        for entry in entries:
            app_name = entry["application"]
            cidr_str = entry["cidr"]
            notes = entry["notes"]

            application, created = Application.objects.get_or_create(name=app_name)
            if created:
                applications_new += 1
            else:
                applications_existing += 1

            try:
                ipnet = IPNetwork(cidr_str)
            except Exception as e:
                logger.warning(f"SKIP unparseable CIDR '{cidr_str}' ({app_name}): {e}")
                skipped += 1
                continue

            pool = _smallest_containing_pool(pools, ipnet)
            if pool is None:
                logger.warning(f"SKIP no matching pool for {cidr_str} ({app_name})")
                skipped += 1
                continue

            if Assignment.objects.filter(pool=pool, cidr=str(ipnet.cidr)).exists():
                assignments_existing += 1
                continue

            a = Assignment(pool=pool, application=application, cidr=str(ipnet.cidr), notes=notes)
            try:
                a.full_clean()
                with transaction.atomic():
                    a.save()
                assignments_new += 1
            except (ValidationError, IntegrityError) as e:
                logger.warning(f"SKIP {cidr_str} ({app_name}): {e}")
                skipped += 1

        self.stdout.write(
            f"Anwendungen angelegt:   {applications_new}\n"
            f"Anwendungen vorhanden:  {applications_existing}\n"
            f"Assignments angelegt: {assignments_new}\n"
            f"Assignments vorhanden:{assignments_existing}\n"
            f"Übersprungen:         {skipped}  (siehe {log_path})\n"
        )


def _smallest_containing_pool(pools, ipnet):
    candidates = [
        p for p in pools
        if IPNetwork(str(p.cidr)).version == ipnet.version
        and ipnet in IPNetwork(str(p.cidr))
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda p: IPNetwork(str(p.cidr)).prefixlen, reverse=True)
    return candidates[0]
