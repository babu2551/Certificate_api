from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import DuplicateKeyError, PyMongoError

from certificate import DEFAULT_RANK, create_certificate
from database import check_database_connection, create_registration_index, registrations
from models import (
    RegistrationRequest,
    RegistrationResponse,
    VerificationRequest,
    VerificationResponse,
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
    ],
    allow_origin_regex=r"https://.*",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

FRONTEND_DIRECTORY = Path(__file__).with_name("frontend")


@app.on_event("startup")
def initialize_database() -> None:
    create_registration_index()


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
        events = registrations.distinct("event")
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database is unavailable.")

    return sorted(event for event in events if isinstance(event, str) and event.strip())


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
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=certificate.pdf"},
    )


app.mount("/", StaticFiles(directory=FRONTEND_DIRECTORY, html=True), name="frontend")
