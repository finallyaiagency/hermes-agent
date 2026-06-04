import json

from tools import google_workspace_tools as gwt


class _Request:
    def __init__(self, result=None, on_execute=None):
        self._result = result
        self._on_execute = on_execute

    def execute(self):
        if self._on_execute:
            self._on_execute()
        return self._result


class _Events:
    def __init__(self, items=None):
        self.items = items or []
        self.deleted = []
        self.list_kwargs = None

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        return _Request({"items": self.items})

    def delete(self, **kwargs):
        self.deleted.append(kwargs)
        return _Request({}, on_execute=lambda: None)


class _Service:
    def __init__(self, items=None):
        self.events_obj = _Events(items)

    def events(self):
        return self.events_obj


class _Files:
    def __init__(self, items=None):
        self.items = items or []
        self.created = []
        self.list_kwargs = []
        self.updated = []

    def list(self, **kwargs):
        self.list_kwargs.append(kwargs)
        return _Request({"files": self.items})

    def create(self, **kwargs):
        self.created.append(kwargs)
        body = kwargs["body"]
        return _Request(
            {
                "id": "created-1",
                "name": body["name"],
                "mimeType": body["mimeType"],
                "parents": body.get("parents", []),
            }
        )

    def update(self, **kwargs):
        self.updated.append(kwargs)
        return _Request({"id": kwargs["fileId"], "trashed": True})


class _DriveService:
    def __init__(self, items=None):
        self.files_obj = _Files(items)

    def files(self):
        return self.files_obj


def test_google_calendar_event_delete_by_event_id(monkeypatch):
    service = _Service()
    monkeypatch.setattr(gwt, "_calendar_service", lambda: service)

    result = json.loads(
        gwt.google_calendar_event(
            action="delete",
            event_id="abc123",
        )
    )

    assert result["success"] is True
    assert result["status"] == "deleted"
    assert service.events_obj.deleted == [
        {"calendarId": "primary", "eventId": "abc123", "sendUpdates": "none"}
    ]


def test_google_calendar_event_delete_by_exact_summary_window(monkeypatch):
    service = _Service(
        [
            {
                "id": "evt-1",
                "summary": "Review appointment",
                "start": {"dateTime": "2026-06-04T14:00:00-04:00"},
                "end": {"dateTime": "2026-06-04T15:00:00-04:00"},
            }
        ]
    )
    monkeypatch.setattr(gwt, "_calendar_service", lambda: service)

    result = json.loads(
        gwt.google_calendar_event(
            action="delete",
            summary="review appointment",
            start="2026-06-04T14:00:00",
            end="2026-06-04T15:00:00",
        )
    )

    assert result["success"] is True
    assert result["status"] == "deleted"
    assert result["deleted"] == 1
    assert service.events_obj.deleted[0]["eventId"] == "evt-1"
    assert service.events_obj.deleted[0]["sendUpdates"] == "none"


def test_google_calendar_event_delete_refuses_multiple_matches(monkeypatch):
    service = _Service(
        [
            {"id": "evt-1", "summary": "Review appointment"},
            {"id": "evt-2", "summary": "Review appointment"},
        ]
    )
    monkeypatch.setattr(gwt, "_calendar_service", lambda: service)

    result = json.loads(
        gwt.google_calendar_event(
            action="delete",
            summary="Review appointment",
            start="2026-06-04T14:00:00",
            end="2026-06-04T15:00:00",
        )
    )

    assert result["success"] is False
    assert "multiple events" in result["error"]
    assert service.events_obj.deleted == []


def test_google_drive_file_lists_folder_by_name(monkeypatch):
    drive = _DriveService(
        [
            {
                "id": "folder-1",
                "name": "CEO Docs",
                "mimeType": "application/vnd.google-apps.folder",
            }
        ]
    )

    def list_side_effect(**kwargs):
        drive.files_obj.list_kwargs.append(kwargs)
        if "mimeType='application/vnd.google-apps.folder'" in kwargs["q"]:
            return _Request(
                {
                    "files": [
                        {
                            "id": "folder-1",
                            "name": "CEO Docs",
                            "mimeType": "application/vnd.google-apps.folder",
                        }
                    ]
                }
            )
        return _Request(
            {
                "files": [
                    {
                        "id": "doc-1",
                        "name": "Board Notes",
                        "mimeType": "application/vnd.google-apps.document",
                    }
                ]
            }
        )

    monkeypatch.setattr(drive.files_obj, "list", list_side_effect)
    monkeypatch.setattr(gwt, "_drive_service", lambda: drive)

    result = json.loads(
        gwt.google_drive_file(action="list", folder_name="CEO Docs")
    )

    assert result["success"] is True
    assert result["files"][0]["id"] == "doc-1"
    assert "'folder-1' in parents" in drive.files_obj.list_kwargs[-1]["q"]


def test_google_drive_file_delete_requires_exact_confirmation(monkeypatch):
    drive = _DriveService()
    monkeypatch.setattr(gwt, "_drive_service", lambda: drive)

    result = json.loads(gwt.google_drive_file(action="delete", file_id="doc-1"))

    assert result["success"] is False
    assert result["required_confirmation"] == "DELETE doc-1"
    assert drive.files_obj.updated == []


def test_google_drive_file_create_honors_spreadsheet_mime_type(monkeypatch):
    drive = _DriveService()
    monkeypatch.setattr(gwt, "_drive_service", lambda: drive)

    def fail_docs_service():
        raise AssertionError("spreadsheet creation should not use Docs API")

    monkeypatch.setattr(gwt, "_docs_service", fail_docs_service)

    result = json.loads(
        gwt.google_drive_file(
            action="create",
            name="Moneypenny Bot Sheet",
            mime_type="application/vnd.google-apps.spreadsheet",
        )
    )

    assert result["success"] is True
    assert result["file"]["mimeType"] == "application/vnd.google-apps.spreadsheet"
    assert drive.files_obj.created == [
        {
            "body": {
                "name": "Moneypenny Bot Sheet",
                "mimeType": "application/vnd.google-apps.spreadsheet",
            },
            "fields": gwt._drive_fields(),
            "supportsAllDrives": True,
        }
    ]


