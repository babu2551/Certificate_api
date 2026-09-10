import os
import hashlib
import secrets
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "certificate_system")

if not MONGODB_URL:
    raise RuntimeError("MONGODB_URL is missing from the .env file")

client = MongoClient(
    MONGODB_URL,
    connectTimeoutMS=10000,
    serverSelectionTimeoutMS=10000,
    socketTimeoutMS=20000,
    maxIdleTimeMS=60000,
)
database = client[DATABASE_NAME]
registrations = database["registrations"]
events = database["events"]
certificates = database["certificates"]
admins = database["admins"]


def create_registration_index() -> None:
    """Enforce uniqueness even when two requests arrive at the same time."""
    registrations.create_index(
        [("email", ASCENDING), ("event", ASCENDING)],
        unique=True,
        name="unique_email_event",
    )
    events.create_index("name", unique=True, name="unique_event_name")
    certificates.create_index(
        [("email", ASCENDING), ("event", ASCENDING)],
        unique=True,
        name="unique_certificate_email_event",
    )
    admins.create_index("username", unique=True, name="unique_admin_username")


def _password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        300_000,
    ).hex()


def seed_admin_account(username: str, password: str) -> None:
    salt = secrets.token_bytes(16)
    admins.update_one(
        {"username": username},
        {
            "$setOnInsert": {
                "username": username,
                "password_hash": _password_hash(password, salt),
                "password_salt": salt.hex(),
                "created_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


def verify_admin_password(username: str, password: str) -> bool:
    account = admins.find_one({"username": username})
    if account is None:
        return False
    expected_hash = _password_hash(password, bytes.fromhex(account["password_salt"]))
    return secrets.compare_digest(expected_hash, account["password_hash"])


def check_database_connection() -> None:
    client.admin.command("ping")
