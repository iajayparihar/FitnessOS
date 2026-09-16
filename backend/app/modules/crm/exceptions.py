from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError


class LeadNotFound(NotFoundError):
    message = "Lead not found."


class LeadSourceNotFound(NotFoundError):
    message = "Lead source not found."


class LeadSourceConflict(ConflictError):
    message = "A lead source with this name already exists."


class LeadAlreadyConverted(BusinessRuleError):
    code = "LEAD_ALREADY_CONVERTED"
    message = "This lead has already been converted."


class FollowUpNotFound(NotFoundError):
    message = "Follow-up not found."


class FollowUpAlreadyCompleted(BusinessRuleError):
    code = "FOLLOW_UP_ALREADY_COMPLETED"
    message = "This follow-up is already completed."
