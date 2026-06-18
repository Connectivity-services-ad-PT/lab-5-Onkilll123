"""
FIT4110 Lab 05 — Access Gate Service (team-gate)
Docker Compose multi-service version.
Adds DB connectivity (PostgreSQL) and AI service integration.
Endpoints: /health, /access-events, /cards
"""

import os
import uuid
import httpx
import asyncpg
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from enum import Enum
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ──────────────────────────────────────────────
# Config from environment
# ──────────────────────────────────────────────
SERVICE_NAME    = os.getenv("SERVICE_NAME",    "access-gate")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.5.0")
AUTH_TOKEN      = os.getenv("AUTH_TOKEN",      "local-dev-token")
AI_SERVICE_URL  = os.getenv("AI_SERVICE_URL",  "http://ai-service:9000")

POSTGRES_HOST   = os.getenv("POSTGRES_HOST",   "db")
POSTGRES_PORT   = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER   = os.getenv("POSTGRES_USER",   "lab05")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "lab05pass")
POSTGRES_DB     = os.getenv("POSTGRES_DB",     "gatedb")

# ──────────────────────────────────────────────
# DB pool (optional — falls back to in-memory)
# ──────────────────────────────────────────────
db_pool = None

async def get_db_pool():
    global db_pool
    if db_pool is None:
        try:
            db_pool = await asyncpg.create_pool(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                database=POSTGRES_DB,
                min_size=1,
                max_size=5,
            )
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS access_events (
                        event_id TEXT PRIMARY KEY,
                        card_id TEXT NOT NULL,
                        gate_id TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        result TEXT NOT NULL,
                        deny_reason TEXT,
                        zone_id TEXT,
                        timestamp TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS cards (
                        card_id TEXT PRIMARY KEY,
                        holder_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        issued_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    )
                """)
                # Seed cards if empty
                count = await conn.fetchval("SELECT COUNT(*) FROM cards")
                if count == 0:
                    await conn.executemany(
                        "INSERT INTO cards VALUES ($1,$2,$3,$4,$5)",
                        [
                            ("CARD-2026-001","Nguyen Van A","active","2026-01-15T00:00:00Z","2027-01-15T00:00:00Z"),
                            ("CARD-2026-002","Tran Thi B","active","2026-02-01T00:00:00Z","2027-02-01T00:00:00Z"),
                            ("CARD-EXPIRED-001","Le Van C","expired","2024-01-01T00:00:00Z","2025-01-01T00:00:00Z"),
                        ]
                    )
        except Exception as e:
            print(f"[WARN] DB connection failed, using in-memory fallback: {e}")
            db_pool = None
    return db_pool

# In-memory fallback
ACCESS_EVENTS_MEM: List[Dict] = []
CARDS_MEM: Dict[str, Dict] = {
    "CARD-2026-001": {"card_id": "CARD-2026-001","holder_name": "Nguyen Van A","status": "active","issued_at": "2026-01-15T00:00:00Z","expires_at": "2027-01-15T00:00:00Z"},
    "CARD-2026-002": {"card_id": "CARD-2026-002","holder_name": "Tran Thi B","status": "active","issued_at": "2026-02-01T00:00:00Z","expires_at": "2027-02-01T00:00:00Z"},
    "CARD-EXPIRED-001": {"card_id": "CARD-EXPIRED-001","holder_name": "Le Van C","status": "expired","issued_at": "2024-01-01T00:00:00Z","expires_at": "2025-01-01T00:00:00Z"},
}

# ──────────────────────────────────────────────
# Lifespan
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_db_pool()
    yield
    if db_pool:
        await db_pool.close()

# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────
app = FastAPI(
    title="FIT4110 Lab 05 — Access Gate Service",
    version=SERVICE_VERSION,
    description="Multi-service Access Gate API with DB + AI integration. team-gate.",
    lifespan=lifespan,
)

# ──────────────────────────────────────────────
# Enums & Models
# ──────────────────────────────────────────────
class Direction(str, Enum):
    in_ = "in"
    out = "out"

class AccessResult(str, Enum):
    accepted = "accepted"
    denied = "denied"
    error = "error"

class DenyReason(str, Enum):
    invalid_card = "invalid_card"
    expired_card = "expired_card"
    permission_denied = "permission_denied"
    gate_error = "gate_error"
    unknown = "unknown"

class CardStatus(str, Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"

class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int = Field(..., ge=400, le=599)
    detail: str
    instance: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    db: str
    ai: str

class AccessEventCreate(BaseModel):
    card_id: str = Field(..., min_length=3, examples=["CARD-2026-001"])
    gate_id: str = Field(..., min_length=1, examples=["GATE-01"])
    direction: Direction = Field(..., examples=["in"])
    timestamp: str = Field(..., examples=["2026-05-19T08:30:00Z"])

class AccessEventResult(BaseModel):
    event_id: str
    card_id: str
    gate_id: str
    direction: Direction
    result: AccessResult
    deny_reason: Optional[DenyReason] = None
    zone_id: Optional[str] = None
    timestamp: str
    created_at: str
    ai_risk: Optional[str] = None

class CardCreate(BaseModel):
    holder_name: str = Field(..., min_length=2, examples=["Nguyen Van B"])
    expires_at: str = Field(..., examples=["2027-06-01T00:00:00Z"])

class Card(BaseModel):
    card_id: str
    holder_name: str
    status: CardStatus
    issued_at: str
    expires_at: str

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"

def next_event_id(count: int) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"EVT-{today}-{count + 1:04d}"

def build_problem(*, status_code, title, detail, instance=None, problem_type="about:blank"):
    p = {"type": problem_type, "title": title, "status": status_code, "detail": detail}
    if instance:
        p["instance"] = instance
    return p

async def call_ai_risk(card_id: str, gate_id: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(f"{AI_SERVICE_URL}/predict", json={"card_id": card_id, "gate_id": gate_id})
            if r.status_code == 200:
                return r.json().get("risk_level", "low")
    except Exception:
        pass
    return "unknown"

async def evaluate_card(card_id: str):
    pool = await get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            card = await conn.fetchrow("SELECT * FROM cards WHERE card_id=$1", card_id)
            if card is None:
                return AccessResult.denied, DenyReason.invalid_card, None
            if card["status"] == "expired":
                return AccessResult.denied, DenyReason.expired_card, dict(card)
            if card["status"] == "revoked":
                return AccessResult.denied, DenyReason.permission_denied, dict(card)
            return AccessResult.accepted, None, dict(card)
    else:
        card = CARDS_MEM.get(card_id)
        if card is None:
            return AccessResult.denied, DenyReason.invalid_card, None
        if card["status"] == "expired":
            return AccessResult.denied, DenyReason.expired_card, card
        if card["status"] == "revoked":
            return AccessResult.denied, DenyReason.permission_denied, card
        return AccessResult.accepted, None, card

# ──────────────────────────────────────────────
# Exception handlers
# ──────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    problem = exc.detail if isinstance(exc.detail, dict) else build_problem(
        status_code=exc.status_code, title=str(exc.status_code),
        detail=str(exc.detail), instance=str(request.url.path),
    )
    for k, v in {"status": exc.status_code, "title": str(exc.status_code),
                  "type": "about:blank", "detail": "Request failed",
                  "instance": str(request.url.path)}.items():
        problem.setdefault(k, v)
    return JSONResponse(status_code=exc.status_code, content=problem,
                        media_type="application/problem+json",
                        headers=getattr(exc, "headers", None))

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(i) for i in first.get("loc", []))
    detail = f"{loc}: {first.get('msg','')}" if loc else first.get("msg", "Validation error")
    return JSONResponse(status_code=422, content=build_problem(
        status_code=422, title="Validation error", detail=detail,
        instance=str(request.url.path),
        problem_type="https://smart-campus.local/problems/validation-error",
    ), media_type="application/problem+json")

# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────
def verify_bearer_token(authorization: Optional[str] = Header(default=None)):
    if not authorization:
        raise HTTPException(status_code=401, detail=build_problem(
            status_code=401, title="Unauthorized", detail="Missing Authorization header",
            instance="/access-events",
            problem_type="https://smart-campus.local/problems/unauthorized",
        ))
    if authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail=build_problem(
            status_code=401, title="Unauthorized", detail="Invalid bearer token",
            instance="/access-events",
            problem_type="https://smart-campus.local/problems/unauthorized",
        ))

# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health():
    # Check DB
    db_status = "ok"
    pool = await get_db_pool()
    if pool is None:
        db_status = "degraded (in-memory)"
    else:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except Exception:
            db_status = "error"

    # Check AI
    ai_status = "ok"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{AI_SERVICE_URL}/health")
            if r.status_code != 200:
                ai_status = "degraded"
    except Exception:
        ai_status = "unreachable"

    return HealthResponse(status="ok", service=SERVICE_NAME, version=SERVICE_VERSION,
                          db=db_status, ai=ai_status)


@app.post("/access-events", response_model=AccessEventResult,
          status_code=201, dependencies=[Depends(verify_bearer_token)],
          responses={401: {"model": ProblemDetails}, 422: {"model": ProblemDetails}})
async def create_access_event(payload: AccessEventCreate):
    result, deny_reason, _ = await evaluate_card(payload.card_id)
    ai_risk = await call_ai_risk(payload.card_id, payload.gate_id)
    created_at = now_iso()
    zone_id = "ZONE-A"

    pool = await get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM access_events")
            event_id = next_event_id(count)
            await conn.execute(
                "INSERT INTO access_events VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
                event_id, payload.card_id, payload.gate_id,
                payload.direction.value, result.value,
                deny_reason.value if deny_reason else None,
                zone_id, payload.timestamp, created_at,
            )
    else:
        event_id = next_event_id(len(ACCESS_EVENTS_MEM))
        ACCESS_EVENTS_MEM.append({
            "event_id": event_id, "card_id": payload.card_id,
            "gate_id": payload.gate_id, "direction": payload.direction.value,
            "result": result.value,
            "deny_reason": deny_reason.value if deny_reason else None,
            "zone_id": zone_id, "timestamp": payload.timestamp, "created_at": created_at,
        })

    return AccessEventResult(
        event_id=event_id, card_id=payload.card_id, gate_id=payload.gate_id,
        direction=payload.direction, result=result, deny_reason=deny_reason,
        zone_id=zone_id, timestamp=payload.timestamp, created_at=created_at,
        ai_risk=ai_risk,
    )


@app.get("/access-events", dependencies=[Depends(verify_bearer_token)],
         responses={401: {"model": ProblemDetails}})
async def get_access_events(
    gate_id: Optional[str] = Query(default=None),
    direction: Optional[str] = Query(default=None),
    result: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    pool = await get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM access_events ORDER BY created_at DESC")
            items = [dict(r) for r in rows]
    else:
        items = list(ACCESS_EVENTS_MEM)

    if gate_id:
        items = [e for e in items if e["gate_id"] == gate_id]
    if direction:
        items = [e for e in items if e["direction"] == direction]
    if result:
        items = [e for e in items if e["result"] == result]

    total = len(items)
    return {"items": items[offset: offset + limit], "total": total}


@app.get("/cards/{card_id}", response_model=Card,
         dependencies=[Depends(verify_bearer_token)],
         responses={401: {"model": ProblemDetails}, 404: {"model": ProblemDetails}})
async def get_card_by_id(card_id: str):
    pool = await get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            card = await conn.fetchrow("SELECT * FROM cards WHERE card_id=$1", card_id)
            if card is None:
                raise HTTPException(status_code=404, detail=build_problem(
                    status_code=404, title="Not Found", detail=f"Card {card_id} not found",
                    instance=f"/cards/{card_id}",
                    problem_type="https://smart-campus.local/problems/not-found",
                ))
            return Card(**dict(card))
    else:
        card = CARDS_MEM.get(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail=build_problem(
                status_code=404, title="Not Found", detail=f"Card {card_id} not found",
                instance=f"/cards/{card_id}",
                problem_type="https://smart-campus.local/problems/not-found",
            ))
        return Card(**card)


@app.post("/cards", response_model=Card, status_code=201,
          dependencies=[Depends(verify_bearer_token)],
          responses={401: {"model": ProblemDetails}})
async def create_card(payload: CardCreate, response: Response):
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    issued_at = now_iso()

    pool = await get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM cards")
            card_id = f"CARD-{today}-{count + 1:03d}"
            await conn.execute(
                "INSERT INTO cards VALUES ($1,$2,$3,$4,$5)",
                card_id, payload.holder_name, "active", issued_at, payload.expires_at,
            )
    else:
        card_id = f"CARD-{today}-{len(CARDS_MEM) + 1:03d}"
        CARDS_MEM[card_id] = {
            "card_id": card_id, "holder_name": payload.holder_name,
            "status": "active", "issued_at": issued_at, "expires_at": payload.expires_at,
        }

    response.headers["Location"] = f"/cards/{card_id}"
    return Card(card_id=card_id, holder_name=payload.holder_name,
                status=CardStatus.active, issued_at=issued_at, expires_at=payload.expires_at)
