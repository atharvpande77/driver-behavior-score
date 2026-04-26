from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    Float,
    Numeric,
    SmallInteger,
    String,
    UUID,
    TIMESTAMP,
    DATE,
    text,
    Text,
    
    ForeignKey,
    UniqueConstraint,
    Index,
    func
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)
from datetime import date, datetime
import uuid

from src.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"
    
    # Vehicle info
    vehicle_number: Mapped[str] = mapped_column(String(16), primary_key=True)
    state_code: Mapped[str | None] = mapped_column(String(2))
    source_id: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str | None] = mapped_column(String(32))
    category_description: Mapped[str | None] = mapped_column(String(255))
    chassis_number: Mapped[str | None] = mapped_column(String(32))
    engine_number: Mapped[str | None] = mapped_column(String(32))
    maker_description: Mapped[str | None] = mapped_column(String(128))
    maker_model: Mapped[str | None] = mapped_column(String)
    fit_up_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    manufacturing_date: Mapped[str | None] = mapped_column(String(32))
    registration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    registered_at: Mapped[str | None] = mapped_column(String(128), comment="Place of registration")
    body_type: Mapped[str | None] = mapped_column(String(64))
    fuel_type: Mapped[str | None] = mapped_column(String(64))
    norms_type: Mapped[str | None] = mapped_column(String(64))
    color: Mapped[str | None] = mapped_column(String(64))
    cubic_capacity: Mapped[float | None] = mapped_column(Numeric(10, 2))
    vehicle_gross_weight: Mapped[int | None] = mapped_column(Integer)
    no_cylinders: Mapped[int | None] = mapped_column(SmallInteger)
    seat_capacity: Mapped[int | None] = mapped_column(SmallInteger)
    sleeper_capacity: Mapped[int | None] = mapped_column(SmallInteger)
    standing_capacity: Mapped[int | None] = mapped_column(SmallInteger)
    wheelbase: Mapped[int | None] = mapped_column(Integer)
    unladen_weight: Mapped[int | None] = mapped_column(Integer)
    
    # Owner info
    owner_name: Mapped[str | None] = mapped_column(String(255))
    present_address: Mapped[str | None] = mapped_column(String(512))
    permanent_address: Mapped[str | None] = mapped_column(String(512))
    mobile_number: Mapped[str | None] = mapped_column(String(20))


    financer: Mapped[str | None] = mapped_column(String(128))
    financed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        init=False,
        server_default=text("false"),
    )
    insurance_company: Mapped[str | None] = mapped_column(String(128))
    insurance_policy_number: Mapped[str | None] = mapped_column(String(64))
    pucc_number: Mapped[str | None] = mapped_column(String(64))
    pucc_upto: Mapped[Date | None] = mapped_column(Date, nullable=True)
    permit_number: Mapped[str | None] = mapped_column(String(64))
    permit_issue_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    permit_type: Mapped[str | None] = mapped_column(String(128))
    national_permit_number: Mapped[str | None] = mapped_column(String(64))
    national_permit_issued_by: Mapped[str | None] = mapped_column(String(128))
    blacklist_status: Mapped[str | None] = mapped_column(Text)
    noc_details: Mapped[str | None] = mapped_column(String(256))
    owner_number: Mapped[int | None] = mapped_column(SmallInteger)
    rc_status: Mapped[str | None] = mapped_column(String(64))
    rto_code: Mapped[str | None] = mapped_column(String(16))
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, init=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, init=False, onupdate=func.now())
    
    __table_args__ = (
        Index("ix_vehicles_state_code", "state_code"),
    )
    
    def __repr__(self) -> str:
        return f"<Vehicle {self.rc_number} {self.category}>"

    
