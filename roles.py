# Centralized role mapping — single source of truth.
# Integer role values from WN_Users.Roles column mapped to string names.
# Used in all API responses; numeric values are never exposed externally.

ROLE_MAP: dict[int, str] = {
    1:  "super_admin",
    2:  "admin",
    14: "general",
}

DEFAULT_ROLE = "general"


def map_role(role_int) -> str:
    """Convert a numeric role value to its string name."""
    if role_int is None:
        return DEFAULT_ROLE
    try:
        return ROLE_MAP.get(int(role_int), DEFAULT_ROLE)
    except (ValueError, TypeError):
        return DEFAULT_ROLE


def is_admin_role(role_str: str) -> bool:
    return role_str in ("admin", "super_admin")
