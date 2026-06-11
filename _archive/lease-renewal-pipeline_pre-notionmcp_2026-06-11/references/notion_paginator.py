"""
ORA Notion paginator — canonical pattern for fetching all rows of the Tenant Database
(or any large ORA Notion database) via Composio's NOTION_QUERY_DATABASE_WITH_FILTER.

Why this exists
---------------
The native Notion API returns prefixed cursors of the form `s:UUID:UUID` for very large
databases. Composio's validator on `start_cursor` rejects these with:

    Invalid UUID length: expected 32 hex characters, got 67.

Workaround: pass the *last record's page id* as `start_cursor`. Notion accepts this and
returns the next page (with one-record overlap with the previous page). After the first
paginated call Composio also returns a clean UUID cursor that can be reused as-is.

We dedupe by page id to drop the overlapping record.

Use this from inside COMPOSIO_REMOTE_WORKBENCH where `run_composio_tool` is available.

Tested against the Tenant Database (8dbbaec0-611a-4617-be07-6a77d0d0307a) on 2026-04-27
— pulled 298 records across 3 pages with no data loss.

ID semantics (added 2026-04-27)
-------------------------------
This module uses the **database wrapper ID** because Composio's
NOTION_QUERY_DATABASE_WITH_FILTER calls Notion REST `/v1/databases/{id}/query`,
which expects the wrapper. Do NOT pass the data source ID
(`b12f4cfd-a995-4755-8341-6435ae8173b4`) here — it will fail.

For `notion-fetch` schema introspection, the wrapper ID returns 400; pass the
data source ID instead. See the ORA Database ID Map in the Knowledge Base.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional


# Active-tenant filter shared across ORA lease workflows.
ACTIVE_TENANT_FILTER: Dict[str, Any] = {
    "or": [
        {"property": "Lease Status", "select": {"equals": "Active"}},
        {"property": "Lease Status", "select": {"equals": "Month-to-Month"}},
        {"property": "Lease Status", "select": {"equals": "Notice Given"}},
        {"property": "Lease Status", "select": {"equals": "Expired"}},
    ]
}


def query_all_rows(
    run_composio_tool,
    database_id: str,
    filter_: Optional[Dict[str, Any]] = None,
    page_size: int = 100,
    safety_cap_pages: int = 25,
) -> List[Dict[str, Any]]:
    """Paginate every row of a Notion database via Composio.

    Parameters
    ----------
    run_composio_tool : callable
        The workbench helper. Returns (result, error).
    database_id : str
        Notion **database wrapper id** (NOT data source id). For the Tenant
        Database use '8dbbaec0-611a-4617-be07-6a77d0d0307a'. The Composio
        NOTION_QUERY_DATABASE_WITH_FILTER tool requires the wrapper.
    filter_ : dict | None
        Server-side Notion filter. Pass ACTIVE_TENANT_FILTER for active scope.
    page_size : int
        1..100. Default 100.
    safety_cap_pages : int
        Hard cap to prevent runaway loops on misconfigured databases.

    Returns
    -------
    list[dict]
        Deduplicated list of Notion page records.
    """
    args: Dict[str, Any] = {"database_id": database_id, "page_size": page_size}
    if filter_:
        args["filter"] = filter_

    result, error = run_composio_tool(
        tool_slug="NOTION_QUERY_DATABASE_WITH_FILTER", arguments=args
    )
    if error:
        raise RuntimeError(f"Initial query failed: {error}")
    data = (result or {}).get("data", {})
    records = list(data.get("results", []))
    seen = {r["id"] for r in records}
    has_more = data.get("has_more")
    pages = 1

    # Use last record's id as start_cursor to bypass Composio's prefixed-cursor rejection.
    cursor: Optional[str] = records[-1]["id"] if records and has_more else None

    while cursor and pages < safety_cap_pages:
        page_args = dict(args)
        page_args["start_cursor"] = cursor
        result, error = run_composio_tool(
            tool_slug="NOTION_QUERY_DATABASE_WITH_FILTER", arguments=page_args
        )
        if error:
            raise RuntimeError(f"Paginate failed at page {pages + 1}: {error}")
        data = (result or {}).get("data", {})
        page_results = data.get("results", [])
        for r in page_results:
            if r["id"] not in seen:
                seen.add(r["id"])
                records.append(r)
        pages += 1
        if not data.get("has_more"):
            break
        # After page 2+ Composio returns a clean UUID cursor — reuse it.
        cursor = data.get("next_cursor")

    return records


# --- Property accessors -----------------------------------------------------

def title(props: Dict[str, Any], key: str) -> str:
    arr = (props.get(key) or {}).get("title") or []
    return "".join((x or {}).get("plain_text", "") for x in arr).strip()


def select_name(props: Dict[str, Any], key: str) -> Optional[str]:
    s = (props.get(key) or {}).get("select")
    return (s or {}).get("name") if s else None


def number(props: Dict[str, Any], key: str) -> Optional[float]:
    return (props.get(key) or {}).get("number")


def date_start(props: Dict[str, Any], key: str) -> Optional[str]:
    d = (props.get(key) or {}).get("date")
    return (d or {}).get("start") if d else None


def rich_text(props: Dict[str, Any], key: str) -> str:
    arr = (props.get(key) or {}).get("rich_text") or []
    return "".join((x or {}).get("plain_text", "") for x in arr).strip()


def formula_number(props: Dict[str, Any], key: str) -> Optional[float]:
    f = (props.get(key) or {}).get("formula") or {}
    return f.get("number")


def is_excluded_duplicate(name: str) -> bool:
    """Tenant Database housekeeping: rows tagged ⛔ or named DUPLICATE are out of scope."""
    n = (name or "").upper()
    return "⛔" in (name or "") or "DUPLICATE" in n
