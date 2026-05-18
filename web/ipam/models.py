import ipaddress

from django.core.exceptions import ValidationError
from django.db import models
from netfields import CidrAddressField, NetManager


class Pool(models.Model):
    name = models.CharField(max_length=100)
    cidr = CidrAddressField(unique=True)
    ip_version = models.PositiveSmallIntegerField(editable=False)
    notes = models.TextField(blank=True)

    objects = NetManager()

    class Meta:
        ordering = ["cidr"]

    def save(self, *args, **kwargs):
        # self.cidr may be a string before the DB field converts it
        cidr = self.cidr
        if isinstance(cidr, str):
            cidr = ipaddress.ip_network(cidr, strict=False)
        self.ip_version = cidr.version
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.cidr})"


class Application(models.Model):
    name = models.CharField(max_length=100, unique=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Anwendung"
        verbose_name_plural = "Anwendungen"

    def __str__(self):
        return self.name


class Assignment(models.Model):
    pool = models.ForeignKey(Pool, on_delete=models.PROTECT, related_name="assignments")
    applications = models.ManyToManyField(Application, related_name="assignments")
    cidr = CidrAddressField()
    notes = models.TextField(blank=True)

    objects = NetManager()

    class Meta:
        ordering = ["cidr"]

    def clean(self):
        super().clean()
        if not self.pool_id or self.cidr is None:
            return
        from netaddr import IPNetwork
        pool_net = IPNetwork(str(self.pool.cidr))
        ass_net = IPNetwork(str(self.cidr))
        if pool_net.version != ass_net.version:
            raise ValidationError(
                {"cidr": f"IP-Familie passt nicht zum Pool (Pool ist IPv{pool_net.version})."}
            )
        if ass_net not in pool_net:
            raise ValidationError(
                {"cidr": f"{self.cidr} liegt nicht innerhalb des Pools {self.pool.cidr}."}
            )

    def __str__(self):
        names = ", ".join(sorted(a.name for a in self.applications.all())) or "—"
        return f"{self.cidr} → {names}"


class IPAssignment(models.Model):
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="ip_assignments"
    )
    address = models.GenericIPAddressField()
    application = models.ForeignKey(
        Application, on_delete=models.PROTECT, related_name="ip_assignments"
    )
    is_gateway = models.BooleanField(default=False)
    label = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["address"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "address"],
                name="ip_unique_per_assignment",
            ),
            models.UniqueConstraint(
                fields=["assignment"],
                condition=models.Q(is_gateway=True),
                name="ip_one_gateway_per_assignment",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.assignment_id or self.address is None:
            return
        import ipaddress
        try:
            net = ipaddress.ip_network(str(self.assignment.cidr), strict=False)
            addr = ipaddress.ip_address(str(self.address))
        except ValueError as exc:
            raise ValidationError({"address": str(exc)})
        if addr.version != net.version:
            raise ValidationError({"address": f"IP-Familie passt nicht zum Subnetz (IPv{net.version})."})
        if addr not in net:
            raise ValidationError(
                {"address": f"{addr} liegt nicht im Subnetz {self.assignment.cidr}."}
            )
        if self.application_id and not self.assignment.applications.filter(pk=self.application_id).exists():
            raise ValidationError(
                {"application": "Anwendung ist nicht in der Subnetz-Liste."}
            )
        from .services.ip_list import reserved_kind_for
        kind = reserved_kind_for(self.assignment.cidr, addr)
        if kind == "network":
            raise ValidationError({"address": "Netzwerk-Adresse ist reserviert."})
        if kind == "broadcast":
            raise ValidationError({"address": "Broadcast-Adresse ist reserviert."})

    def __str__(self):
        return f"{self.address} → {self.application.name}"
