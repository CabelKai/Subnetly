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
    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="assignments")
    cidr = CidrAddressField()
    gateway = models.GenericIPAddressField(null=True, blank=True)
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
        return f"{self.cidr} → {self.application.name}"