class Challan(Base):
    __tablename__ = "challans"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        init=False,
        server_default=text("gen_random_uuid()"),
    )
    
    vehicle_number: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    
    challan_number: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64))
    
    offense_details: Mapped[str] = mapped_column(String(256))
    
    thz_category: Mapped[str] = mapped_column(String(8))
    thz_description: Mapped[str] = mapped_column(String(256))
    thz_deduction: Mapped[int] = mapped_column(Integer)
    
    severity: Mapped[str] = mapped_column(String(16))
    
    challan_place: Mapped[str | None] = mapped_column(String(256))
    challan_datetime: Mapped[datetime] = mapped_column(TIMESTAMP)
    state_code: Mapped[str | None] = mapped_column(String(2))
    rto: Mapped[str | None] = mapped_column(String(64))
    accused_name: Mapped[str | None] = mapped_column(String(64))
    fine_amount: Mapped[int | None] = mapped_column(Integer)
    challan_status: Mapped[str | None] = mapped_column(String(64))
    court_challan: Mapped[bool] = mapped_column(Boolean)
    court_name: Mapped[str | None] = mapped_column(String(64))
    upstream_code: Mapped[str | None] = mapped_column(String(64))
    
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, init=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        init=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    removed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, init=False)
    
    __table_args__ = (
        UniqueConstraint('challan_number', 'source_id', name='_unique_challan_number'),
        Index("ix_challans_vehicle_date", "vehicle_number", "challan_datetime")
    )
    
    def __repr__(self) -> str:
        return (
            f"<Challan {self.challan_number} {self.vehicle_number} "
            f"{self.thz_category}>"
        )
    
    
class ChallansOffenseDetail(Base):
    __tablename__ = "challans_offense_details"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        init=False,
        server_default=text("gen_random_uuid()"),
    )
    
    challan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("challans.id"), nullable=False)
    
    offense_name: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        Index("ix_challan_offenses_challan_id", "challan_id"),
    )
 
    def __repr__(self) -> str:
        return f"<ChallanOffense challan={self.challan_id} offense={self.offense_name!r}>"
    
    
class ChallansFetchLog(Base):
    __tablename__ = "challans_fetch_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        init=False,
        server_default=text("gen_random_uuid()"),
    )
    
    vehicle_number: Mapped[str] = mapped_column(String(16), nullable=False)
    
    source_id: Mapped[str] = mapped_column(String(64))
    
    fetched_at: Mapped[datetime] = mapped_column(TIMESTAMP, init=False, server_default=func.now())
    
    response_duration_ms: Mapped[float] = mapped_column(Float)
    
    __table_args__ = (
        Index("ix_challan_fetch_logs_vehicle_fetched", "vehicle_number", "fetched_at"),
    )
    
    
class DBSRecord(Base):
    __tablename__ = "dbs_records"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        init=False,
        server_default=text("gen_random_uuid()"),
    )
    
    vehicle_number: Mapped[str] = mapped_column(String(16), nullable=False)
    
    score: Mapped[int] = mapped_column(Integer)
    total_deductions: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(16))
    premium_modifier_pct: Mapped[int] = mapped_column(Integer)
    
    total_violations: Mapped[int] = mapped_column(Integer)
    severe_violations: Mapped[int] = mapped_column(Integer)
    moderate_violations: Mapped[int] = mapped_column(Integer)
    low_violations: Mapped[int] = mapped_column(Integer)
    
    window_start: Mapped[date] = mapped_column(DATE, init=False)
    window_end: Mapped[date] = mapped_column(DATE, init=False)
        
    last_violation_datetime: Mapped[datetime | None] = mapped_column(TIMESTAMP, init=False)
    computed_at: Mapped[datetime] = mapped_column(TIMESTAMP, init=False, server_default=func.now())
    
    __table_args__ = (
        Index("ix_dbs_records_vehicle_computed", "vehicle_number", "computed_at"),
    )


class DashboardUser(Base):
    __tablename__ = "dashboard_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        init=False,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        init=False,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        Index("ix_dashboard_users_email", "email"),
    )


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        init=False,
        server_default=text("gen_random_uuid()"),
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dashboard_users.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        init=False,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_api_keys_created_by", "created_by"),
        Index("ix_api_keys_key_hash", "key_hash"),
    )
