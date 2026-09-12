from pathlib import Path

import csv
import os
from datetime import datetime, timezone
from io import StringIO

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import DuplicateKeyError, PyMongoError

from certificate import DEFAULT_RANK, create_certificate
from database import (
    certificates,
    check_database_connection,
    create_registration_index,
    events,
    registrations,
    seed_admin_account,
    verify_admin_password,
)
from models import (
    RegistrationRequest,
    RegistrationResponse,
    VerificationRequest,
    VerificationResponse,
    CertificateRequest,
    EventRequest,
)

app = FastAPI(
    title="College Event Certificate Management API",
    description="Register students, verify eligibility, and download certificates.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5501",
        "http://127.0.0.1:5501",
        "null",
        "https://certificate-api-w6r6.onrender.com",
    ],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

FRONTEND_DIRECTORY = Path(__file__).with_name("frontend")
LOGO_FILE = FRONTEND_DIRECTORY / "logo.jpg"
security = HTTPBasic()
APP_ENV = os.getenv("APP_ENV", "development").lower()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if APP_ENV == "production" and (not ADMIN_USERNAME or not ADMIN_PASSWORD):
    raise RuntimeError("ADMIN_USERNAME and ADMIN_PASSWORD must be configured in production.")

ADMIN_USERNAME = ADMIN_USERNAME or "admin"
ADMIN_PASSWORD = ADMIN_PASSWORD or "admin12345"


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    try:
        valid_credentials = verify_admin_password(credentials.username, credentials.password)
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")
    if not valid_credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.on_event("startup")
def initialize_database() -> None:
    create_registration_index()
    seed_admin_account(ADMIN_USERNAME, ADMIN_PASSWORD)


@app.get("/health")
def health_check() -> JSONResponse:
    try:
        check_database_connection()
    except PyMongoError:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "unavailable"},
        )

    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "database": "available"},
    )


@app.post("/register", response_model=RegistrationResponse, status_code=201)
def register_student(registration: RegistrationRequest) -> RegistrationResponse:
    registration_data = registration.model_dump()
    registration_data["email"] = str(registration.email).lower()
    registration_data.setdefault("download_count", 0)
    registration_data["created_at"] = datetime.now(timezone.utc)

    try:
        result = registrations.insert_one(registration_data)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="This email is already registered for this event.",
        )
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")

    return RegistrationResponse(
        message="Student registered successfully.",
        registration_id=str(result.inserted_id),
    )


@app.post("/certificate/verify", response_model=VerificationResponse)
def verify_registration(request: VerificationRequest) -> VerificationResponse:
    email = str(request.email).lower()

    try:
        student = registrations.find_one({"email": email, "event": request.event})
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")

    if student is None:
        return VerificationResponse(
            eligible=False,
            message="Certificate not available. Student is not registered for this event.",
        )

    return VerificationResponse(
        eligible=True,
        name=student["name"],
        course=student["course"],
        rank=student.get("rank") or DEFAULT_RANK,
        message="Student is registered and eligible for certificate.",
    )


@app.get("/events", response_model=list[str])
def list_events() -> list[str]:
    try:
        registration_events = registrations.distinct("event")
        configured_events = events.distinct("name")
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")

    return sorted({event for event in [*registration_events, *configured_events] if isinstance(event, str) and event.strip()})


@app.get("/certificate/download/{email}/{event}")
def download_certificate(email: str, event: str) -> StreamingResponse:
    try:
        student = registrations.find_one({"email": email.lower(), "event": event})
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")

    if student is None:
        raise HTTPException(
            status_code=404,
            detail="Certificate not available. Student is not registered for this event.",
        )

    pdf_buffer = create_certificate(
        name=student["name"],
        rank=student.get("rank"),
    )
    registrations.update_one(
        {"_id": student["_id"]},
        {"$set": {"downloaded_at": datetime.now(timezone.utc)}, "$inc": {"download_count": 1}},
    )
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=certificate.pdf"},
    )