def test_google_drive_file_create_doc_honors_explicit_spreadsheet_mime_type(monkeypatch):
    drive = _DriveService()
    monkeypatch.setattr(gwt, "_drive_service", lambda: drive)
    monkeypatch.setattr(
        gwt,
        "_docs_service",
        lambda: (_ for _ in ()).throw(
            AssertionError("explicit spreadsheet MIME should not use Docs API")
        ),
    )

    result = json.loads(
        gwt.google_drive_file(
            action="create_doc",
            name="Moneypenny Bot Sheet",
            mime_type="application/vnd.google-apps.spreadsheet",
        )
    )

    assert result["success"] is True
    assert result["file"]["mimeType"] == "application/vnd.google-apps.spreadsheet"


def test_google_drive_file_handler_accepts_camelcase_mimetype(monkeypatch):
    drive = _DriveService()
    monkeypatch.setattr(gwt, "_drive_service", lambda: drive)

    result = json.loads(
        gwt.registry.get_entry("google_drive_file").handler(
            {
                "action": "create",
                "name": "Moneypenny Bot Sheet",
                "mimeType": "application/vnd.google-apps.spreadsheet",
            }
        )
    )

    assert result["success"] is True
    assert result["file"]["mimeType"] == "application/vnd.google-apps.spreadsheet"


def test_google_drive_file_create_sheet_action_creates_spreadsheet(monkeypatch):
    drive = _DriveService()
    monkeypatch.setattr(gwt, "_drive_service", lambda: drive)

    result = json.loads(
        gwt.google_drive_file(
            action="create_sheet",
            name="Moneypenny Bot Sheet",
        )
    )

    assert result["success"] is True
    assert result["file"]["mimeType"] == "application/vnd.google-apps.spreadsheet"


def test_google_drive_file_delete_trashes_after_confirmation(monkeypatch):
    drive = _DriveService()
    monkeypatch.setattr(gwt, "_drive_service", lambda: drive)

    result = json.loads(
        gwt.google_drive_file(
            action="delete",
            file_id="doc-1",
            deletion_confirmation="DELETE doc-1",
        )
    )

    assert result["success"] is True
    assert result["status"] == "trashed"
    assert drive.files_obj.updated == [
        {
            "fileId": "doc-1",
            "body": {"trashed": True},
            "fields": "id, trashed",
            "supportsAllDrives": True,
        }
    ]


def test_check_google_requirements_only_needs_token(monkeypatch, tmp_path):
    token_path = tmp_path / "google_token.json"
    token_path.write_text("{}")
    monkeypatch.setattr(gwt, "_token_path", lambda: token_path)

    assert gwt._check_google_requirements() is True


def test_google_calendar_event_create_uses_gws_when_available(monkeypatch):
    monkeypatch.setattr(gwt, "_gws_binary", lambda: "gws")

    captured = {}

    def fake_run_gws(parts, *, params=None, body=None):
        captured["parts"] = parts
        captured["params"] = params
        captured["body"] = body
        return {
            "id": "evt-123",
            "summary": "Self-Care Break",
            "start": {"dateTime": "2026-06-02T15:00:00"},
            "end": {"dateTime": "2026-06-02T16:00:00"},
            "htmlLink": "https://calendar.google.com/event?eid=123",
        }

    monkeypatch.setattr(gwt, "_run_gws", fake_run_gws)

    result = json.loads(
        gwt.google_calendar_event(
            action="create",
            summary="Self-Care Break",
            start="2026-06-02T15:00:00",
            end="2026-06-02T16:00:00",
        )
    )

    assert result["success"] is True
    assert result["status"] == "created"
    assert captured["parts"] == ["calendar", "events", "insert"]
    assert captured["params"] == {"calendarId": "primary"}
    assert captured["body"]["summary"] == "Self-Care Break"


def test_google_calendar_event_upsert_updates_reminders_with_gws(monkeypatch):
    monkeypatch.setattr(gwt, "_gws_binary", lambda: "gws")

    calls = []

    def fake_run_gws(parts, *, params=None, body=None):
        calls.append((parts, params, body))
        if parts == ["calendar", "events", "list"]:
            return {
                "items": [
                    {
                        "id": "evt-1",
                        "summary": "Self-Care Break",
                        "start": {"dateTime": "2026-06-02T15:00:00"},
                        "end": {"dateTime": "2026-06-02T16:00:00"},
                    }
                ]
            }
        if parts == ["calendar", "events", "patch"]:
            return {
                "id": "evt-1",
                "summary": "Self-Care Break",
                "start": {"dateTime": "2026-06-02T15:00:00"},
                "end": {"dateTime": "2026-06-02T16:00:00"},
                "reminders": body["reminders"],
            }
        raise AssertionError(parts)

    monkeypatch.setattr(gwt, "_run_gws", fake_run_gws)

    result = json.loads(
        gwt.google_calendar_event(
            action="upsert",
            summary="Self-Care Break",
            start="2026-06-02T15:00:00",
            end="2026-06-02T16:00:00",
            reminder_minutes=30,
        )
    )

    assert result["success"] is True
    assert result["status"] == "updated"
    assert calls[0][0] == ["calendar", "events", "list"]
    assert calls[1][0] == ["calendar", "events", "patch"]
