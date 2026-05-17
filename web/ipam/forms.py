from django import forms
from django.core.exceptions import ValidationError
from netaddr import IPNetwork

from .models import Application, Assignment, Pool


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["name", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class AssignmentForm(forms.ModelForm):
    """ModelForm for Assignment, excluding `pool` (injected from URL)."""

    class Meta:
        model = Assignment
        fields = ["applications", "cidr", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "applications": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, pool=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool = pool
        for name, field in self.fields.items():
            if name == "applications":
                continue
            field.widget.attrs.setdefault(
                "class",
                "w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400",
            )

    def clean(self):
        cleaned = super().clean()
        cidr_val = cleaned.get("cidr")
        if cidr_val is None or self.pool is None:
            return cleaned

        instance = self.instance or Assignment()
        instance.pool = self.pool
        instance.cidr = cidr_val
        try:
            instance.clean()
        except ValidationError as exc:
            self.add_error(None, exc)
            return cleaned

        new_net = IPNetwork(str(cidr_val))
        qs = Assignment.objects.filter(pool=self.pool)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        for other in qs:
            other_net = IPNetwork(str(other.cidr))
            if new_net in other_net or other_net in new_net:
                names = ", ".join(sorted(a.name for a in other.applications.all())) or "—"
                raise ValidationError(
                    {"cidr": f"Überschneidung mit {other.cidr} ({names})."}
                )
        return cleaned

    def clean_applications(self):
        apps = self.cleaned_data["applications"]
        if self.instance.pk:
            used = set(
                self.instance.ip_assignments.values_list("application_id", flat=True)
            )
            missing = used - {a.id for a in apps}
            if missing:
                names = list(
                    Application.objects.filter(pk__in=missing).values_list("name", flat=True)
                )
                raise ValidationError(
                    "Diese Anwendungen haben noch IP-Zuordnungen und können nicht "
                    f"entfernt werden: {', '.join(names)}. Erst die IPs löschen."
                )
        return apps


class PoolForm(forms.ModelForm):
    class Meta:
        model = Pool
        fields = ["name", "cidr", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