def _serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@app.get("/admin/dashboard")
def admin_dashboard(_: str = Depends(verify_admin)) -> dict:
    try:
        total_students = registrations.count_documents({})
        downloaded = registrations.count_documents({"downloaded_at": {"$exists": True}})
        event_rows = list(events.find({}, {"_id": 0}).sort("created_at", -1))
        known_event_names = {row.get("name") for row in event_rows}
        registration_names = registrations.distinct("event")
        for name in registration_names:
            if name not in known_event_names:
                event_rows.append({"name": name, "date": "", "description": "", "created_at": None})
        recent = list(registrations.find({}, {"_id": 0}).sort("created_at", -1))
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")

    return {
        "stats": {
            "students": total_students,
            "downloaded": downloaded,
            "pending": max(total_students - downloaded, 0),
            "events": len(event_rows),
        },
        "events": [{key: _serialize(value) for key, value in row.items()} for row in event_rows],
        "recent_registrations": [{key: _serialize(value) for key, value in row.items()} for row in recent],
    }


@app.post("/admin/events")
def create_event(request: EventRequest, _: str = Depends(verify_admin)) -> dict:
    event_data = {**request.model_dump(), "created_at": datetime.now(timezone.utc)}
    try:
        events.insert_one(event_data)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="An event with this name already exists.")
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")
    return {"message": "Event created successfully."}


@app.delete("/admin/events/{event_name}")
def delete_event(event_name: str, _: str = Depends(verify_admin)) -> dict:
    try:
        event_result = events.delete_one({"name": event_name})
        registration_result = registrations.delete_many({"event": event_name})
        certificate_result = certificates.delete_many({"event": event_name})
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")
    return {
        "message": "Event and related records deleted successfully.",
        "event_deleted": event_result.deleted_count,
        "students_deleted": registration_result.deleted_count,
        "certificates_deleted": certificate_result.deleted_count,
    }


@app.delete("/admin/registrations/{email}/{event_name}")
def delete_registration(email: str, event_name: str, _: str = Depends(verify_admin)) -> dict:
    normalized_email = email.lower()
    try:
        registration_result = registrations.delete_one({"email": normalized_email, "event": event_name})
        certificate_result = certificates.delete_one({"email": normalized_email, "event": event_name})
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")
    if not registration_result.deleted_count:
        raise HTTPException(status_code=404, detail="Student registration was not found.")
    return {
        "message": "Student registration deleted successfully.",
        "certificate_deleted": certificate_result.deleted_count,
    }


@app.post("/admin/certificates")
def create_certificate_record(request: CertificateRequest, _: str = Depends(verify_admin)) -> dict:
    certificate_data = request.model_dump()
    certificate_data["email"] = str(request.email).lower()
    now = datetime.now(timezone.utc)
    certificate_data["issued_at"] = now
    try:
        registrations.update_one(
            {"email": certificate_data["email"], "event": certificate_data["event"]},
            {"$set": certificate_data, "$setOnInsert": {"created_at": now, "download_count": 0}},
            upsert=True,
        )
        certificates.update_one(
            {"email": certificate_data["email"], "event": certificate_data["event"]},
            {"$set": certificate_data},
            upsert=True,
        )
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")
    return {"message": "Certificate issued successfully."}


@app.post("/admin/registrations/upload")
async def upload_registrations(
    file: UploadFile = File(...),
    _: str = Depends(verify_admin),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(StringIO(content))
    required = {"name", "email", "course", "event"}
    headers = {header.strip().lower() for header in (reader.fieldnames or [])}
    if not required.issubset(headers):
        raise HTTPException(status_code=400, detail="CSV must include name, email, course, and event columns.")

    imported = 0
    now = datetime.now(timezone.utc)
    try:
        for row in reader:
            normalized = {str(key).strip().lower(): (value or "").strip() for key, value in row.items() if key}
            if not all(normalized.get(field) for field in required):
                continue
            registrations.update_one(
                {"email": normalized["email"].lower(), "event": normalized["event"]},
                {"$set": {**normalized, "email": normalized["email"].lower()}, "$setOnInsert": {"created_at": now, "download_count": 0}},
                upsert=True,
            )
            imported += 1
    except (UnicodeDecodeError, PyMongoError):
        raise HTTPException(status_code=400, detail="The CSV could not be imported.")
    return {"message": f"Imported {imported} registration(s).", "imported": imported}


@app.get("/logo.jpg", include_in_schema=False)
def serve_logo() -> FileResponse:
    return FileResponse(LOGO_FILE, media_type="image/jpeg")


@app.get("/")
def api_root() -> dict[str, str]:
    return {"message": "Certificate API is running.", "docs": "/docs", "health": "/health"}
