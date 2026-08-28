"""Tests for the public web viewer and private scheduled runner."""

from datetime import UTC, datetime

from agentic_brief.pipeline import BriefingResult
from agentic_brief.service import create_app
from agentic_brief.store import ClaimStatus, ExecutionClaim


class FakeStore:
    def __init__(
        self,
        latest: dict | None = None,
        claim_result: ExecutionClaim | None = None,
    ) -> None:
        self.latest = latest
        self.claim_result = claim_result or ExecutionClaim(
            ClaimStatus.ACQUIRED, "claim-token"
        )
        self.claimed: list[str] = []
        self.released: list[str] = []
        self.saved: list[BriefingResult] = []
        self.saved_keys: list[str | None] = []
        self.saved_tokens: list[str | None] = []

    def get_latest(self) -> dict | None:
        return self.latest

    def claim(self, execution_key: str) -> ExecutionClaim:
        self.claimed.append(execution_key)
        return self.claim_result

    def release_claim(self, execution_key: str, _claim_token: str) -> bool:
        self.released.append(execution_key)
        return True

    def save(
        self,
        result: BriefingResult,
        execution_key: str | None = None,
        claim_token: str | None = None,
    ) -> None:
        self.saved.append(result)
        self.saved_keys.append(execution_key)
        self.saved_tokens.append(claim_token)


def sample_result() -> BriefingResult:
    return BriefingResult(
        run_id="20260828T010203000000Z",
        generated_at=datetime(2026, 8, 28, 1, 2, 3, tzinfo=UTC),
        daily_brief="TOP SIGNALS\nSoftware",
        news_findings="[]",
        video_findings="[]",
    )


def test_public_home_shows_waiting_state() -> None:
    client = create_app(mode="web", store=FakeStore()).test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"first autonomous run" in response.data
    assert client.post("/run").status_code == 404


def test_public_home_escapes_generated_content() -> None:
    latest = sample_result().to_document()
    latest["daily_brief"] = "<script>alert(1)</script>"
    client = create_app(mode="web", store=FakeStore(latest)).test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"<script>" not in response.data
    assert b"&lt;script&gt;" in response.data


def test_public_home_removes_executable_markdown_urls_and_images() -> None:
    latest = sample_result().to_document()
    latest["daily_brief"] = (
        "[unsafe](javascript:alert(document.domain)) "
        "![pixel](https://attacker.example/pixel.png) "
        "[safe](https://example.com/report)"
    )
    client = create_app(mode="web", store=FakeStore(latest)).test_client()

    response = client.get("/")

    assert b"javascript:" not in response.data
    assert b"<img" not in response.data
    assert b'href="https://example.com/report"' in response.data


def test_public_home_renders_safe_markdown_as_formatted_html() -> None:
    latest = sample_result().to_document()
    latest["daily_brief"] = (
        "### TOP SIGNALS\n\n"
        "1. **Software** led the session.\n"
        "   * **News Scout:** Earnings accelerated."
    )
    client = create_app(mode="web", store=FakeStore(latest)).test_client()

    response = client.get("/")

    assert b"<h3>TOP SIGNALS</h3>" in response.data
    assert b"<strong>Software</strong>" in response.data
    assert b"<ul>" in response.data
    assert b"<strong>News Scout:</strong> Earnings accelerated." in response.data
    assert b"### TOP SIGNALS" not in response.data


def test_latest_api_returns_saved_document() -> None:
    latest = sample_result().to_document()
    client = create_app(mode="web", store=FakeStore(latest)).test_client()

    response = client.get("/api/latest")

    assert response.status_code == 200
    assert response.get_json()["run_id"] == latest["run_id"]


def test_private_runner_generates_and_persists_briefing() -> None:
    store = FakeStore()
    result = sample_result()

    async def fake_generate() -> BriefingResult:
        return result

    client = create_app(
        mode="runner",
        store=store,
        brief_generator=fake_generate,
        execution_key_factory=lambda: "2026-08-28",
    ).test_client()

    response = client.post("/run")

    assert response.status_code == 201
    assert response.get_json() == {"run_id": result.run_id, "status": "completed"}
    assert store.saved == [result]
    assert store.claimed == ["2026-08-28"]
    assert store.saved_keys == ["2026-08-28"]
    assert store.saved_tokens == ["claim-token"]
    assert client.get("/").status_code == 404


def test_completed_scheduled_delivery_skips_model_generation() -> None:
    store = FakeStore(claim_result=ExecutionClaim(ClaimStatus.COMPLETED))
    generated = False

    async def fake_generate() -> BriefingResult:
        nonlocal generated
        generated = True
        return sample_result()

    client = create_app(
        mode="runner",
        store=store,
        brief_generator=fake_generate,
        execution_key_factory=lambda: "2026-08-28",
    ).test_client()

    response = client.post("/run")

    assert response.status_code == 200
    assert response.get_json() == {
        "execution_key": "2026-08-28",
        "status": "already_completed",
    }
    assert generated is False
    assert store.saved == []


def test_active_scheduled_delivery_requests_a_delayed_retry() -> None:
    store = FakeStore(claim_result=ExecutionClaim(ClaimStatus.RUNNING))

    async def should_not_generate() -> BriefingResult:
        raise AssertionError("active duplicate must not generate")

    client = create_app(
        mode="runner",
        store=store,
        brief_generator=should_not_generate,
        execution_key_factory=lambda: "2026-08-28",
    ).test_client()

    response = client.post("/run")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "900"
    assert response.get_json() == {
        "execution_key": "2026-08-28",
        "status": "already_running",
    }
    assert store.saved == []


def test_runner_returns_generic_error_without_internal_details() -> None:
    async def broken_generate() -> BriefingResult:
        raise RuntimeError("secret internal detail")

    client = create_app(
        mode="runner",
        store=(store := FakeStore()),
        brief_generator=broken_generate,
        execution_key_factory=lambda: "2026-08-28",
    ).test_client()

    response = client.post("/run")

    assert response.status_code == 500
    assert response.get_json() == {"status": "failed"}
    assert b"secret internal detail" not in response.data
    assert store.released == ["2026-08-28"]


def test_health_endpoint_is_available_in_both_modes() -> None:
    for mode in ("web", "runner"):
        response = create_app(mode=mode, store=FakeStore()).test_client().get("/health")
        assert response.get_json() == {"service": mode, "status": "ok"}


def test_invalid_service_mode_fails_fast() -> None:
    try:
        create_app(mode="chatbot", store=FakeStore())
    except RuntimeError as exc:
        assert "SERVICE_MODE" in str(exc)
    else:
        raise AssertionError("invalid mode should fail")
