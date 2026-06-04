"""Native Google Workspace tools for Hermes.

These wrappers avoid asking the model to shell out to skill scripts for common
operations where a direct tool is safer and more reliable.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python 3.8 compatibility
    ZoneInfo = None

from hermes_constants import display_hermes_home, get_hermes_home
from tools.registry import registry, tool_error, tool_result

_DRIVE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


GOOGLE_CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]

GOOGLE_WORKSPACE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


def _token_path() -> Path:
    return get_hermes_home() / "google_token.json"


def _gws_binary() -> str | None:
    override = os.getenv("HERMES_GWS_BIN")
    if override:
        return override
    return shutil.which("gws")


def _stored_token_scopes(path: Path, fallback_scopes: list[str]) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback_scopes
    scopes = data.get("scopes")
    if isinstance(scopes, list) and scopes:
        return scopes
    return fallback_scopes


def _normalize_authorized_user_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.setdefault("type", "authorized_user")
    return normalized


def _calendar_service():
    return _google_service("calendar", "v3", GOOGLE_CALENDAR_SCOPES)


def _drive_service():
    return _google_service("drive", "v3", GOOGLE_WORKSPACE_SCOPES)


def _docs_service():
    return _google_service("docs", "v1", GOOGLE_WORKSPACE_SCOPES)


def _google_service(api: str, version: str, fallback_scopes: list[str]):
    token_path = _token_path()
    if not token_path.exists():
        raise FileNotFoundError(
            f"Google token not found at {token_path}. Run google-workspace setup first."
        )

    _ensure_google_python_deps()
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(
        str(token_path),
        _stored_token_scopes(token_path, fallback_scopes),
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(
            json.dumps(
                _normalize_authorized_user_payload(json.loads(creds.to_json())),
                indent=2,
            ),
            encoding="utf-8",
        )
    if not creds.valid:
        raise RuntimeError("Google token is invalid. Re-run google-workspace setup.")
    return build(api, version, credentials=creds, cache_discovery=False)


def _check_google_calendar_requirements() -> bool:
    return _check_google_requirements()


def _has_google_python_deps() -> bool:
    try:
        import googleapiclient.discovery  # noqa: F401
        import googleapiclient.http  # noqa: F401
        from google.oauth2.credentials import Credentials  # noqa: F401
    except Exception:
        return False
    return True


def _check_google_requirements() -> bool:
    if not _token_path().exists():
        return False
    return True


def _ensure_google_python_deps() -> None:
    if _has_google_python_deps():
        return
    try:
        from tools.lazy_deps import ensure

        ensure("skill.google_workspace", prompt=False)
    except Exception as exc:
        raise RuntimeError(
            "Google Workspace dependencies are unavailable. "
            "Install the Google Workspace extras or configure gws."
        ) from exc
    if not _has_google_python_deps():
        raise RuntimeError(
            "Google Workspace dependencies are still unavailable after install attempt."
        )


def _calendar_backend() -> str:
    return "gws" if _gws_binary() else "python"


def _gws_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"] = str(_token_path())
    return env


def _run_gws(
    parts: list[str],
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    binary = _gws_binary()
    if not binary:
        raise RuntimeError("gws is not installed")
    cmd = [binary, *parts]
    if params is not None:
        cmd.extend(["--params", json.dumps(params)])
    if body is not None:
        cmd.extend(["--json", json.dumps(body)])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=_gws_env(),
        check=False,
    )
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or "Unknown gws error"
        raise RuntimeError(err)
    stdout = result.stdout.strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Unexpected non-JSON output from gws: {stdout}") from exc


def _event_time(value: str, timezone_name: str) -> dict[str, str]:
    value = (value or "").strip()
    if not value:
        raise ValueError("start and end are required ISO datetimes")
    if "T" not in value:
        return {"date": value}
    return {"dateTime": value, "timeZone": timezone_name}


def _list_window(start: str | None, end: str | None) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    time_min = start or now.isoformat()
    time_max = end or (now + timedelta(days=7)).isoformat()
    return time_min, time_max


def _rfc3339_for_query(value: str, timezone_name: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("start and end are required for calendar queries")
    if value.endswith("Z"):
        return value
    tail = value[10:] if len(value) > 10 else ""
    if "+" in tail or "-" in tail:
        return value
    if "T" not in value:
        return f"{value}T00:00:00Z"
    if ZoneInfo is None:
        return value
    return datetime.fromisoformat(value).replace(
        tzinfo=ZoneInfo(timezone_name)
    ).isoformat()


def _format_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event.get("id", ""),
        "summary": event.get("summary", ""),
        "start": event.get("start", {}).get("dateTime")
        or event.get("start", {}).get("date", ""),
        "end": event.get("end", {}).get("dateTime")
        or event.get("end", {}).get("date", ""),
        "location": event.get("location", ""),
        "htmlLink": event.get("htmlLink", ""),
    }


def _calendar_list(
    *,
    calendar_id: str,
    time_min: str,
    time_max: str,
    max_results: int,
    summary: str | None = None,
) -> list[dict[str, Any]]:
    if _calendar_backend() == "gws":
        params: dict[str, Any] = {
            "calendarId": calendar_id,
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if summary:
            params["q"] = summary
        return _run_gws(["calendar", "events", "list"], params=params).get("items", [])

    service = _calendar_service()
    return service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        q=summary,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute().get("items", [])


def _calendar_insert(*, calendar_id: str, event_body: dict[str, Any]) -> dict[str, Any]:
    if _calendar_backend() == "gws":
        return _run_gws(
            ["calendar", "events", "insert"],
            params={"calendarId": calendar_id},
            body=event_body,
        )

    service = _calendar_service()
    return service.events().insert(
        calendarId=calendar_id,
        body=event_body,
        sendUpdates="none",
    ).execute()


def _calendar_delete(*, calendar_id: str, event_id: str) -> None:
    if _calendar_backend() == "gws":
        _run_gws(
            ["calendar", "events", "delete"],
            params={"calendarId": calendar_id, "eventId": event_id},
        )
        return

    service = _calendar_service()
    service.events().delete(
        calendarId=calendar_id,
        eventId=event_id,
        sendUpdates="none",
    ).execute()


def _calendar_patch(
    *,
    calendar_id: str,
    event_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    if _calendar_backend() == "gws":
        return _run_gws(
            ["calendar", "events", "patch"],
            params={"calendarId": calendar_id, "eventId": event_id},
            body=body,
        )

    service = _calendar_service()
    return service.events().patch(
        calendarId=calendar_id,
        eventId=event_id,
        body=body,
        sendUpdates="none",
    ).execute()


def _escape_drive_query(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("'", "\\'")


def _format_drive_file(file: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": file.get("id", ""),
        "name": file.get("name", ""),
        "mimeType": file.get("mimeType", ""),
        "modifiedTime": file.get("modifiedTime", ""),
        "webViewLink": file.get("webViewLink", ""),
        "parents": file.get("parents", []),
    }


def _drive_fields() -> str:
    return "id, name, mimeType, modifiedTime, webViewLink, parents"


def _drive_list_kwargs(**kwargs: Any) -> dict[str, Any]:
    return {
        **kwargs,
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
        "corpora": "allDrives",
    }


def _normalize_drive_name(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def _drive_name_variants(value: str) -> list[str]:
    variants = []
    for variant in (value, value.lower(), value.upper(), value.title()):
        if variant and variant not in variants:
            variants.append(variant)
    return variants


GOOGLE_NATIVE_CREATE_MIME_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.drawing",
}


def _find_drive_folder(service, folder_name: str) -> list[dict[str, Any]]:
    escaped = _escape_drive_query(folder_name)
    result = service.files().list(**_drive_list_kwargs(
        q=(
            f"mimeType='{_DRIVE_FOLDER_MIME_TYPE}' "
            f"and name='{escaped}' and trashed=false"
        ),
        pageSize=10,
        fields=f"files({_drive_fields()})",
    )).execute()
    files = result.get("files", [])
    if files:
        return files

    first_word = (folder_name or "").split()[0] if (folder_name or "").split() else folder_name
    name_clauses = [
        f"name contains '{_escape_drive_query(variant)}'"
        for variant in _drive_name_variants(first_word)
    ]
    if not name_clauses:
        return []
    result = service.files().list(**_drive_list_kwargs(
        q=(
            f"mimeType='{_DRIVE_FOLDER_MIME_TYPE}' and trashed=false "
            f"and ({' or '.join(name_clauses)})"
        ),
        pageSize=100,
        fields=f"files({_drive_fields()})",
    )).execute()
    expected = _normalize_drive_name(folder_name)
    return [
        file
        for file in result.get("files", [])
        if _normalize_drive_name(file.get("name", "")) == expected
    ]


def _resolve_drive_parent(service, parent_id: str | None, folder_name: str | None) -> str | None:
    if parent_id:
        return parent_id
    if not folder_name:
        return None
    folders = _find_drive_folder(service, folder_name)
    if not folders:
        raise ValueError(f"Drive folder not found: {folder_name}")
    if len(folders) > 1:
        names = ", ".join(f"{f.get('name')} ({f.get('id')})" for f in folders)
        raise ValueError(f"Multiple Drive folders matched {folder_name!r}; retry with parent_id. Matches: {names}")
    return folders[0]["id"]


def _doc_text(document: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in document.get("body", {}).get("content", []):
        paragraph = item.get("paragraph")
        if not paragraph:
            continue
        for element in paragraph.get("elements", []):
            text_run = element.get("textRun")
            if text_run:
                chunks.append(text_run.get("content", ""))
    return "".join(chunks).rstrip("\n")


def _doc_end_index(document: dict[str, Any]) -> int:
    content = document.get("body", {}).get("content", [])
    if not content:
        return 1
    return max(1, int(content[-1].get("endIndex", 1)) - 1)


def google_drive_file(
    action: str,
    file_id: str | None = None,
    query: str | None = None,
    name: str | None = None,
    folder_name: str | None = None,
    parent_id: str | None = None,
    mime_type: str | None = None,
    content: str | None = None,
    match_text: str | None = None,
    local_path: str | None = None,
    output_path: str | None = None,
    export_mime: str | None = None,
    max_results: int = 20,
    permanent: bool = False,
    deletion_confirmation: str | None = None,
) -> str:
    """List, read, create, edit, upload, download, or delete Google Drive files."""
    try:
        action = (action or "").strip().lower()
        drive = _drive_service()

        if action in {"list", "search"}:
            parent = _resolve_drive_parent(drive, parent_id, folder_name)
            clauses = ["trashed=false"]
            if parent:
                clauses.append(f"'{_escape_drive_query(parent)}' in parents")
            if query:
                clauses.append(f"fullText contains '{_escape_drive_query(query)}'")
            if name:
                clauses.append(f"name contains '{_escape_drive_query(name)}'")
            if mime_type:
                clauses.append(f"mimeType='{_escape_drive_query(mime_type)}'")
            result = drive.files().list(**_drive_list_kwargs(
                q=" and ".join(clauses),
                pageSize=max_results,
                fields=f"files({_drive_fields()})",
            )).execute()
            return tool_result(
                success=True,
                files=[_format_drive_file(file) for file in result.get("files", [])],
            )

        if action == "get":
            if not file_id:
                return tool_error("file_id is required", success=False)
            file = drive.files().get(
                fileId=file_id,
                fields=_drive_fields() + ", size, owners(emailAddress)",
                supportsAllDrives=True,
            ).execute()
            return tool_result(success=True, file=file)

        if action == "read":
            if not file_id:
                return tool_error("file_id is required", success=False)
            meta = drive.files().get(
                fileId=file_id,
                fields="id, name, mimeType, webViewLink",
                supportsAllDrives=True,
            ).execute()
            if meta.get("mimeType") != "application/vnd.google-apps.document":
                return tool_error(
                    "read currently supports Google Docs files; use download for binary files",
                    success=False,
                    file=meta,
                )
            doc = _docs_service().documents().get(documentId=file_id).execute()
            return tool_result(success=True, file=meta, text=_doc_text(doc))

        if action in {"create_doc", "create", "create_sheet"}:
            if not name:
                return tool_error("name is required", success=False)
            parent = _resolve_drive_parent(drive, parent_id, folder_name)
            requested_mime_type = (
                mime_type
                or (
                    "application/vnd.google-apps.spreadsheet"
                    if action == "create_sheet"
                    else "application/vnd.google-apps.document"
                )
            )
            if requested_mime_type != "application/vnd.google-apps.document":
                if content:
                    return tool_error(
                        "content insertion is only supported when creating Google Docs",
                        success=False,
                    )
                if requested_mime_type not in GOOGLE_NATIVE_CREATE_MIME_TYPES:
                    return tool_error(
                        "create supports Google-native MIME types; use upload for binary files",
                        success=False,
                    )
                body = {"name": name, "mimeType": requested_mime_type}
                if parent:
                    body["parents"] = [parent]
                created = drive.files().create(
                    body=body,
                    fields=_drive_fields(),
                    supportsAllDrives=True,
                ).execute()
                return tool_result(success=True, status="created", file=_format_drive_file(created))
            doc = _docs_service().documents().create(body={"title": name}).execute()
            document_id = doc["documentId"]
            if content:
                _docs_service().documents().batchUpdate(
                    documentId=document_id,
                    body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
                ).execute()
            if parent:
                current = drive.files().get(
                    fileId=document_id,
                    fields="parents",
                    supportsAllDrives=True,
                ).execute()
                previous_parents = ",".join(current.get("parents", []))
                drive.files().update(
                    fileId=document_id,
                    addParents=parent,
                    removeParents=previous_parents,
                    fields=_drive_fields(),
                    supportsAllDrives=True,
                ).execute()
            meta = drive.files().get(
                fileId=document_id,
                fields=_drive_fields(),
                supportsAllDrives=True,
            ).execute()
            return tool_result(success=True, status="created", file=_format_drive_file(meta))

        if action in {"append", "edit", "replace_text", "rewrite"}:
            if not file_id or content is None:
                return tool_error("file_id and content are required", success=False)
            doc = _docs_service().documents().get(documentId=file_id).execute()
            if action == "replace_text":
                if not match_text:
                    return tool_error("match_text is required for replace_text", success=False)
                requests = [
                    {
                        "replaceAllText": {
                            "containsText": {"text": match_text, "matchCase": False},
                            "replaceText": content,
                        }
                    }
                ]
                status = "replaced"
            elif action == "rewrite":
                end_index = _doc_end_index(doc)
                requests = []
                if end_index > 1:
                    requests.append(
                        {
                            "deleteContentRange": {
                                "range": {"startIndex": 1, "endIndex": end_index}
                            }
                        }
                    )
                requests.append({"insertText": {"location": {"index": 1}, "text": content}})
                status = "rewritten"
            else:
                index = _doc_end_index(doc)
                requests = [{"insertText": {"location": {"index": index}, "text": content}}]
                status = "appended"
            _docs_service().documents().batchUpdate(
                documentId=file_id,
                body={"requests": requests},
            ).execute()
            return tool_result(success=True, status=status, file_id=file_id)

        if action == "create_folder":
            if not name:
                return tool_error("name is required", success=False)
            parent = _resolve_drive_parent(drive, parent_id, folder_name)
            body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
            if parent:
                body["parents"] = [parent]
            created = drive.files().create(
                body=body,
                fields=_drive_fields(),
                supportsAllDrives=True,
            ).execute()
            return tool_result(success=True, status="created", file=_format_drive_file(created))

        if action == "upload":
            if not local_path:
                return tool_error("local_path is required", success=False)
            import mimetypes
            from googleapiclient.http import MediaFileUpload

            path = Path(local_path).expanduser()
            if not path.exists():
                return tool_error(f"file not found: {path}", success=False)
            parent = _resolve_drive_parent(drive, parent_id, folder_name)
            body = {"name": name or path.name}
            if parent:
                body["parents"] = [parent]
            media = MediaFileUpload(
                str(path),
                mimetype=mime_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream",
                resumable=True,
            )
            uploaded = drive.files().create(
                body=body,
                media_body=media,
                fields=_drive_fields(),
                supportsAllDrives=True,
            ).execute()
            return tool_result(success=True, status="uploaded", file=_format_drive_file(uploaded))

        if action == "download":
            if not file_id:
                return tool_error("file_id is required", success=False)
            import io
            from googleapiclient.http import MediaIoBaseDownload

            meta = drive.files().get(
                fileId=file_id,
                fields="id, name, mimeType",
                supportsAllDrives=True,
            ).execute()
            native_export_map = {
                "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
                "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
                "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
                "application/vnd.google-apps.drawing": ("image/png", ".png"),
            }
            output = Path(output_path).expanduser() if output_path else Path.cwd() / meta.get("name", file_id)
            mime = meta.get("mimeType", "")
            if mime in native_export_map:
                selected_export_mime, default_ext = native_export_map[mime]
                if not output_path and not output.suffix:
                    output = output.with_suffix(default_ext)
                request = drive.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime or selected_export_mime,
                )
            else:
                request = drive.files().get_media(fileId=file_id)
            output.parent.mkdir(parents=True, exist_ok=True)
            with io.FileIO(str(output), "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            return tool_result(
                success=True,
                status="downloaded",
                file_id=file_id,
                path=str(output),
                mimeType=mime,
            )

        if action == "delete":
            if not file_id:
                return tool_error("file_id is required", success=False)
            required = f"DELETE {file_id}"
            if (deletion_confirmation or "").strip() != required:
                return tool_error(
                    "explicit user permission required before deleting a Drive file",
                    success=False,
                    required_confirmation=required,
                    note="Ask the user to confirm with the exact phrase before retrying.",
                )
            if permanent:
                drive.files().delete(fileId=file_id, supportsAllDrives=True).execute()
                return tool_result(success=True, status="deleted", file_id=file_id, permanent=True)
            drive.files().update(
                fileId=file_id,
                body={"trashed": True},
                fields="id, trashed",
                supportsAllDrives=True,
            ).execute()
            return tool_result(success=True, status="trashed", file_id=file_id, permanent=False)

        return tool_error(
            "action must be one of: list, search, get, read, create, create_doc, create_sheet, append, edit, replace_text, rewrite, create_folder, upload, download, delete",
            success=False,
        )
    except Exception as exc:
        return tool_error(str(exc), success=False)


def _reminders(minutes: int | None) -> dict[str, Any] | None:
    if minutes is None:
        return None
    return {
        "useDefault": False,
        "overrides": [{"method": "popup", "minutes": int(minutes)}],
    }


def google_calendar_event(
    action: str,
    event_id: str | None = None,
    summary: str | None = None,
    start: str | None = None,
    end: str | None = None,
    timezone_name: str = "America/New_York",
    calendar_id: str = "primary",
    location: str | None = None,
    description: str | None = None,
    attendees: list[str] | None = None,
    reminder_minutes: int | None = None,
    max_results: int = 10,
) -> str:
    """Create, upsert, list, or delete real Google Calendar events."""
    try:
        action = (action or "").strip().lower()

        if action == "list":
            time_min, time_max = _list_window(start, end)
            return tool_result(
                success=True,
                events=[
                    _format_event(e)
                    for e in _calendar_list(
                        calendar_id=calendar_id,
                        time_min=time_min,
                        time_max=time_max,
                        max_results=max_results,
                    )
                ],
            )

        if action == "delete":
            if event_id:
                _calendar_delete(calendar_id=calendar_id, event_id=event_id)
                return tool_result(success=True, status="deleted", event_id=event_id)

            if not summary or not start or not end:
                return tool_error(
                    "delete requires event_id, or summary plus start and end",
                    success=False,
                )

            query_start = _rfc3339_for_query(start, timezone_name)
            query_end = _rfc3339_for_query(end, timezone_name)
            existing = _calendar_list(
                calendar_id=calendar_id,
                time_min=query_start,
                time_max=query_end,
                max_results=max_results,
                summary=summary,
            )
            matches = [
                event for event in existing
                if event.get("summary", "").casefold() == summary.casefold()
            ]
            if not matches:
                return tool_result(success=True, status="not_found", deleted=0)
            if len(matches) > 1:
                return tool_error(
                    "delete matched multiple events; retry with event_id",
                    success=False,
                    matches=[_format_event(event) for event in matches],
                )
            target = matches[0]
            _calendar_delete(calendar_id=calendar_id, event_id=target["id"])
            return tool_result(
                success=True,
                status="deleted",
                deleted=1,
                event=_format_event(target),
            )

        if action not in {"create", "upsert"}:
            return tool_error("action must be one of: create, upsert, list, delete", success=False)

        if not summary or not start or not end:
            return tool_error("summary, start, and end are required", success=False)

        event_body: dict[str, Any] = {
            "summary": summary,
            "start": _event_time(start, timezone_name),
            "end": _event_time(end, timezone_name),
        }
        if location:
            event_body["location"] = location
        if description:
            event_body["description"] = description
        if attendees:
            event_body["attendees"] = [{"email": e} for e in attendees if e]
        reminders = _reminders(reminder_minutes)
        if reminders:
            event_body["reminders"] = reminders

        if action == "upsert":
            query_start = _rfc3339_for_query(start, timezone_name)
            query_end = _rfc3339_for_query(end, timezone_name)
            existing = _calendar_list(
                calendar_id=calendar_id,
                time_min=query_start,
                time_max=query_end,
                max_results=10,
                summary=summary,
            )
            for event in existing:
                if event.get("summary", "").casefold() == summary.casefold():
                    if reminders:
                        updated = _calendar_patch(
                            calendar_id=calendar_id,
                            event_id=event["id"],
                            body={"reminders": reminders},
                        )
                        return tool_result(
                            success=True,
                            status="updated",
                            event=_format_event(updated),
                        )
                    return tool_result(
                        success=True,
                        status="exists",
                        event=_format_event(event),
                    )

        created = _calendar_insert(calendar_id=calendar_id, event_body=event_body)
        return tool_result(
            success=True,
            status="created",
            event=_format_event(created),
        )
    except Exception as exc:
        return tool_error(str(exc), success=False)


GOOGLE_CALENDAR_EVENT_SCHEMA = {
    "name": "google_calendar_event",
    "description": (
        "Create, upsert, list, or delete REAL Google Calendar events using "
        "the user's Hermes Google OAuth token. Use this for calendar "
        "appointments. Do not use cronjob for calendar events unless the user "
        "asks for a reminder notification instead of a calendar entry. Inserts "
        "and deletes never send email invitations by default."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "One of: create, upsert, list, delete. Prefer upsert when the user wants no duplicates.",
            },
            "event_id": {
                "type": "string",
                "description": "Google Calendar event id. Preferred for delete when available.",
            },
            "summary": {"type": "string", "description": "Event title."},
            "start": {
                "type": "string",
                "description": "ISO datetime, e.g. 2026-06-02T06:30:00, or date for all-day events.",
            },
            "end": {
                "type": "string",
                "description": "ISO datetime, e.g. 2026-06-02T12:00:00, or date for all-day events.",
            },
            "timezone_name": {
                "type": "string",
                "description": "IANA timezone. Default America/New_York.",
                "default": "America/New_York",
            },
            "calendar_id": {
                "type": "string",
                "description": "Calendar id. Use primary unless the user specifies another calendar.",
                "default": "primary",
            },
            "location": {"type": "string", "description": "Optional location."},
            "description": {"type": "string", "description": "Optional event notes."},
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional attendee emails. Omit unless the user explicitly asks for guests.",
            },
            "reminder_minutes": {
                "type": "integer",
                "description": "Optional popup reminder minutes before start, e.g. 30.",
            },
            "max_results": {
                "type": "integer",
                "description": "For action=list only.",
                "default": 10,
            },
        },
        "required": ["action"],
    },
}


GOOGLE_DRIVE_FILE_SCHEMA = {
    "name": "google_drive_file",
    "description": (
        "List, search, inspect, read, create, append/edit/rewrite, upload, download, "
        "trash, or permanently delete REAL Google Drive files using the "
        "user's Hermes Google OAuth token. Supports Google Docs text reads "
        "and edits. Use this to modify Google Docs directly instead of saying "
        "Docs cannot be edited. For deletes, the tool refuses to run until the "
        "user has confirmed the exact required deletion phrase."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": (
                    "One of: list, search, get, read, create_doc, append, edit, "
                    "replace_text, rewrite, create_folder, upload, download, delete. "
                    "Use append/edit to add text to a Google Doc, replace_text with "
                    "match_text to replace matching text, and rewrite to replace the "
                    "document body. Use action=create_sheet "
                    "or action=create with mime_type=application/vnd.google-apps.spreadsheet "
                    "to create a Google Sheet."
                ),
            },
            "file_id": {
                "type": "string",
                "description": "Google Drive file id. Required for get, read, append/edit, download, and delete.",
            },
            "query": {
                "type": "string",
                "description": "Full-text search query for list/search.",
            },
            "name": {
                "type": "string",
                "description": "File/folder name filter, or title for create/create_doc/create_folder/upload.",
            },
            "folder_name": {
                "type": "string",
                "description": "Folder name to list within or create into, e.g. CEO Docs. If ambiguous, retry with parent_id.",
            },
            "parent_id": {
                "type": "string",
                "description": "Drive folder id to list within or create into. Prefer this when known.",
            },
            "mime_type": {
                "type": "string",
                "description": "Optional MIME filter for list/search, Google-native MIME type for create, or MIME type for upload.",
            },
            "content": {
                "type": "string",
                "description": "Text content for create_doc, append/edit, replace_text, or rewrite.",
            },
            "match_text": {
                "type": "string",
                "description": "Text to replace for action=replace_text.",
            },
            "local_path": {
                "type": "string",
                "description": "Local path to upload for action=upload.",
            },
            "output_path": {
                "type": "string",
                "description": "Local output path for action=download.",
            },
            "export_mime": {
                "type": "string",
                "description": "Export MIME type for Google-native downloads, e.g. text/plain.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum files to return for list/search.",
                "default": 20,
            },
            "permanent": {
                "type": "boolean",
                "description": "For delete only. False trashes the file; true permanently deletes it.",
                "default": False,
            },
            "deletion_confirmation": {
                "type": "string",
                "description": (
                    "For delete only. Must exactly equal DELETE <file_id>. "
                    "Do not provide this unless the user explicitly confirmed that exact phrase."
                ),
            },
        },
        "required": ["action"],
    },
}


registry.register(
    name="google_calendar_event",
    toolset="google-workspace",
    schema=GOOGLE_CALENDAR_EVENT_SCHEMA,
    handler=lambda args, **kw: google_calendar_event(
        action=args.get("action", ""),
        event_id=args.get("event_id"),
        summary=args.get("summary"),
        start=args.get("start"),
        end=args.get("end"),
        timezone_name=args.get("timezone_name") or "America/New_York",
        calendar_id=args.get("calendar_id") or "primary",
        location=args.get("location"),
        description=args.get("description"),
        attendees=args.get("attendees"),
        reminder_minutes=args.get("reminder_minutes"),
        max_results=args.get("max_results") or 10,
    ),
    check_fn=_check_google_calendar_requirements,
    description=f"Google Calendar using OAuth files in {display_hermes_home()}.",
    emoji="GCal",
)

registry.register(
    name="google_drive_file",
    toolset="google-workspace",
    schema=GOOGLE_DRIVE_FILE_SCHEMA,
    handler=lambda args, **kw: google_drive_file(
        action=args.get("action", ""),
        file_id=args.get("file_id"),
        query=args.get("query"),
        name=args.get("name"),
        folder_name=args.get("folder_name"),
        parent_id=args.get("parent_id"),
        mime_type=args.get("mime_type") or args.get("mimeType"),
        content=args.get("content"),
        match_text=args.get("match_text") or args.get("matchText"),
        local_path=args.get("local_path"),
        output_path=args.get("output_path"),
        export_mime=args.get("export_mime"),
        max_results=args.get("max_results") or 20,
        permanent=bool(args.get("permanent")),
        deletion_confirmation=args.get("deletion_confirmation"),
    ),
    check_fn=_check_google_requirements,
    description=f"Google Drive and Docs using OAuth files in {display_hermes_home()}.",
    emoji="GDrive",
)
