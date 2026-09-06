import os

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "certificate_system")

if not MONGODB_URL:
    raise RuntimeError("MONGODB_URL is missing from the .env file")

client = MongoClient(MONGODB_URL)
database = client[DATABASE_NAME]
registrations = database["registrations"]


def create_registration_index() -> None:
    """Enforce uniqueness even when two requests arrive at the same time."""
    registrations.create_index(
        [("email", ASCENDING), ("event", ASCENDING)],
        unique=True,
        name="unique_email_event",
    )
