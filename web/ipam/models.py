import ipaddress

from django.db import models
from netfields import CidrAddressField, NetManager


class Pool(models.Model):
    name = models.CharField(max_length=100)
    cidr = CidrAddressField(unique=True)
    ip_version = models.PositiveSmallIntegerField(editable=False)
    block_prefix = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="IPv4 only: prefix length of one grid cell, e.g. 30",
    )
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


class Customer(models.Model):
    name = models.CharField(max_length=100, unique=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Assignment(models.Model):
    # Full definition in Task 7
    pool = models.ForeignKey(Pool, on_delete=models.PROTECT, related_name="assignments")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="assignments")
    cidr = CidrAddressField()
    gateway = models.GenericIPAddressField(null=True, blank=True)
    notes = models.TextField(blank=True)

    objects = NetManager()

    class Meta:
        ordering = ["cidr"]
