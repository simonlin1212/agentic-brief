"""Tests for Firestore persistence."""

from datetime import UTC, datetime, timedelta

import pytest

from agentic_brief import store as store_module
from agentic_brief.pipeline import BriefingResult
from agentic_brief.store import (
    ClaimOwnershipError,
    ClaimStatus,
    FirestoreBriefStore,
)


class FakeSnapshot:
    def __init__(self, value: dict | None) -> None:
        self.exists = value is not None
        self._value = value

    def to_dict(self) -> dict | None:
        return self._value


class FakeDocument:
    def __init__(self, database: dict[str, dict], path: str) -> None:
        self.database = database
        self.path = path

    def get(self, **_kwargs) -> FakeSnapshot:
        return FakeSnapshot(self.database.get(self.path))

    def delete(self) -> None:
        self.database.pop(self.path, None)


class FakeCollection:
    def __init__(self, database: dict[str, dict], name: str) -> None:
        self.database = database
        self.name = name

    def document(self, document_id: str) -> FakeDocument:
        return FakeDocument(self.database, f"{self.name}/{document_id}")


class FakeBatch:
    def __init__(self, database: dict[str, dict]) -> None:
        self.database = database
        self.pending: list[tuple[str, dict]] = []

    def set(self, document: FakeDocument, value: dict) -> None:
        self.pending.append((document.path, value))

    def commit(self) -> None:
        self.database.update(self.pending)


class FakeTransaction:
    def __init__(self, database: dict[str, dict]) -> None:
        self.database = database

    def set(self, document: FakeDocument, value: dict) -> None:
        self.database[document.path] = value

    def delete(self, document: FakeDocument) -> None:
        self.database.pop(document.path, None)


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.database: dict[str, dict] = {}

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self.database, name)

    def batch(self) -> FakeBatch:
        return FakeBatch(self.database)

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self.database)


def sample_result() -> BriefingResult:
    return BriefingResult(
        run_id="20260828T010203000000Z",
        generated_at=datetime(2026, 8, 28, 1, 2, 3, tzinfo=UTC),
        daily_brief="TOP SIGNALS\nSoftware",
        news_findings="[]",
        video_findings="[]",
    )


def test_save_and_read_latest_briefing(monkeypatch) -> None:
    monkeypatch.setattr(
        store_module.firestore, "transactional", lambda function: function
    )
    client = FakeFirestoreClient()
    store = FirestoreBriefStore(client=client)

    claim = store.claim("2026-08-28")
    assert claim.token is not None
    store.save(
        sample_result(), execution_key="2026-08-28", claim_token=claim.token
    )

    latest = store.get_latest()
    assert latest is not None
    assert latest["run_id"] == "20260828T010203000000Z"
    assert latest["daily_brief"] == "TOP SIGNALS\nSoftware"
    assert client.database["metadata/latest"]["run_id"] == latest["run_id"]
    assert client.database["executions/2026-08-28"]["status"] == "completed"


def test_get_latest_returns_none_before_first_run() -> None:
    store = FirestoreBriefStore(client=FakeFirestoreClient())

    assert store.get_latest() is None


def test_claim_is_atomic_and_rejects_an_active_duplicate(monkeypatch) -> None:
    monkeypatch.setattr(
        store_module.firestore, "transactional", lambda function: function
    )
    client = FakeFirestoreClient()
    store = FirestoreBriefStore(client=client)

    first_claim = store.claim("2026-08-28")
    assert first_claim.status == ClaimStatus.ACQUIRED
    assert first_claim.token
    assert store.claim("2026-08-28").status == ClaimStatus.RUNNING
    assert client.database["executions/2026-08-28"]["status"] == "running"


def test_release_claim_allows_a_failed_period_to_retry(monkeypatch) -> None:
    monkeypatch.setattr(
        store_module.firestore, "transactional", lambda function: function
    )
    client = FakeFirestoreClient()
    store = FirestoreBriefStore(client=client)
    claim = store.claim("2026-08-28")
    assert claim.status == ClaimStatus.ACQUIRED
    assert claim.token is not None

    assert store.release_claim("2026-08-28", claim.token) is True

    assert store.claim("2026-08-28").status == ClaimStatus.ACQUIRED


def test_claim_reports_completed_period(monkeypatch) -> None:
    monkeypatch.setattr(
        store_module.firestore, "transactional", lambda function: function
    )
    client = FakeFirestoreClient()
    store = FirestoreBriefStore(client=client)
    claim = store.claim("2026-08-28")
    assert claim.token is not None
    store.save(
        sample_result(), execution_key="2026-08-28", claim_token=claim.token
    )

    assert store.claim("2026-08-28").status == ClaimStatus.COMPLETED


def test_stale_worker_cannot_release_or_save_reclaimed_execution(monkeypatch) -> None:
    monkeypatch.setattr(
        store_module.firestore, "transactional", lambda function: function
    )
    client = FakeFirestoreClient()
    store = FirestoreBriefStore(client=client)
    stale_claim = store.claim("2026-08-28")
    assert stale_claim.token is not None
    client.database["executions/2026-08-28"]["lease_until"] = datetime.now(
        UTC
    ) - timedelta(seconds=1)

    replacement_claim = store.claim("2026-08-28")

    assert replacement_claim.status == ClaimStatus.ACQUIRED
    assert replacement_claim.token is not None
    assert replacement_claim.token != stale_claim.token
    assert store.release_claim("2026-08-28", stale_claim.token) is False
    with pytest.raises(ClaimOwnershipError):
        store.save(
            sample_result(),
            execution_key="2026-08-28",
            claim_token=stale_claim.token,
        )
    assert "briefings/20260828T010203000000Z" not in client.database
    assert (
        client.database["executions/2026-08-28"]["claim_token"]
        == replacement_claim.token
    )
