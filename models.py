from sqlmodel import SQLModel, Field, create_engine, Session
from datetime import datetime
from typing import Optional
from config import DATABASE_URL

# ── Database engine ────────────────────────────────────────────────────────────
engine = create_engine(DATABASE_URL, echo=False)

def create_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

# ── Lead table ─────────────────────────────────────────────────────────────────
class Lead(SQLModel, table=True):
    id:           Optional[int] = Field(default=None, primary_key=True)

    # Form fields
    name:         str
    email:        str
    company:      str
    website:      str
    industry:     str
    pain_points:  str

    # Pipeline state
    # Lifecycle: pending → enriching → generating → rendering → sending → sent
    #                                                                   → failed
    status:       str = "pending"
    error_msg:    Optional[str] = None

    # Outputs
    pdf_path:     Optional[str] = None
    drive_url:    Optional[str] = None
    sheet_row:    Optional[int] = None

    # Timestamps
    created_at:   datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

# ── Pydantic schema for the intake form (validation layer) ─────────────────────
from pydantic import BaseModel, EmailStr, HttpUrl

class LeadFormInput(BaseModel):
    name:        str
    email:       EmailStr
    company:     str
    website:     str           # validated as a URL in the endpoint
    industry:    str
    pain_points: str

class LeadStatusResponse(BaseModel):
    id:     int
    status: str
    msg:    str
