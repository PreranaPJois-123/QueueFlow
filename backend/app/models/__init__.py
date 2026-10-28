"""Import every model module so Base.metadata is complete for Alembic and tests."""
from app.models import models, venues, assistant  # noqa: F401
