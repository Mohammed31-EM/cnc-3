import os
from django import template

register = template.Library()

@register.filter(name="basename")
def basename(value):
    """
    Return the basename of a path or storage path.
    Works with strings, Django File/FieldFile (uses .name), and URLs.
    """
    try:
        path = value.name if hasattr(value, "name") else ("" if value is None else str(value))
        # normalize Windows backslashes so os.path.basename works consistently
        path = path.replace("\\", "/")
        return os.path.basename(path)
    except Exception:
        return value