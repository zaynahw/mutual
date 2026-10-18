"""Internal proposal storage; services validate and authorize plans.

Initialize the database first. These functions do not validate a plan against
availability, establish caller identity, or approve/create calendar events.
"""
from backend.database import connect
from backend.models import Proposal


def create_proposal(proposal: Proposal) -> None:
    """Insert only; initial state must be pending. Integrity errors propagate."""
    if proposal.status != "pending":
        raise ValueError("New proposals must be pending")
    with connect() as connection:
        connection.execute(
            "INSERT INTO proposals (id, request_id, data) VALUES (?, ?, ?)",
            (proposal.id, proposal.request_id, proposal.model_dump_json()),
        )


def get_proposal(proposal_id: str) -> Proposal | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT data FROM proposals WHERE id = ?", (proposal_id,),
        ).fetchone()
    if row is None:
        return None
    return Proposal.model_validate_json(row["data"])


def list_proposals_for_request(request_id: str) -> list[Proposal]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT data FROM proposals WHERE request_id = ? ORDER BY id", (request_id,),
        ).fetchall()
    return [Proposal.model_validate_json(row["data"]) for row in rows]
