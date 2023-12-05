def is_relative_to(this, other):
    """Can be replaced by pathlib.Path.is_relative_to() once we drop Python 3.8."""
    try:
        this.relative_to(other)
        return True
    except ValueError:
        return False
