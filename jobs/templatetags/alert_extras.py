from django import template

from jobs.utils import default_alert_name

register = template.Library()


@register.filter()
def show_default_alert_name(alert, idx):
    return default_alert_name(alert, idx)
