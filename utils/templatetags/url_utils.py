from django import template

register = template.Library()


@register.simple_tag
def url_replace(request, key, value):
    query_params = request.GET.copy()
    query_params[key] = value

    return query_params.urlencode()


@register.simple_tag
def url_remove(request, key, value=None):
    query_params = request.GET.copy()
    query_params.pop("page", None)

    if value is None:
        query_params.pop(key, None)
        return query_params.urlencode()

    values = query_params.getlist(key)
    values = [current_value for current_value in values if current_value != value]

    if values:
        query_params.setlist(key, values)
    else:
        query_params.pop(key, None)

    return query_params.urlencode()


@register.filter
def replace_quotes(value):
    return value.replace('"', "'")
