from pathlib import Path


def test_telegram_polling_startup_preserves_pending_updates():
    source = Path("gateway/platforms/telegram.py").read_text(encoding="utf-8")
    polling_call = source.rsplit("await self._app.updater.start_polling(", 1)[1].split(")", 1)[0]

    assert "drop_pending_updates=False" in polling_call
    assert "drop_pending_updates=True" not in polling_call
