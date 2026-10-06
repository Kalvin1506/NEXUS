from typing import Any
from .base import AIProvider

class DemoProvider(AIProvider):
    """Pass-through provider. It never performs external calls."""
    name="local";model="deterministic"
    def normalize_ticket(self,ticket):return ticket.get("local_normalized",{})
    def extract_ticket_fields(self,ticket):return ticket.get("local_extracted",{})
    def classify_ticket(self,ticket):return ticket.get("local_classification",{})
    def summarize_cases(self,evidence):return evidence.get("local_summary",{})
    def draft_grounded_resolution(self,evidence):return evidence.get("local_resolution",{})
    def suggest_investigation_steps(self,ticket):return ticket.get("local_investigation",{})
    def generate_explanation(self,evidence):return evidence.get("local_explanation",{})
    def generate_handover(self,evidence):return evidence.get("local_handover",{})
    def generate_kb_draft(self,evidence):return evidence.get("local_kb_draft",{})

