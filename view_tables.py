"""View all Mimora tables.

Usage:
    python view_tables.py                    # show counts + first 5 rows of each table
    python view_tables.py bookings           # show all rows of just `bookings`
    python view_tables.py bookings 20        # show first 20 rows
    python view_tables.py --counts           # just counts, no rows
"""
import sys
from app.auth.database import engine
from sqlalchemy import text

# Every app table — keep in sync with models.py
TABLES = [
    "customer",
    "artists",
    "artist_packages",
    "bookings",
    "booking_packages",
    "wishlists",
    "kyc_requests",
    "email_otps",
    "email_artist_otps",
]


def show_table(conn, name: str, limit: int | None) -> None:
    print("\n" + "=" * 78)
    print(f"TABLE: {name}")
    print("=" * 78)
    n = conn.execute(text(f'SELECT count(*) FROM "{name}"')).scalar()
    print(f"rows: {n}")
    if n == 0 or limit == 0:
        return
    sql = f'SELECT * FROM "{name}" ORDER BY 1 DESC'
    if limit is not None:
        sql += f" LIMIT {limit}"
    result = conn.execute(text(sql))
    cols = list(result.keys())
    print(" | ".join(cols))
    print("-" * 78)
    for row in result:
        print(" | ".join((str(v)[:35] if v is not None else "-") for v in row))


def main() -> None:
    args = sys.argv[1:]
    counts_only = "--counts" in args
    args = [a for a in args if a != "--counts"]

    target = args[0] if args else None
    limit_arg = int(args[1]) if len(args) > 1 else None

    with engine.connect() as conn:
        if target:
            if target not in TABLES:
                sys.exit(f"unknown table {target!r}. valid: {', '.join(TABLES)}")
            show_table(conn, target, limit_arg)
        else:
            for t in TABLES:
                show_table(conn, t, 0 if counts_only else 5)


if __name__ == "__main__":
    main()
