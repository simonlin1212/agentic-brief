"""Firestore persistence for generated briefings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

from google.cloud import firestore

from agentic_brief.config import GOOGLE_CLOUD_PROJECT
from agentic_brief.pipeline import BriefingResult


class ClaimStatus(StrEnum):
    """Outcome of an atomic scheduled-execution claim."""

    ACQUIRED = "acquired"
    RUNNING = "running"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class ExecutionClaim:
    """A claim status plus the fencing token for its current owner."""

    status: ClaimStatus
    token: str | None = None


class ClaimOwnershipError(RuntimeError):
    """Raised when a stale worker tries to persist another owner's execution."""


class BriefStore(Protocol):
    """Storage contract shared by the web viewer and scheduled runner."""

    def claim(self, execution_key: str) -> ExecutionClaim:
        """Atomically claim a scheduled period before model work begins."""

    def release_claim(self, execution_key: str, claim_token: str) -> bool:
        """Release a failed period so Cloud Scheduler may retry it."""

    def save(
        self,
        result: BriefingResult,
        execution_key: str | None = None,
        claim_token: str | None = None,
    ) -> None:
        """Persist one completed run and make it the latest briefing."""

    def get_latest(self) -> dict[str, Any] | None:
        """Return the newest briefing, or None before the first run."""


class FirestoreBriefStore:
    """Store immutable runs plus a small pointer to the latest one."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client or firestore.Client(project=GOOGLE_CLOUD_PROJECT or None)

    def claim(self, execution_key: str) -> ExecutionClaim:
        """Claim a period with a lease so duplicate delivery does no model work."""
        claim_ref = self._client.collection("executions").document(execution_key)
        now = datetime.now(UTC)
        lease_until = now + timedelta(minutes=15)
        claim_token = uuid4().hex

        @firestore.transactional
        def claim_in_transaction(transaction) -> ExecutionClaim:
            snapshot = claim_ref.get(transaction=transaction)
            data = snapshot.to_dict() or {} if snapshot.exists else {}
            current_lease = data.get("lease_until")
            if isinstance(current_lease, datetime) and current_lease.tzinfo is None:
                current_lease = current_lease.replace(tzinfo=UTC)
            if data.get("status") == "completed":
                return ExecutionClaim(ClaimStatus.COMPLETED)
            if (
                data.get("status") == "running"
                and isinstance(current_lease, datetime)
                and current_lease > now
            ):
                return ExecutionClaim(ClaimStatus.RUNNING)
            transaction.set(
                claim_ref,
                {
                    "status": "running",
                    "claim_token": claim_token,
                    "started_at": now,
                    "lease_until": lease_until,
                },
            )
            return ExecutionClaim(ClaimStatus.ACQUIRED, claim_token)

        return claim_in_transaction(self._client.transaction())

    def release_claim(self, execution_key: str, claim_token: str) -> bool:
        """Release a failed claim only if this worker still owns it."""
        claim_ref = self._client.collection("executions").document(execution_key)

        @firestore.transactional
        def release_in_transaction(transaction) -> bool:
            snapshot = claim_ref.get(transaction=transaction)
            data = snapshot.to_dict() or {} if snapshot.exists else {}
            if (
                data.get("status") != "running"
                or data.get("claim_token") != claim_token
            ):
                return False
            transaction.delete(claim_ref)
            return True

        return release_in_transaction(self._client.transaction())

    def save(
        self,
        result: BriefingResult,
        execution_key: str | None = None,
        claim_token: str | None = None,
    ) -> None:
        """Atomically write the run, latest pointer, and completed claim."""
        document = result.to_document()
        run_ref = self._client.collection("briefings").document(result.run_id)
        latest_ref = self._client.collection("metadata").document("latest")
        if execution_key is not None:
            if claim_token is None:
                raise ValueError("claim_token is required for a scheduled save")
            execution_ref = self._client.collection("executions").document(
                execution_key
            )

            @firestore.transactional
            def save_in_transaction(transaction) -> None:
                snapshot = execution_ref.get(transaction=transaction)
                data = snapshot.to_dict() or {} if snapshot.exists else {}
                if (
                    data.get("status") != "running"
                    or data.get("claim_token") != claim_token
                ):
                    raise ClaimOwnershipError(
                        "scheduled execution is no longer owned by this worker"
                    )
                transaction.set(run_ref, document)
                transaction.set(
                    latest_ref,
                    {"run_id": result.run_id, "updated_at": result.generated_at},
                )
                transaction.set(
                    execution_ref,
                    {
                        "status": "completed",
                        "run_id": result.run_id,
                        "completed_at": result.generated_at,
                    },
                )

            save_in_transaction(self._client.transaction())
            return

        batch = self._client.batch()
        batch.set(run_ref, document)
        batch.set(
            latest_ref,
            {"run_id": result.run_id, "updated_at": result.generated_at},
        )
        batch.commit()

    def get_latest(self) -> dict[str, Any] | None:
        """Resolve the latest pointer without requiring a query index."""
        pointer = self._client.collection("metadata").document("latest").get()
        if not pointer.exists:
            return None
        pointer_data = pointer.to_dict() or {}
        run_id = pointer_data.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            return None
        snapshot = self._client.collection("briefings").document(run_id).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict()
