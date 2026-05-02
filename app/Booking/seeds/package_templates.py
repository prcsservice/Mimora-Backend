"""
Package template seeder.
Run: python -m app.Booking.seeds.package_templates
Also called on Booking service startup (idempotent).

Image URLs are stored as **root-relative paths** (`/artist/pakage/...`). The
frontend serves these assets from its own `public/` folder, so the path
resolves against whatever origin the FE is running on (dev or prod) — no env
needed. Folder spelled "pakage" intentionally to match the existing path.
"""
from app.auth.database import SessionLocal
from app.Booking.models import ArtistPackage
import app.auth.models  # register artists table in Base.metadata (FK target)
import uuid


def _img(filename: str) -> str:
    return f"/artist/pakage/{filename}"


TEMPLATES = [
    {
        "name": "HD Makeup",
        "price": 1000.0,
        "duration_minutes": 60,
        "category": "makeup",
        "service_type": "makeup",
        "description": "HD makeup for parties, events, shoots. Clean base, long-lasting finish.",
        "module": "instant",
        "is_template": True,
        "image_url": _img("e855fd2ba6b6236a603453151ebbf617e95ae944.png"),
    },
    {
        "name": "SFX / Editorial Makeup",
        "price": 1200.0,
        "duration_minutes": 90,
        "category": "makeup",
        "service_type": "makeup",
        "description": "Creative or SFX makeup for shoots, performances, themed looks.",
        "module": "instant",
        "is_template": True,
        "image_url": _img("3b8c1872b73c3b652564fc033eb727b3beb31e58.png"),
    },
    {
        "name": "Basic Hairstyling",
        "price": 1000.0,
        "duration_minutes": 45,
        "category": "hairstyle",
        "service_type": "hairstyle",
        "description": "Hair straightening, curls, waves, or basic styling.",
        "module": "instant",
        "is_template": True,
        "image_url": _img("fa17e98631225dbcf37e9ba47d52bd4aae4452b9.png"),
    },
    {
        "name": "Premium Hairstyling",
        "price": 1200.0,
        "duration_minutes": 60,
        "category": "hairstyle",
        "service_type": "hairstyle",
        "description": "Detailed hairstyling with volume, texture, and long-lasting hold.",
        "module": "instant",
        "is_template": True,
        "image_url": _img("fa17e98631225dbcf37e9ba47d52bd4aae4452b9.png"),
    },
    {
        "name": "Gel Nail Art",
        "price": 1000.0,
        "duration_minutes": 45,
        "category": "nail",
        "service_type": "nail",
        "description": "Gel nail art with neat designs and durable finish.",
        "module": "instant",
        "is_template": True,
        "image_url": _img("bc992a668f17d9be4ec2b34a9e870ebfdd208748.png"),
    },
    {
        "name": "Festive Mehendi",
        "price": 500.0,
        "duration_minutes": 45,
        "category": "mehendi",
        "service_type": "mehendi",
        "description": "Lighter, quicker mehendi for everyday celebration festivals.",
        "module": "instant",
        "is_template": True,
        "image_url": _img("68e46b23947108e39a31613a92783b1777bbaf83.png"),
    },
    {
        "name": "Bridal Mehendi",
        "price": 3000.0,
        "duration_minutes": 90,
        "category": "mehendi",
        "service_type": "mehendi",
        "description": "Full bridal mehendi for hands and feet. Intricate patterns.",
        "module": "instant",
        "is_template": True,
        "image_url": _img("ad6a629e8008a42aed4bf37493df095ab18440b8.png"),
    },
    {
        "name": "Saree Draping",
        "price": 800.0,
        "duration_minutes": 30,
        "category": "saree_draping",
        "service_type": "saree_draping",
        "description": "Classic and modern saree draping styles for all occasions.",
        "module": "instant",
        "is_template": True,
        "image_url": _img("2c3956aa8a0886d11016f0b373375bea2d8918d8.png"),
    },
    {
        "name": "Party Makeup",
        "price": 900.0,
        "duration_minutes": 45,
        "category": "makeup",
        "service_type": "makeup",
        "description": "Party-ready glamorous makeup look.",
        "module": "instant",
        "is_template": True,
        "image_url": _img("e855fd2ba6b6236a603453151ebbf617e95ae944.png"),
    },
    {
        "name": "Natural Makeup",
        "price": 700.0,
        "duration_minutes": 45,
        "category": "makeup",
        "service_type": "makeup",
        "description": "Soft, natural-looking makeup for daily wear or intimate events.",
        "module": "instant",
        "is_template": True,
        "image_url": _img("e855fd2ba6b6236a603453151ebbf617e95ae944.png"),
    },
]


def seed_templates():
    """Insert templates if missing; otherwise upsert image_url on existing rows
    so admins can refresh imagery without wiping the table."""
    db = SessionLocal()
    try:
        existing = {
            row.name: row
            for row in db.query(ArtistPackage).filter(ArtistPackage.is_template == True).all()
        }

        if not existing:
            for t in TEMPLATES:
                pkg = ArtistPackage(
                    id=uuid.uuid4(),
                    artist_id=None,
                    is_active=True,
                    **t,
                )
                db.add(pkg)
            db.commit()
            print(f"Seeded {len(TEMPLATES)} templates.")
            return

        # Backfill: update image_url on rows that have none (and refresh whenever
        # the seeder definition changes).
        updated = 0
        for t in TEMPLATES:
            row = existing.get(t["name"])
            if not row:
                # New template added to seeder later — insert it.
                db.add(ArtistPackage(id=uuid.uuid4(), artist_id=None, is_active=True, **t))
                updated += 1
                continue
            if row.image_url != t["image_url"]:
                row.image_url = t["image_url"]
                updated += 1
        if updated:
            db.commit()
            print(f"Templates already seeded ({len(existing)} found). Refreshed {updated} image_url(s).")
        else:
            print(f"Templates already seeded ({len(existing)} found). No changes.")
    except Exception as e:
        db.rollback()
        print(f"Seed error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_templates()
