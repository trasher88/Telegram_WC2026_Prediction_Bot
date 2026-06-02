from html import escape


def user_display_name(
    user_id: int,
    display_name: str | None = None,
    username: str | None = None,
    first_name: str | None = None,
    *,
    html: bool = False,
    include_username: bool = False,
) -> str:
    """Return the tournament-facing name with safe fallbacks."""
    if display_name:
        name = display_name
    elif username:
        name = f"@{username}"
    elif first_name:
        name = first_name
    else:
        name = f"Игрок {user_id}"

    if include_username and display_name and username:
        name = f"{name} (@{username})"

    if html:
        return escape(name)

    return name
