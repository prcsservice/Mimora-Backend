"""Truncate Mimora tables.

Usage:
    python clear_tables.py                  # truncate ALL app tables (FK-safe, with confirm)
    python clear_tables.py bookings         # truncate just `bookings` (+ FK cascades)
    python clear_tables.py bookings booking_packages   # multiple tables
    python clear_tables.py --yes            # skip the confirm prompt (for scripts)
    python clear_tables.py --keep-templates # don't wipe seeded package templates

⚠️  Destructive. Always confirms before running unless --yes is passed.
"""
import sys
from app.auth.database import engine
from sqlalchemy import text

# FK-safe truncate order (children first); CASCADE handles the rest.
TABLES = [
    "booking_packages",
    "bookings",
    "wishlists",
    "kyc_requests",
    "email_otps",
    "email_artist_otps",
    "artist_packages",
    "artists",
    "customer",
]


def main() -> None:
    args = sys.argv[1:]
    yes = "--yes" in args
    keep_templates = "--keep-templates" in args
    args = [a for a in args if not a.startswith("--")]

    targets = args if args else TABLES
    unknown = [t for t in targets if t not in TABLES]
    if unknown:
        sys.exit(f"unknown table(s): {unknown}. valid: {', '.join(TABLES)}")

    print("About to TRUNCATE these tables (CASCADE):")
    for t in targets:
        print(f"  - {t}")
    if keep_templates and "artist_packages" in targets:
        print("  (--keep-templates: artist_packages templates will be preserved)")

    if not yes:
        ans = input("\nType 'YES' to proceed: ").strip()
        if ans != "YES":
            print("aborted.")
            return

    with engine.begin() as conn:
        if keep_templates and "artist_packages" in targets:
            # Wipe everything except templates
            non_template = [t for t in targets if t != "artist_packages"]
            for t in non_template:
                conn.execute(text(f'TRUNCATE TABLE "{t}" RESTART IDENTITY CASCADE'))
                print(f"  truncated {t}")
            conn.execute(text(
                'DELETE FROM artist_packages WHERE is_template = false'
            ))
            print("  deleted non-template rows from artist_packages")
        else:
            for t in targets:
                conn.execute(text(f'TRUNCATE TABLE "{t}" RESTART IDENTITY CASCADE'))
                print(f"  truncated {t}")
    print("\ndone.")


if __name__ == "__main__":
    main()
