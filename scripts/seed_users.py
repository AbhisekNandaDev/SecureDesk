"""Run with: python -m scripts.seed_users (use --credentials or SEED_USER_PASSWORD)."""
import argparse
import asyncio
import csv
from pathlib import Path
import os

from sqlalchemy import select

from core.db import AsyncSessionLocal, close_db, init_db
from core.security import hash_password
from models.user import User

# Name, department, role, explicit groups, support scope.
USERS = (
    ("Alice", "engineering", "employee", [], []),
    ("Bob", "engineering", "document_publisher", [], []),
    ("Carol", "engineering", "document_approver", [], []),
    ("David", "finance", "employee", ["finance_employees"], []),
    ("Emma", "finance", "document_publisher", ["finance_employees"], []),
    ("Frank", "finance", "document_approver", ["finance_employees"], []),
    ("Grace", "it_support", "support_analyst", [], ["engineering", "finance", "it_support"]),
    ("Henry", "it_support", "platform_administrator", [], []),
    ("Iris", "security", "security_reviewer", [], []),
)


def load_credentials(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected = {f"{row[0].lower()}@northstar.example" for row in USERS}
    credentials = {row["email"]: row["password"] for row in rows}
    if len(rows) != len(expected) or set(credentials) != expected:
        raise ValueError("Credentials CSV must contain each of the nine seeded emails exactly once")
    return credentials


async def seed_users(db, password: str | dict[str, str]) -> int:
    passwords = password.values() if isinstance(password, dict) else [password]
    for value in passwords:
        if len(value) < 12 or len(value.encode("utf-8")) > 72:
            raise ValueError("Seed password must be at least 12 characters and at most 72 UTF-8 bytes")
    created = 0
    for name, department, role, groups, scope in USERS:
        email = f"{name.lower()}@northstar.example"
        existing = await db.scalar(select(User).where(User.email == email))
        if existing is not None:
            continue  # Never reset passwords or overwrite later permission changes.
        db.add(User(name=name, email=email, department=department, user_type=role,
                    permission_group="", groups=groups, support_departments=scope,
                    is_active=True, hashed_password=hash_password(password[email] if isinstance(password, dict) else password)))
        created += 1
    await db.commit()
    return created


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, help="Local CSV containing email and password columns")
    args = parser.parse_args()
    password = load_credentials(args.credentials) if args.credentials else os.environ.get("SEED_USER_PASSWORD")
    if not password:
        raise SystemExit("Pass --credentials or set SEED_USER_PASSWORD for these local lab accounts")
    try:
        await init_db()
        async with AsyncSessionLocal() as db:
            print(f"Created {await seed_users(db, password)} lab accounts")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
