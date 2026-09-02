"""Crea la primera cuenta administrativa sin almacenar credenciales por defecto."""

import argparse
from getpass import getpass

from pydantic import ValidationError

from app.core.exceptions import AppException
from app.db.session import SessionLocal
from app.modules.users.schemas import UsuarioAdminCreate
from app.modules.users.service import UserService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crear una cuenta administrativa")
    parser.add_argument("--email", required=True)
    parser.add_argument("--nombres", required=True)
    parser.add_argument("--apellidos", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    password = getpass("Contraseña: ")
    confirmation = getpass("Repite la contraseña: ")
    if password != confirmation:
        raise SystemExit("Las contraseñas no coinciden.")

    try:
        data = UsuarioAdminCreate(
            email=args.email,
            password=password,
            nombres=args.nombres,
            apellidos=args.apellidos,
            roles=["administrador"],
        )
        with SessionLocal() as db:
            user = UserService(db).create_user(data)
        print(f"Administrador creado: {user.email}")
    except (ValidationError, AppException) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
