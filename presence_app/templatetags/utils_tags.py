from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    try:
        return dictionary.get(key)
    except Exception:
        return None


@register.filter(name='has_group')
def has_group(user, group_name):
    """Return True if the user is in the given group (safe to call from templates)."""
    try:
        return user.groups.filter(name=group_name).exists()
    except Exception:
        return False


# simple utility filters ----------------------------------------------------
@register.filter(name='startswith')
def startswith(value, prefix):
    """Return True if the string value starts with the given prefix.

    Example in template:
        {% if request.path|startswith:'/profile/' %} ... {% endif %}
    """
    try:
        return str(value).startswith(str(prefix))
    except Exception:
        return False


@register.filter(name='times')
def times(value):
    """Return a range object usable in a for loop.

    Example in template:
        {% for _ in 5|times %} ... {% endfor %}
    """
    try:
        return range(int(value))
    except Exception:
        return range(0)
