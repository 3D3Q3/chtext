"""Tests for chtext core logic. All network access is mocked."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from chtext.cli import (
    Config,
    CTextAPI,
    CtextAPIError,
    CtextAuthError,
    StateTracker,
    _extract_short_segments,
    __version__,
)


# --- helpers -----------------------------------------------------------------

def make_response(payload=None, text=None, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text if text is not None else json.dumps(payload)
    if payload is not None:
        resp.json.return_value = payload
    else:
        resp.json.side_effect = ValueError("not json")
    resp.raise_for_status.return_value = None
    return resp


# --- CTextAPI ----------------------------------------------------------------

class TestCTextAPI:
    def test_call_success(self):
        api = CTextAPI()
        api.session = MagicMock()
        api.session.get.return_value = make_response({"fulltext": ["道可道"]})
        assert api.gettext("ctp:dao-de-jing") == {"fulltext": ["道可道"]}

    def test_call_passes_apikey(self):
        api = CTextAPI()
        api.setapikey("SECRET")
        api.session = MagicMock()
        api.session.get.return_value = make_response({"ok": True})
        api.gettext("ctp:analects")
        _, kwargs = api.session.get.call_args
        assert kwargs["params"]["apikey"] == "SECRET"

    def test_empty_response_raises(self):
        api = CTextAPI()
        api.session = MagicMock()
        api.session.get.return_value = make_response(text="   ")
        with pytest.raises(CtextAPIError, match="Empty response"):
            api.getstatus()

    def test_non_json_response_raises_clean_error(self):
        api = CTextAPI()
        api.session = MagicMock()
        api.session.get.return_value = make_response(text="<html>502</html>")
        with pytest.raises(CtextAPIError, match="non-JSON"):
            api.getstatus()

    def test_network_error_wrapped(self):
        import requests

        api = CTextAPI()
        api.session = MagicMock()
        api.session.get.side_effect = requests.ConnectionError("boom")
        with pytest.raises(CtextAPIError, match="Network error"):
            api.getstatus()

    def test_auth_error_detected(self):
        api = CTextAPI()
        api.session = MagicMock()
        api.session.get.return_value = make_response(
            {"error": {"code": "AUTHENTICATION_REQUIRED", "description": "key needed"}}
        )
        with pytest.raises(CtextAuthError):
            api.gettext("ctp:zhuangzi")

    def test_generic_api_error(self):
        api = CTextAPI()
        api.session = MagicMock()
        api.session.get.return_value = make_response(
            {"error": {"code": "BAD_URN", "description": "unknown"}}
        )
        with pytest.raises(CtextAPIError, match="BAD_URN"):
            api.gettext("ctp:nope")

    def test_gettextasstring_recurses_subsections(self):
        api = CTextAPI()
        responses = {
            "ctp:book": {"subsections": ["ctp:book/ch1", "ctp:book/ch2"]},
            "ctp:book/ch1": {"fulltext": ["甲"]},
            "ctp:book/ch2": {"fulltext": ["乙", "丙"]},
        }
        api.gettext = lambda urn: responses[urn]
        assert api.gettextasstring("ctp:book") == "甲\n\n乙\n\n丙\n\n"

    def test_gettextasparagraphlist_strips_trailing_blank(self):
        api = CTextAPI()
        api.gettextasstring = lambda urn: "甲\n\n乙\n\n"
        assert api.gettextasparagraphlist("x") == ["甲", "乙"]


# --- StateTracker ------------------------------------------------------------

class TestStateTracker:
    def test_mark_and_check_seen(self, tmp_path):
        db = StateTracker(db_path=str(tmp_path / "t.sqlite"))
        assert not db.is_seen("abc")
        db.mark_seen("abc", "ctp:analects", "ctp:analects/xue-er", "學而")
        assert db.is_seen("abc")

    def test_duplicate_mark_is_idempotent(self, tmp_path):
        db = StateTracker(db_path=str(tmp_path / "t.sqlite"))
        db.mark_seen("abc")
        db.mark_seen("abc")  # must not raise
        assert db.is_seen("abc")

    def test_stats_counts(self, tmp_path):
        db = StateTracker(db_path=str(tmp_path / "t.sqlite"))
        db.mark_seen("a", "ctp:analects")
        db.mark_seen("b", "ctp:analects")
        db.mark_seen("c", "ctp:mozi")
        stats = db.get_stats()
        assert stats["total"] == 3
        assert dict(stats["by_book"]).get("ctp:analects") == 2

    def test_reset_clears(self, tmp_path):
        db = StateTracker(db_path=str(tmp_path / "t.sqlite"))
        db.mark_seen("a")
        db.reset()
        assert not db.is_seen("a")

    def test_default_path_not_cwd(self, tmp_path, monkeypatch):
        """Regression: v1.0.0 wrote the DB into the current working directory."""
        monkeypatch.chdir(tmp_path)
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
        import chtext.cli as cli

        monkeypatch.setattr(cli, "DATA_DIR", fake_home / ".chtext")
        monkeypatch.setattr(cli, "DB_FILE", str(fake_home / ".chtext" / "seen_ids.sqlite"))
        db = StateTracker(db_path=cli.DB_FILE)
        db.mark_seen("x")
        assert not (tmp_path / "seen_ids.sqlite").exists()
        assert (fake_home / ".chtext" / "seen_ids.sqlite").exists()


# --- _extract_short_segments ---------------------------------------------------

class TestExtractShortSegments:
    def test_splits_on_chinese_punctuation(self):
        para = "道可道，非常道。名可名，非常名。"
        segs = _extract_short_segments([para], max_chars=80)
        texts = [s[1] if isinstance(s, tuple) else s for s in segs]
        assert any("道可道" in t for t in texts)
        assert all(len(t) <= 81 for t in texts)

    def test_filters_long_segments(self):
        long_sentence = "很" * 200 + "。"
        segs = _extract_short_segments([long_sentence], max_chars=80)
        assert segs == []

    def test_empty_input(self):
        assert _extract_short_segments([]) == []


# --- Config --------------------------------------------------------------------

class TestConfig:
    def test_defaults_when_missing(self, tmp_path):
        cfg = Config(config_path=tmp_path / "nope.json")
        assert cfg.get("language") == "en"
        assert cfg.get("api_key") is None

    def test_set_persists(self, tmp_path):
        path = tmp_path / "c.json"
        Config(config_path=path).set("api_key", "K")
        assert Config(config_path=path).get("api_key") == "K"

    def test_corrupt_file_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text("{not json", encoding="utf-8")
        assert Config(config_path=path).get("language") == "en"


def test_version_is_current():
    assert __version__ == "1.1.0"
