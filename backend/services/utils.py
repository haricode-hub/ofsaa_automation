def shell_escape(value: str) -> str:
    """Return a safely single-quoted string for POSIX shells."""
    return "'" + value.replace("'", "'\"'\"'") + "'"


def sed_escape(value: str) -> str:
    """Escape replacement text for sed."""
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("&", "\\&")
