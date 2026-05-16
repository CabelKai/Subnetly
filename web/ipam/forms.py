from django import forms
from django.core.exceptions import ValidationError
from netaddr import IPNetwork

from .models import Application, Assignment


class AssignmentForm(forms.ModelForm):
    """ModelForm for Assignment, excluding `pool` (injected from URL)."""

    class Meta:
        model = Assignment
        fields = ["application", "cidr", "gateway", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, pool=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool = pool
        # Style fields with Tailwind
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400",
            )

    def clean(self):
        cleaned = super().clean()
        cidr_val = cleaned.get("cidr")
        if cidr_val is None or self.pool is None:
            return cleaned

        # Run model-level validation (IP-family + inside-pool checks)
        instance = self.instance or Assignment()
        instance.pool = self.pool
        instance.cidr = cidr_val
        try:
            instance.clean()
        except ValidationError as exc:
            self.add_error(None, exc)
            return cleaned

        # Friendly overlap check against existing assignments in the same pool
        new_net = IPNetwork(str(cidr_val))
        qs = Assignment.objects.filter(pool=self.pool)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        for other in qs:
            other_net = IPNetwork(str(other.cidr))
            if new_net in other_net or other_net in new_net:
                raise ValidationError(
                    {
                        "cidr": (
                            f"Überschneidung mit {other.cidr} ({other.application.name})."
                        )
                    }
                )
        return cleaned
