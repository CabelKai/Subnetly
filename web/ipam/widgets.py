from django import forms


class PillCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    """Renders M2M selection as Tailwind pill-toggles.

    Real checkbox inputs are kept in the DOM (visually hidden via sr-only)
    so existing JS that reads `input[name=...]:checked` continues to work.
    """

    template_name = "ipam/widgets/pill_checkbox_select.html"
    option_template_name = "ipam/widgets/pill_checkbox_option.html"

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        option["attrs"]["class"] = "sr-only"
        return option
