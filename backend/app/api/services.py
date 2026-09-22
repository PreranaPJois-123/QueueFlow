from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_staff
from app.models.models import Service, User
from app.schemas.schemas import ServiceCreate, ServiceUpdate, ServiceOut

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("", response_model=list[ServiceOut])
def list_services(active_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(Service)
    if active_only:
        q = q.filter(Service.is_active.is_(True))
    return q.order_by(Service.name.asc()).all()


@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_staff)):
    service = Service(name=payload.name, description=payload.description, created_by=current_user.id)
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("/{service_id}", response_model=ServiceOut)
def get_service(service_id: str, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    return service


@router.patch("/{service_id}", response_model=ServiceOut)
def update_service(service_id: str, payload: ServiceUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_staff)):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    db.commit()
    db.refresh(service)
    return service
