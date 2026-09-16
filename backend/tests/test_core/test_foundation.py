from app.core.error_handlers import _STATUS_TO_CODE, _validation_details
from app.core.exceptions import (
    AppError,
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthenticatedError,
    ValidationError,
)
from app.core.schemas import page_meta


def test_app_error_subclasses_have_standard_codes():
    cases = {
        ValidationError: ("VALIDATION_ERROR", 400),
        UnauthenticatedError: ("UNAUTHENTICATED", 401),
        ForbiddenError: ("FORBIDDEN", 403),
        NotFoundError: ("NOT_FOUND", 404),
        ConflictError: ("CONFLICT", 409),
        BusinessRuleError: ("BUSINESS_RULE_VIOLATION", 422),
    }
    for error_cls, (code, status_code) in cases.items():
        exc = error_cls()
        assert exc.code == code
        assert exc.status_code == status_code
        assert isinstance(exc, AppError)


def test_app_error_allows_message_and_details_override():
    exc = NotFoundError("Lead not found.", details=[{"field": "id", "issue": "missing"}])
    assert exc.message == "Lead not found."
    assert exc.details == [{"field": "id", "issue": "missing"}]


def test_status_to_code_maps_common_statuses():
    assert _STATUS_TO_CODE[401] == "UNAUTHENTICATED"
    assert _STATUS_TO_CODE[403] == "FORBIDDEN"
    assert _STATUS_TO_CODE[404] == "NOT_FOUND"
    assert _STATUS_TO_CODE[429] == "RATE_LIMITED"


def test_validation_details_strips_body_and_joins_location():
    errors = [
        {"loc": ("body", "email"), "msg": "value is not a valid email", "type": "x"},
        {"loc": ("body", "organization", "name"), "msg": "field required", "type": "y"},
    ]
    details = _validation_details(errors)
    assert details == [
        {"field": "email", "issue": "value is not a valid email"},
        {"field": "organization.name", "issue": "field required"},
    ]


def test_page_meta_computes_total_pages():
    meta = page_meta(total=45, page=2, page_size=20)
    assert meta.total == 45
    assert meta.total_pages == 3
    assert page_meta(total=0, page=1, page_size=20).total_pages == 0
