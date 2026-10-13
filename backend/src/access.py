"""Who may see a stored record: the one ownership rule for every resource.

Every persisted resource that can belong to a user (saved runs, scenario
suites, calibration runs) is checked through this module, so the rule lives in
one place rather than in a copy per route or DAO.

The rule:

* an admin sees everything;
* a record with an owner is visible to that owner only;
* a record with no owner (``user_id`` NULL) depends on the resource:

  - *private* resources (suites, calibration runs) were created by signed-in
    users only, so an unowned row is a legacy row stored before the owner
    column existed, and only admins see it;
  - *public* resources (simulation runs) are also produced by anonymous
    studies (sweeps, batch experiments started without signing in), which
    have always been readable by anyone; those stay public.

Callers that cannot see a record get the same answer as for a missing one
(404), so ids of other users' records cannot be probed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Caller:
    """The identity a request acts as. ``user_id`` is None when anonymous."""

    user_id: Optional[str]
    is_admin: bool = False


ANONYMOUS = Caller(user_id=None)


def can_see(owner: Optional[str], caller: Caller, *, unowned_public: bool) -> bool:
    """Whether ``caller`` may read (and, for its own records, change) a record
    owned by ``owner``."""
    if caller.is_admin:
        return True
    if owner is None:
        return unowned_public
    return caller.user_id is not None and owner == caller.user_id


def owner_filter(
    caller: Caller, *, unowned_public: bool, column: str = "user_id"
) -> Tuple[str, Tuple[str, ...]]:
    """The SQL condition (without ``WHERE``) and parameters that select the
    rows ``can_see`` allows, for list queries. ``column`` is a trusted
    identifier from the calling module, never user input."""
    if caller.is_admin:
        return "1 = 1", ()
    if caller.user_id is None:
        return (f"{column} IS NULL", ()) if unowned_public else ("0 = 1", ())
    if unowned_public:
        return f"({column} IS NULL OR {column} = ?)", (caller.user_id,)
    return f"{column} = ?", (caller.user_id,)
