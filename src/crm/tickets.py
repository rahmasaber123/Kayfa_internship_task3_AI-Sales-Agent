"""Save tickets to MongoDB. Generates human-readable ticket IDs."""
from datetime import datetime, timezone
from src.config import COL_TICKETS
from src.memory.mongo import get_db
from src.crm.schemas import Ticket, LeadData, EscalationData, Contact


def _next_ticket_id(ticket_type: str) -> str:
    """LEAD-2026-0001 / ESC-2026-0001 — monotonic per type per year."""
    db = get_db()
    year = datetime.now(timezone.utc).year
    prefix = {"lead": "LEAD", "escalation": "ESC",
              "complaint": "CPL", "abuse": "ABS"}[ticket_type]
    pattern = f"^{prefix}-{year}-"
    last = db[COL_TICKETS].find_one(
        {"ticket_id": {"$regex": pattern}},
        sort=[("ticket_id", -1)],
    )
    if last:
        n = int(last["ticket_id"].split("-")[-1]) + 1
    else:
        n = 1
    return f"{prefix}-{year}-{n:04d}"


def save_lead_ticket(
    *,
    session_id: str,
    language: str,
    dialect: str | None,
    contact: dict,
    summary_ar: str,
    next_action_ar: str,
    recommendation: str | None = None,
    temperature: str = "warm",
    products_of_interest: list[str] | None = None,
    goal: str | None = None,
    current_level: str | None = None,
    buying_signals: list[str] | None = None,
    objections_raised: list[str] | None = None,
) -> str:
    """Insert a lead ticket. Returns the ticket_id."""
    ticket = Ticket(
        ticket_id=_next_ticket_id("lead"),
        type="lead",
        session_id=session_id,
        language=language,
        dialect=dialect,
        contact=Contact(**contact),
        summary_ar=summary_ar,
        next_action_ar=next_action_ar,
        recommendation=recommendation,
        priority="high" if temperature == "hot" else "medium",
        lead_data=LeadData(
            temperature=temperature,
            products_of_interest=products_of_interest or [],
            goal=goal,
            current_level=current_level,
            buying_signals=buying_signals or [],
            objections_raised=objections_raised or [],
        ),
    )
    get_db()[COL_TICKETS].insert_one(ticket.model_dump(mode="json"))
    return ticket.ticket_id


def save_escalation_ticket(
    *,
    session_id: str,
    language: str,
    dialect: str | None,
    contact: dict,
    reason: str,
    summary_ar: str,
    next_action_ar: str,
    recommendation: str | None = None,
    agent_confidence: float = 0.5,
) -> str:
    """Insert an escalation ticket. Returns the ticket_id."""
    ticket = Ticket(
        ticket_id=_next_ticket_id("escalation"),
        type="escalation",
        session_id=session_id,
        language=language,
        dialect=dialect,
        contact=Contact(**contact),
        summary_ar=summary_ar,
        next_action_ar=next_action_ar,
        recommendation=recommendation,
        priority="high",
        escalation_data=EscalationData(reason=reason, agent_confidence=agent_confidence),
    )
    get_db()[COL_TICKETS].insert_one(ticket.model_dump(mode="json"))
    return ticket.ticket_id
