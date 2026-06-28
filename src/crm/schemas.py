from datetime import datetime, timezone
from typing import Literal, Annotated
from pydantic import BaseModel, Field, model_validator

# Types
TicketType = Literal["lead", "escalation", "complaint", "abuse"]
Temperature = Literal["cold", "warm", "hot"]
Status = Literal["new", "assigned", "contacted", "closed"]

class Contact(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    country: str | None = None
    preferred_channel: str | None = None
    best_contact_time: str | None = None

class LeadData(BaseModel):
    # Kept for backward compatibility
    temperature: Temperature = "warm" 
    products_of_interest: list[str] = Field(default_factory=list)
    goal: str | None = None
    current_level: str | None = None
    buying_signals: list[str] = Field(default_factory=list)
    objections_raised: list[str] = Field(default_factory=list)

class EscalationData(BaseModel):
    reason: str
    agent_confidence: float = Field(default=0.5, ge=0.0, le=1.0)

class ComplaintData(BaseModel):
    category: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    is_resolved: bool = False

class AbuseData(BaseModel):
    violation_type: str
    is_flagged_for_review: bool = True

class Ticket(BaseModel):
    """Unified ticket with type-safe data blocks."""
    ticket_id: str
    type: TicketType
    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Status = "new"
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    
    # TEMPERATURE MOVED HERE: Available for all ticket types
    temperature: Temperature = "warm" 
    
    language: str = "ar"
    dialect: str | None = None
    contact: Contact = Field(default_factory=Contact)
    
    # Arabic content
    summary_ar: str
    next_action_ar: str
    recommendation: str | None = None
    
    # Data blocks (optional, populated based on type)
    lead_data: LeadData | None = None
    escalation_data: EscalationData | None = None
    complaint_data: ComplaintData | None = None
    abuse_data: AbuseData | None = None
    
    assigned_to: str | None = None

    @model_validator(mode='after')
    def validate_data_block(self) -> 'Ticket':
        """Ensure that the data block matching the type is present."""
        if self.type == "lead" and not self.lead_data:
            self.lead_data = LeadData()
        elif self.type == "escalation" and not self.escalation_data:
            raise ValueError("escalation_data is required for escalation tickets")
        elif self.type == "complaint" and not self.complaint_data:
            raise ValueError("complaint_data is required for complaint tickets")
        elif self.type == "abuse" and not self.abuse_data:
            raise ValueError("abuse_data is required for abuse tickets")
        return self