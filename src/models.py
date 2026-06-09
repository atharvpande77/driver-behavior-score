from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    Float,
    Numeric,
    SmallInteger,
    BigInteger,
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
    

class UsageEvent(Base):
    __tablename__ = "usage_events"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        server_default=text("gen_random_uuid()"),
    )
    
    dashboard_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dashboard_users.id"),
        nullable=False,
    )
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id"),
        nullable=True,
    )
    auth_type: Mapped[str] = mapped_column(String(16), nullable=False) # Dashboard or API key
    
    endpoint: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(8))
    api_name: Mapped[str] = mapped_column(String(64))
    usage_type: Mapped[str] = mapped_column(String(8)) # Single or batch
    
    vehicle_number: Mapped[str] = mapped_column(String(16))
    risk_level: Mapped[str] = mapped_column(String(16))
    from_db_cache: Mapped[bool] = mapped_column(Boolean)
    challan_net_changes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    
    total_latency_ms: Mapped[float] = mapped_column(Float)
    vendor_challan_latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    vendor_rc_latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    
    is_success: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(64))
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    http_status_code: Mapped[int] = mapped_column(Integer)
    
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_usage_dashboard_user_created", dashboard_user_id, created_at.desc()),
        Index(
            "idx_usage_api_key_created",
            api_key_id,
            created_at.desc(),
            postgresql_where=text("api_key_id IS NOT NULL"),
        ),
        Index(
            "idx_usage_vehicle_number",
            vehicle_number,
            created_at.desc(),
            postgresql_where=text("vehicle_number IS NOT NULL"),
        ),
        Index("idx_usage_created", created_at.desc()),
    )


class TelematicsEvent(Base):
    __tablename__ = "telematics_events"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    raw_packet: Mapped[str] = mapped_column(Text)
    
    # DP packet fields
    header: Mapped[str] = mapped_column(String(8))
    vendor_id: Mapped[str] = mapped_column(String(16), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    packet_type: Mapped[str | None] = mapped_column(String(4), nullable=True)
    alert_id: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    packet_status: Mapped[str | None] = mapped_column(String(1), nullable=True, comment="L=Live, H=History")
    imei: Mapped[str | None] = mapped_column(String(15), nullable=True)
    vehicle_reg_no: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gps_fix: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    gps_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="Combined GPS date and time in UTC (DDMMYYYY + hhmmss)")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Signed decimal degrees, negative=South")
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Signed decimal degrees, negative=West")
    speed: Mapped[float | None] = mapped_column(Float, nullable=True, comment="km/h")
    heading: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Course over ground in degrees (0-359.99)")
    num_satellites: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    altitude: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Meters")
    pdop: Mapped[float | None] = mapped_column(Float, nullable=True)
    hdop: Mapped[float | None] = mapped_column(Float, nullable=True)
    operator_name: Mapped[str | None] = mapped_column(String(11), nullable=True)
    ignition: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    main_power_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True, comment="0=disconnected, 1=reconnected")
    main_input_voltage: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Volts (7.0-40.0)")
    internal_battery_voltage: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Volts (0-4.2)")
    emergency_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tamper_alert: Mapped[str | None] = mapped_column(String(1), nullable=True, comment="C=Closed, O=Open")
    gsm_signal_strength: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, comment="0-31")
    mcc: Mapped[str | None] = mapped_column(String(4), nullable=True)
    mnc: Mapped[str | None] = mapped_column(String(4), nullable=True)
    lac: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cell_id: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nmr1_lac: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nmr1_cell_id: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nmr1_signal_strength: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="dBm")
    nmr2_lac: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nmr2_cell_id: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nmr2_signal_strength: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="dBm")
    nmr3_lac: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nmr3_cell_id: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nmr3_signal_strength: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="dBm")
    nmr4_lac: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nmr4_cell_id: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nmr4_signal_strength: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="dBm")
    din_status: Mapped[str | None] = mapped_column(String(4), nullable=True, comment="4-bit digital input status (DIN1-DIN4)")
    dout_status: Mapped[str | None] = mapped_column(String(2), nullable=True, comment="2-bit digital output status (DO1-DO2)")
    device_mode: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, comment="1=Active>0, 2=Active>0, 3=Sleep, 4=Deep sleep")
    distance: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Accumulated distance in km")
    adc1: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="mV")
    adc2: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="mV")
    frame_number: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Sequence number (1-999999)")
    ota_command: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="32-bit CRC")
    
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())