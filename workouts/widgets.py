import json

from django import forms
from django.forms.utils import flatatt
from django.utils.html import format_html, json_script
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _


def _steps_as_list(value):
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        out = []
        for x in value:
            if x is None:
                out.append("")
            elif isinstance(x, str):
                out.append(x)
            else:
                out.append(str(x))
        return out
    if isinstance(value, str):
        try:
            return _steps_as_list(json.loads(value))
        except json.JSONDecodeError:
            return []
    return []


class InstructionStepsArrayWidget(forms.Widget):
    """
    Admin-friendly UI: one text field per step, “Add more”, and Remove per row.
    Persists as JSON array in the bound hidden input (same name as the JSONField).
    """

    class Media:
        css = {"all": ("workouts/admin/exercise_instruction_steps.css",)}
        js = ("workouts/admin/exercise_instruction_steps.js",)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        steps = _steps_as_list(value)
        field_id = attrs.get("id", "id_" + name)
        container_id = field_id + "_instruction_ui"
        seed_id = field_id + "_seed"
        hidden_attrs = {
            "type": "hidden",
            "name": name,
            "id": field_id,
            "value": json.dumps(steps),
        }
        hidden = format_html("<input{} />", flatatt(hidden_attrs))
        opening = format_html(
            '<div class="instruction-steps-array" id="{}" data-field-id="{}" data-remove-label="{}">'
            '<div class="instruction-steps-rows"></div>',
            container_id,
            field_id,
            _("Remove"),
        )
        btn = format_html(
            '<button type="button" class="button instruction-steps-add">{}</button>',
            _("Add more"),
        )
        closing = format_html("</div>")
        return mark_safe(
            str(opening)
            + " "
            + str(btn)
            + str(hidden)
            + str(closing)
            + str(json_script(steps, seed_id))
        )


def _methods_as_list(value):
    if value in (None, "", []):
        return []
    if isinstance(value, str):
        try:
            return _methods_as_list(json.loads(value))
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    out = []
    for m in value:
        if not isinstance(m, dict):
            continue
        title = m.get("title", "")
        steps = m.get("steps", [])
        if title is None:
            title = ""
        if not isinstance(title, str):
            title = str(title)
        if steps in (None, ""):
            steps = []
        if not isinstance(steps, list):
            steps = []
        steps2 = []
        for s in steps:
            if s is None:
                continue
            steps2.append(s if isinstance(s, str) else str(s))
        out.append({"title": title, "steps": steps2})
    return out


class InstructionMethodsWidget(forms.Widget):
    """
    Admin-friendly UI: multiple methods, each with title + “Add step”.
    Persists as JSON array in the bound hidden input (same name as the JSONField).
    """

    class Media:
        css = {"all": ("workouts/admin/exercise_instruction_methods.css",)}
        js = ("workouts/admin/exercise_instruction_methods.js",)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        methods = _methods_as_list(value)
        field_id = attrs.get("id", "id_" + name)
        container_id = field_id + "_methods_ui"
        seed_id = field_id + "_seed"
        hidden_attrs = {
            "type": "hidden",
            "name": name,
            "id": field_id,
            "value": json.dumps(methods),
        }
        hidden = format_html("<input{} />", flatatt(hidden_attrs))
        opening = format_html(
            '<div class="instruction-methods" id="{}" data-field-id="{}" data-remove-label="{}">'
            '<div class="instruction-methods-list"></div>',
            container_id,
            field_id,
            _("Remove"),
        )
        btn = format_html(
            '<button type="button" class="button instruction-method-add">{}</button>',
            _("Add method"),
        )
        closing = format_html("</div>")
        return mark_safe(
            str(opening) + str(btn) + str(hidden) + str(closing) + str(json_script(methods, seed_id))
        )
