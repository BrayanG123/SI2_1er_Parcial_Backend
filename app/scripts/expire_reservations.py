"""Vence reservas cuyo día de visita ya terminó."""

import argparse

from app.db.session import SessionLocal
from app.modules.reservations.service import ReservationService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 10_000:
        parser.error("--limit debe estar entre 1 y 10000")
    with SessionLocal() as db:
        expired = ReservationService(db).expire_due(limit=args.limit)
    print(f"Reservas vencidas: {expired}")


if __name__ == "__main__":
    main()
