"""Puebla una base vacía con datos demostrativos de catálogo y ventas."""

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from getpass import getpass
import os
import re
from uuid import UUID, uuid5

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal
from app.modules.branches.models import Ciudad, Sucursal
from app.modules.cart.models import Carrito, DetalleCarrito
from app.modules.catalog.models import (
    Coleccion,
    Color,
    ImagenProducto,
    Producto,
    Talla,
    Temporada,
    VarianteProducto,
)
from app.modules.categories.models import Categoria
from app.modules.inventory.models import Inventario, MovimientoInventario
from app.modules.inventory.schemas import RecepcionCreate
from app.modules.inventory.service import InventoryService
from app.modules.orders.models import DetallePedido, Pedido
from app.modules.payments.models import Pago, Reembolso
from app.modules.reservations.models import DetalleReserva, Reserva
from app.modules.returns.models import DetalleDevolucion, Devolucion
from app.modules.suppliers.models import Proveedor
from app.modules.users.models import PerfilCliente, Rol, Usuario


SEED_NAMESPACE = UUID("a16e4251-e9ca-4c5f-9fb9-31b90547b610")
DEMO_EMAIL_DOMAIN = "demo.example.com"
DEMO_EMAIL_SUFFIX = f"@{DEMO_EMAIL_DOMAIN}"
LEGACY_DEMO_EMAIL_SUFFIX = ".demo@ropa.test"
LEGACY_SUPPLIER_EMAIL_SUFFIX = "@ropa.test"
EMAIL_VALIDATOR = TypeAdapter(EmailStr)
CITY_DATA = (
    ("La Paz", "La Paz"),
    ("Santa Cruz de la Sierra", "Santa Cruz"),
    ("Cochabamba", "Cochabamba"),
    ("Sucre", "Chuquisaca"),
    ("Tarija", "Tarija"),
    ("Oruro", "Oruro"),
    ("Potosí", "Potosí"),
    ("Trinidad", "Beni"),
    ("Cobija", "Pando"),
    ("El Alto", "La Paz"),
)
CATEGORY_NAMES = (
    "Camisetas",
    "Camisas",
    "Pantalones",
    "Vestidos",
    "Chaquetas",
    "Suéteres",
    "Ropa deportiva",
    "Ropa interior",
    "Calzado",
    "Accesorios",
)
SIZE_DATA = (("XS", 1), ("S", 2), ("M", 3), ("L", 4), ("XL", 5), ("XXL", 6))
COLOR_DATA = (
    ("Negro", "#111111"),
    ("Blanco", "#FFFFFF"),
    ("Azul", "#2563EB"),
    ("Rojo", "#DC2626"),
    ("Verde", "#16A34A"),
    ("Beige", "#D6C6A8"),
    ("Gris", "#6B7280"),
    ("Rosado", "#EC4899"),
    ("Morado", "#9333EA"),
    ("Amarillo", "#EAB308"),
    ("Café", "#78350F"),
    ("Celeste", "#38BDF8"),
)
FIRST_NAMES = (
    "Ana", "Luis", "María", "Carlos", "Sofía", "Diego", "Valeria", "Mateo",
    "Camila", "Andrés", "Lucía", "Javier", "Daniela", "Fernando", "Gabriela",
    "Miguel", "Paola", "Rodrigo", "Elena", "Nicolás",
)
LAST_NAMES = (
    "Flores", "Mamani", "Quispe", "Rojas", "Vargas", "Gutiérrez", "Condori",
    "Fernández", "Pérez", "Rivera", "Castillo", "Torrez", "Morales", "Salazar",
)
BRANDS = ("Andina", "Altura", "Nativa", "Urbana", "Línea Sur", "Cordillera")
STYLES = (
    "Clásico", "Urbano", "Esencial", "Premium", "Ligero", "Confort",
    "Moderno", "Andino", "Casual", "Activo",
)


class SeedDataExistsError(RuntimeError):
    """La base contiene información que el seeder no debe sobrescribir."""


@dataclass(frozen=True)
class SeedConfig:
    seed: int = 20260906
    anchor_date: date = date(2026, 9, 6)
    city_count: int = 10
    branch_count: int = 15
    client_count: int = 70
    product_count: int = 160
    order_count: int = 240
    reservation_count: int = 25
    return_count: int = 24
    cart_count: int = 20
    variants_per_product: int = 3

    def validate(self) -> None:
        if not 1 <= self.city_count <= len(CITY_DATA):
            raise ValueError(f"city_count debe estar entre 1 y {len(CITY_DATA)}.")
        if not self.city_count <= self.branch_count <= self.city_count * 2:
            raise ValueError("branch_count debe estar entre city_count y su doble.")
        if self.client_count < 5 or self.product_count < 5 or self.order_count < 5:
            raise ValueError("Se requieren al menos 5 clientes, productos y pedidos.")
        if not 1 <= self.variants_per_product <= min(len(SIZE_DATA), len(COLOR_DATA)):
            raise ValueError("variants_per_product no es válido.")
        if self.reservation_count < 0 or self.return_count < 0 or self.cart_count < 0:
            raise ValueError("Las cantidades no pueden ser negativas.")
        if self.return_count > self.order_count:
            raise ValueError("return_count no puede superar order_count.")
        if self.cart_count > self.client_count:
            raise ValueError("cart_count no puede superar client_count.")
        if self.product_count * self.variants_per_product < self.branch_count * 2:
            raise ValueError("Se requieren al menos dos variantes por sucursal.")


@dataclass(frozen=True)
class SeedResult:
    inserted_rows: int
    counts: dict[str, int]


@dataclass(frozen=True)
class EmailRepairResult:
    users: int
    suppliers: int

    @property
    def updated_rows(self) -> int:
        return self.users + self.suppliers


DOMAIN_MODELS = (
    Ciudad,
    Sucursal,
    Categoria,
    Proveedor,
    Talla,
    Color,
    Temporada,
    Coleccion,
    Producto,
    VarianteProducto,
    ImagenProducto,
    Inventario,
    MovimientoInventario,
    Reserva,
    DetalleReserva,
    Carrito,
    DetalleCarrito,
    Pedido,
    DetallePedido,
    Pago,
    Reembolso,
    Devolucion,
    DetalleDevolucion,
)


def _seed_id(config: SeedConfig, entity: str, index: int) -> UUID:
    return uuid5(SEED_NAMESPACE, f"{config.seed}:{entity}:{index}")


def _at_noon(day: date) -> datetime:
    return datetime.combine(day, time(hour=12), tzinfo=UTC)


def _database_row_count(db: Session) -> int:
    total = 0
    for table in Base.metadata.sorted_tables:
        total += int(db.scalar(select(func.count()).select_from(table)) or 0)
    return total


def _ensure_seedable(db: Session) -> dict[str, Rol]:
    occupied = [
        model.__tablename__
        for model in DOMAIN_MODELS
        if int(db.scalar(select(func.count()).select_from(model)) or 0) > 0
    ]
    if occupied:
        raise SeedDataExistsError(
            "El seeder requiere tablas de negocio vacías. Hay datos en: "
            + ", ".join(occupied)
            + "."
        )
    if db.scalar(select(Usuario.id).where(Usuario.email.endswith(DEMO_EMAIL_SUFFIX))):
        raise SeedDataExistsError("Los usuarios demostrativos ya existen.")
    roles = {
        role.nombre: role
        for role in db.scalars(
            select(Rol).where(
                Rol.nombre.in_(("cliente", "administrador", "encargado", "cajero"))
            )
        )
    }
    missing = {"cliente", "administrador", "encargado", "cajero"} - roles.keys()
    if missing:
        raise RuntimeError(
            "Ejecuta las migraciones antes del seeder. Faltan roles: "
            + ", ".join(sorted(missing))
            + "."
        )
    return roles


def repair_legacy_demo_emails(db: Session) -> EmailRepairResult:
    """Corrige solo los correos creados por versiones antiguas del seeder."""

    users = list(
        db.scalars(
            select(Usuario).where(Usuario.email.endswith(LEGACY_DEMO_EMAIL_SUFFIX))
        )
    )
    suppliers = list(
        db.scalars(
            select(Proveedor).where(
                Proveedor.email.endswith(LEGACY_SUPPLIER_EMAIL_SUFFIX)
            )
        )
    )
    user_emails = {
        email.casefold(): user_id
        for user_id, email in db.execute(select(Usuario.id, Usuario.email))
    }
    supplier_emails = {
        email.casefold(): supplier_id
        for supplier_id, email in db.execute(
            select(Proveedor.id, Proveedor.email).where(
                Proveedor.email.is_not(None)
            )
        )
        if email is not None
    }

    user_updates: list[tuple[Usuario, str]] = []
    for user in users:
        legacy_alias = user.email.removesuffix(LEGACY_SUPPLIER_EMAIL_SUFFIX)
        if not re.fullmatch(
            r"(?:admin|encargado\d+|cajero\d+|cliente\d{3})\.demo",
            legacy_alias,
        ):
            continue
        alias = legacy_alias.removesuffix(".demo")
        target = str(EMAIL_VALIDATOR.validate_python(f"{alias}{DEMO_EMAIL_SUFFIX}"))
        owner = user_emails.get(target.casefold())
        if owner is not None and owner != user.id:
            raise RuntimeError(
                f"Ya existe otro usuario con el correo destino {target}."
            )
        user_updates.append((user, target))

    supplier_updates: list[tuple[Proveedor, str]] = []
    for supplier in suppliers:
        if supplier.email is None:
            continue
        alias = supplier.email.removesuffix(LEGACY_SUPPLIER_EMAIL_SUFFIX)
        if not re.fullmatch(r"proveedor\d{2}", alias):
            continue
        target = str(EMAIL_VALIDATOR.validate_python(f"{alias}{DEMO_EMAIL_SUFFIX}"))
        owner = supplier_emails.get(target.casefold())
        if owner is not None and owner != supplier.id:
            raise RuntimeError(
                f"Ya existe otro proveedor con el correo destino {target}."
            )
        supplier_updates.append((supplier, target))

    for user, target in user_updates:
        user.email = target
    for supplier, target in supplier_updates:
        supplier.email = target
    db.flush()
    return EmailRepairResult(
        users=len(user_updates),
        suppliers=len(supplier_updates),
    )


def _create_locations(
    db: Session, config: SeedConfig
) -> tuple[list[Ciudad], list[Sucursal]]:
    cities = [
        Ciudad(
            id=_seed_id(config, "city", index),
            nombre=name,
            departamento=department,
        )
        for index, (name, department) in enumerate(CITY_DATA[: config.city_count])
    ]
    branches: list[Sucursal] = []
    for index in range(config.branch_count):
        city = cities[index % len(cities)]
        branch_number = index // len(cities) + 1
        branches.append(
            Sucursal(
                id=_seed_id(config, "branch", index),
                ciudad_id=city.id,
                nombre=f"Sucursal {city.nombre} {branch_number}",
                direccion=f"Av. Comercial {100 + index}, zona central",
                telefono=f"{2 + index % 7}{2000000 + index:07d}",
                horario_informativo="Lunes a sábado de 09:00 a 20:00",
                activa=True,
            )
        )
    db.add_all([*cities, *branches])
    db.flush()
    return cities, branches


def _create_users(
    db: Session,
    config: SeedConfig,
    roles: dict[str, Rol],
    branches: list[Sucursal],
    password: str,
) -> tuple[list[Usuario], list[Usuario]]:
    shared_hash = hash_password(password)
    staff_specs = (
        ("admin", "Administrador", "Demo", "administrador", None),
        ("encargado1", "Elena", "Encargada", "encargado", branches[0]),
        ("encargado2", "Marco", "Encargado", "encargado", branches[1 % len(branches)]),
        ("cajero1", "Carla", "Caja", "cajero", branches[0]),
        ("cajero2", "Pablo", "Caja", "cajero", branches[1 % len(branches)]),
    )
    staff: list[Usuario] = []
    for index, (alias, first, last, role_name, branch) in enumerate(staff_specs):
        staff.append(
            Usuario(
                id=_seed_id(config, "staff", index),
                email=f"{alias}{DEMO_EMAIL_SUFFIX}",
                password_hash=shared_hash,
                nombres=first,
                apellidos=last,
                telefono=f"71000{index:03d}",
                activo=True,
                sucursal_id=branch.id if branch else None,
                creado_en=_at_noon(config.anchor_date - timedelta(days=400 - index)),
                roles=[roles[role_name]],
            )
        )

    clients: list[Usuario] = []
    for index in range(config.client_count):
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[(index * 3) % len(LAST_NAMES)]
        client = Usuario(
            id=_seed_id(config, "client", index),
            email=f"cliente{index + 1:03d}{DEMO_EMAIL_SUFFIX}",
            password_hash=shared_hash,
            nombres=first,
            apellidos=f"{last} {index + 1:03d}",
            telefono=f"7{1000000 + index:07d}",
            activo=True,
            creado_en=_at_noon(
                config.anchor_date - timedelta(days=365 - (index * 5) % 330)
            ),
            roles=[roles["cliente"]],
        )
        client.perfil_cliente = PerfilCliente(
            id=_seed_id(config, "profile", index),
            direccion=f"Calle Demo {index + 1}, {CITY_DATA[index % config.city_count][0]}",
            preferencias_json={
                "estilo": STYLES[index % len(STYLES)],
                "color": COLOR_DATA[index % len(COLOR_DATA)][0],
            },
        )
        clients.append(client)
    db.add_all([*staff, *clients])
    db.flush()
    return staff, clients


def _create_catalog(
    db: Session, config: SeedConfig
) -> tuple[list[Producto], list[VarianteProducto]]:
    categories = [
        Categoria(
            id=_seed_id(config, "category", index),
            nombre=name,
            descripcion=f"Selección demostrativa de {name.lower()}.",
            activa=True,
        )
        for index, name in enumerate(CATEGORY_NAMES)
    ]
    suppliers = [
        Proveedor(
            id=_seed_id(config, "supplier", index),
            nombre=f"Proveedor Textil {index + 1:02d}",
            nit=f"10203040{index + 1:02d}",
            telefono=f"3{3000000 + index:07d}",
            email=f"proveedor{index + 1:02d}{DEMO_EMAIL_SUFFIX}",
            direccion=f"Parque industrial, bloque {index + 1}",
            activo=True,
        )
        for index in range(10)
    ]
    sizes = [
        Talla(id=_seed_id(config, "size", index), nombre=name, orden=order)
        for index, (name, order) in enumerate(SIZE_DATA)
    ]
    colors = [
        Color(id=_seed_id(config, "color", index), nombre=name, codigo_hex=hex_code)
        for index, (name, hex_code) in enumerate(COLOR_DATA)
    ]
    seasons: list[Temporada] = []
    for index, name in enumerate(("Verano", "Otoño", "Invierno", "Primavera")):
        start = date(config.anchor_date.year, 1 + index * 3, 1)
        end_month = 3 + index * 3
        end = date(config.anchor_date.year, end_month, 28)
        seasons.append(
            Temporada(
                id=_seed_id(config, "season", index),
                nombre=f"{name} {config.anchor_date.year}",
                fecha_inicio=start,
                fecha_fin=end,
                activa=True,
            )
        )
    collections = [
        Coleccion(
            id=_seed_id(config, "collection", index),
            temporada_id=seasons[index // 2].id,
            nombre=f"{('Esencial', 'Tendencia')[index % 2]} {seasons[index // 2].nombre}",
            descripcion="Colección demostrativa para catálogo y reportes.",
        )
        for index in range(8)
    ]
    db.add_all([*categories, *suppliers, *sizes, *colors, *seasons, *collections])

    products: list[Producto] = []
    variants: list[VarianteProducto] = []
    images: list[ImagenProducto] = []
    for index in range(config.product_count):
        category = categories[index % len(categories)]
        season = seasons[index % len(seasons)]
        collection = collections[(index % len(seasons)) * 2 + (index // 4) % 2]
        price = Decimal(65 + (index * 13) % 430) + (
            Decimal("0.50") if index % 2 else Decimal("0.00")
        )
        product = Producto(
            id=_seed_id(config, "product", index),
            categoria_id=category.id,
            proveedor_id=suppliers[index % len(suppliers)].id,
            temporada_id=season.id,
            coleccion_id=collection.id,
            nombre=f"{category.nombre} {STYLES[index % len(STYLES)]} {index + 1:03d}",
            descripcion="Prenda demostrativa con datos coherentes para catálogo y ventas.",
            marca=BRANDS[index % len(BRANDS)],
            precio_base=price.quantize(Decimal("0.01")),
            activo=True,
        )
        products.append(product)
        images.append(
            ImagenProducto(
                id=_seed_id(config, "image", index),
                producto_id=product.id,
                url=f"https://placehold.co/800x1000/png?text=Producto+{index + 1:03d}",
                es_principal=True,
                orden=0,
            )
        )
        for variant_index in range(config.variants_per_product):
            global_index = index * config.variants_per_product + variant_index
            variants.append(
                VarianteProducto(
                    id=_seed_id(config, "variant", global_index),
                    producto_id=product.id,
                    talla_id=sizes[(index + variant_index) % len(sizes)].id,
                    color_id=colors[(index * 2 + variant_index) % len(colors)].id,
                    sku=f"DEMO-{index + 1:04d}-{variant_index + 1}",
                    precio=(
                        None
                        if variant_index == 0
                        else (price + Decimal(variant_index * 10)).quantize(Decimal("0.01"))
                    ),
                    activa=True,
                )
            )
    db.add_all([*products, *variants, *images])
    db.flush()
    return products, variants


def _create_inventory(
    db: Session,
    config: SeedConfig,
    branches: list[Sucursal],
    variants: list[VarianteProducto],
    admin: Usuario,
) -> dict[UUID, list[Inventario]]:
    service = InventoryService(db)
    by_branch: dict[UUID, list[Inventario]] = {branch.id: [] for branch in branches}
    for index, variant in enumerate(variants):
        branch = branches[index % len(branches)]
        item = service.receive(
            RecepcionCreate(
                sucursal_id=branch.id,
                variante_id=variant.id,
                cantidad=40 + (index * 7) % 51,
                observacion="Inventario inicial generado por el seeder demostrativo",
            ),
            user=admin,
            commit=False,
        )
        by_branch[branch.id].append(item)
    return by_branch


def _create_reservations(
    db: Session,
    config: SeedConfig,
    clients: list[Usuario],
    branches: list[Sucursal],
    inventory_by_branch: dict[UUID, list[Inventario]],
) -> list[Reserva]:
    inventory = InventoryService(db)
    reservations: list[Reserva] = []
    converted_count = min(5, config.reservation_count, config.order_count)
    other_states = ("PENDIENTE", "CONFIRMADA", "PREPARADA", "CANCELADA", "VENCIDA")
    for index in range(config.reservation_count):
        branch = branches[index % len(branches)]
        state = "COMPLETADA" if index < converted_count else other_states[index % 5]
        is_active = state in {"PENDIENTE", "CONFIRMADA", "PREPARADA"}
        visit_date = (
            config.anchor_date + timedelta(days=2 + index % 12)
            if is_active
            else config.anchor_date - timedelta(days=5 + index * 3)
        )
        created_at = _at_noon(visit_date - timedelta(days=3))
        reservation = Reserva(
            id=_seed_id(config, "reservation", index),
            cliente_id=clients[index % len(clients)].id,
            sucursal_id=branch.id,
            estado=state,
            fecha_visita=visit_date,
            hora_aproximada=time(hour=10 + index % 8),
            vence_en=datetime.combine(visit_date, time.max, tzinfo=UTC),
            creada_en=created_at,
            cancelada_en=(
                created_at + timedelta(days=2)
                if state in {"CANCELADA", "VENCIDA"}
                else None
            ),
        )
        available = inventory_by_branch[branch.id]
        line_count = 2 if index % 3 == 0 else 1
        details: list[DetalleReserva] = []
        for line_index in range(line_count):
            item = available[(index * 3 + line_index) % len(available)]
            detail = DetalleReserva(
                id=_seed_id(config, f"reservation-detail-{index}", line_index),
                reserva_id=reservation.id,
                inventario_id=item.id,
                cantidad=1,
            )
            details.append(detail)
        reservation.detalles = details
        db.add(reservation)
        db.flush()
        for detail in details:
            item = detail.inventario
            inventory.reserve(
                branch.id,
                item.variante_id,
                detail.cantidad,
                reference_id=reservation.id,
            )
            if state in {"CANCELADA", "VENCIDA"}:
                inventory.release_reservation(
                    branch.id,
                    item.variante_id,
                    detail.cantidad,
                    reference_id=reservation.id,
                )
        reservations.append(reservation)
    return reservations


def _price(variant: VarianteProducto) -> Decimal:
    return Decimal(variant.precio or variant.producto.precio_base).quantize(Decimal("0.01"))


def _create_order(
    db: Session,
    config: SeedConfig,
    *,
    index: int,
    client: Usuario | None,
    branch: Sucursal,
    selected: list[tuple[Inventario, int]],
    channel: str,
    state: str,
    created_at: datetime,
    reservation: Reserva | None = None,
) -> tuple[Pedido, Pago, list[DetallePedido]]:
    order_id = _seed_id(config, "order", index)
    details: list[DetallePedido] = []
    subtotal = Decimal("0.00")
    for line_index, (item, quantity) in enumerate(selected):
        unit_price = _price(item.variante)
        line_subtotal = unit_price * quantity
        details.append(
            DetallePedido(
                id=_seed_id(config, f"order-detail-{index}", line_index),
                pedido_id=order_id,
                variante_id=item.variante_id,
                cantidad=quantity,
                precio_unitario=unit_price,
                subtotal=line_subtotal,
            )
        )
        subtotal += line_subtotal
    order = Pedido(
        id=order_id,
        cliente_id=client.id if client else None,
        sucursal_id=branch.id,
        reserva_id=reservation.id if reservation else None,
        canal=channel,
        estado=state,
        subtotal=subtotal,
        descuento=Decimal("0.00"),
        total=subtotal,
        creado_en=created_at,
        detalles=details,
    )
    db.add(order)
    db.flush()

    inventory = InventoryService(db)
    for item, quantity in selected:
        inventory.sell(
            branch.id,
            item.variante_id,
            quantity,
            from_reservation=reservation is not None,
            reference_id=order.id,
        )

    is_pos = channel == "POS"
    payment_state = (
        "PENDIENTE"
        if state == "CREADO"
        else "RECHAZADO" if state == "CANCELADO" else "APROBADO"
    )
    payment = Pago(
        id=_seed_id(config, "payment", index),
        pedido_id=order.id,
        metodo="CAJA" if is_pos else "PASARELA_PRUEBA",
        estado=payment_state,
        monto=order.total,
        referencia_externa=(
            f"SEED-POS-{index + 1:04d}" if is_pos else f"SEED-TEST-{index + 1:04d}"
        ),
        creado_en=created_at + timedelta(minutes=5),
        pagado_en=(
            created_at + timedelta(minutes=6)
            if payment_state == "APROBADO"
            else None
        ),
    )
    db.add(payment)
    db.flush()
    if state == "CANCELADO":
        for item, quantity in selected:
            inventory.return_stock(
                branch.id,
                item.variante_id,
                quantity,
                reference_id=payment.id,
                reference_type="PAGO",
                observation="Reposición por pago rechazado de datos demo",
            )
    return order, payment, details


def _create_orders(
    db: Session,
    config: SeedConfig,
    clients: list[Usuario],
    branches: list[Sucursal],
    inventory_by_branch: dict[UUID, list[Inventario]],
    reservations: list[Reserva],
) -> list[tuple[Pedido, Pago, list[DetallePedido]]]:
    records: list[tuple[Pedido, Pago, list[DetallePedido]]] = []
    converted = [item for item in reservations if item.estado == "COMPLETADA"][:5]
    for index, reservation in enumerate(converted):
        selected = [
            (detail.inventario, detail.cantidad) for detail in reservation.detalles
        ]
        records.append(
            _create_order(
                db,
                config,
                index=index,
                client=reservation.cliente,
                branch=reservation.sucursal,
                selected=selected,
                channel="WEB",
                state="PAGADO",
                created_at=reservation.creada_en + timedelta(days=4),
                reservation=reservation,
            )
        )

    for index in range(len(converted), config.order_count):
        branch = branches[index % len(branches)]
        available = inventory_by_branch[branch.id]
        line_count = 2 if index % 3 != 0 else 1
        selected = [
            (available[(index * 5 + line) % len(available)], 1 + (index + line) % 3)
            for line in range(line_count)
        ]
        channel = ("WEB", "WEB", "MOBILE", "POS")[index % 4]
        if channel == "POS":
            state = "COMPLETADO"
        elif index % 23 == 0:
            state = "CREADO"
        elif index % 19 == 0:
            state = "CANCELADO"
        else:
            state = "PAGADO"
        created_at = _at_noon(
            config.anchor_date - timedelta(days=(index * 11) % 365)
        ) + timedelta(hours=index % 8)
        client = None if channel == "POS" and index % 5 == 0 else clients[index % len(clients)]
        records.append(
            _create_order(
                db,
                config,
                index=index,
                client=client,
                branch=branch,
                selected=selected,
                channel=channel,
                state=state,
                created_at=created_at,
            )
        )
    return records


def _create_returns(
    db: Session,
    config: SeedConfig,
    records: list[tuple[Pedido, Pago, list[DetallePedido]]],
    inventory_by_branch: dict[UUID, list[Inventario]],
) -> int:
    candidates = [record for record in records if record[1].estado == "APROBADO"]
    inventory = InventoryService(db)
    states = ("SOLICITADA", "APROBADA", "CANCELADA", "COMPLETADA")
    selected_candidates = candidates[: config.return_count]
    for index, (order, payment, order_details) in enumerate(selected_candidates):
        state = states[index % len(states)]
        detail = order_details[0]
        created_at = min(
            _at_noon(config.anchor_date),
            order.creado_en + timedelta(days=3 + index % 10),
        )
        completed = state == "COMPLETADA"
        return_request = Devolucion(
            id=_seed_id(config, "return", index),
            pedido_id=order.id,
            cliente_id=order.cliente_id,
            estado=state,
            motivo_general=(
                "La talla no era adecuada" if index % 2 == 0 else "Cambio de preferencia"
            ),
            reingresa_stock=True if completed else None,
            genera_reembolso=True if completed else None,
            creada_en=created_at,
            completada_en=created_at + timedelta(days=2) if completed else None,
        )
        return_detail = DetalleDevolucion(
            id=_seed_id(config, "return-detail", index),
            devolucion_id=return_request.id,
            detalle_pedido_id=detail.id,
            cantidad=1,
            motivo="Producto sin señales de uso",
        )
        return_request.detalles = [return_detail]
        db.add(return_request)
        db.flush()
        if not completed:
            continue
        item = next(
            item
            for item in inventory_by_branch[order.sucursal_id]
            if item.variante_id == detail.variante_id
        )
        inventory.return_stock(
            order.sucursal_id,
            item.variante_id,
            1,
            reference_id=return_request.id,
            observation="Reingreso por devolución de datos demo",
        )
        refund_amount = detail.precio_unitario
        refund = Reembolso(
            id=_seed_id(config, "refund", index),
            pago_id=payment.id,
            devolucion_id=return_request.id,
            monto=refund_amount,
            motivo=return_request.motivo_general or "Devolución demo",
            referencia_externa=f"SEED-REF-{index + 1:04d}",
            creado_en=return_request.completada_en or created_at,
        )
        db.add(refund)
        if refund_amount == payment.monto:
            payment.estado = "REEMBOLSADO"
            order.estado = "REEMBOLSADO"
    return len(selected_candidates)


def _create_carts(
    db: Session,
    config: SeedConfig,
    clients: list[Usuario],
    variants: list[VarianteProducto],
) -> None:
    for index, client in enumerate(clients[: config.cart_count]):
        cart = Carrito(
            id=_seed_id(config, "cart", index),
            cliente_id=client.id,
            activo=True,
            creado_en=_at_noon(config.anchor_date - timedelta(days=index % 8)),
            actualizado_en=_at_noon(config.anchor_date),
        )
        line_count = 2 if index % 3 else 1
        cart.detalles = [
            DetalleCarrito(
                id=_seed_id(config, f"cart-detail-{index}", line),
                carrito_id=cart.id,
                variante_id=variants[(index * 7 + line) % len(variants)].id,
                cantidad=1 + (index + line) % 2,
            )
            for line in range(line_count)
        ]
        db.add(cart)


def seed_database(db: Session, config: SeedConfig, *, password: str) -> SeedResult:
    """Crea el conjunto demo sin hacer commit; el llamador controla la transacción."""

    config.validate()
    if len(password) < 8:
        raise ValueError("La contraseña demo debe tener al menos 8 caracteres.")
    roles = _ensure_seedable(db)
    before = _database_row_count(db)
    _cities, branches = _create_locations(db, config)
    staff, clients = _create_users(db, config, roles, branches, password)
    products, variants = _create_catalog(db, config)
    inventory_by_branch = _create_inventory(
        db, config, branches, variants, staff[0]
    )
    reservations = _create_reservations(
        db, config, clients, branches, inventory_by_branch
    )
    order_records = _create_orders(
        db, config, clients, branches, inventory_by_branch, reservations
    )
    return_count = _create_returns(db, config, order_records, inventory_by_branch)
    _create_carts(db, config, clients, variants)
    db.flush()
    after = _database_row_count(db)
    return SeedResult(
        inserted_rows=after - before,
        counts={
            "ciudades": config.city_count,
            "sucursales": config.branch_count,
            "clientes": config.client_count,
            "personal": len(staff),
            "categorias": len(CATEGORY_NAMES),
            "productos": len(products),
            "variantes": len(variants),
            "pedidos": len(order_records),
            "reservas": len(reservations),
            "devoluciones": return_count,
            "carritos": min(config.cart_count, len(clients)),
        },
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Usa el formato AAAA-MM-DD.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument("--fecha-base", type=_parse_date, default=date.today())
    parser.add_argument("--clientes", type=int, default=70)
    parser.add_argument("--productos", type=int, default=160)
    parser.add_argument("--pedidos", type=int, default=240)
    execution_mode = parser.add_mutually_exclusive_group()
    execution_mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra la configuración sin conectarse ni escribir en PostgreSQL.",
    )
    execution_mode.add_argument(
        "--reparar-emails",
        action="store_true",
        help="Corrige los correos .test creados por una versión anterior.",
    )
    return parser


def _password() -> str:
    from_environment = os.getenv("DEMO_SEED_PASSWORD")
    if from_environment:
        return from_environment
    password = getpass("Contraseña para todas las cuentas demo: ")
    confirmation = getpass("Repite la contraseña demo: ")
    if password != confirmation:
        raise SystemExit("Las contraseñas no coinciden.")
    return password


def main() -> None:
    args = build_parser().parse_args()
    if args.reparar_emails:
        try:
            with SessionLocal.begin() as db:
                repair = repair_legacy_demo_emails(db)
        except SQLAlchemyError as exc:
            raise SystemExit(
                "No se pudieron reparar los correos: falló la transacción de "
                "base de datos. Revisa PostgreSQL y las migraciones."
            ) from exc
        except RuntimeError as exc:
            raise SystemExit(f"No se pudieron reparar los correos: {exc}") from exc
        print(f"Reparación completada: {repair.updated_rows} correos actualizados.")
        print(f"- usuarios: {repair.users}")
        print(f"- proveedores: {repair.suppliers}")
        return

    config = SeedConfig(
        seed=args.seed,
        anchor_date=args.fecha_base,
        client_count=args.clientes,
        product_count=args.productos,
        order_count=args.pedidos,
    )
    try:
        config.validate()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.dry_run:
        print("Seeder demostrativo (sin escritura)")
        print(f"Ciudades: {config.city_count}; sucursales: {config.branch_count}")
        print(f"Clientes: {config.client_count}; personal: 5")
        print(
            f"Productos: {config.product_count}; variantes: "
            f"{config.product_count * config.variants_per_product}"
        )
        print(f"Pedidos: {config.order_count}; fecha base: {config.anchor_date}")
        return

    password = _password()
    try:
        with SessionLocal.begin() as db:
            result = seed_database(db, config, password=password)
    except SQLAlchemyError as exc:
        raise SystemExit(
            "No se pudo ejecutar el seeder: falló la transacción de base de datos. "
            "Revisa PostgreSQL y las migraciones."
        ) from exc
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(f"No se pudo ejecutar el seeder: {exc}") from exc

    print(f"Seeder completado: {result.inserted_rows} filas insertadas.")
    for name, count in result.counts.items():
        print(f"- {name}: {count}")
    print("Cuentas principales: admin@demo.example.com,")
    print("encargado1@demo.example.com, cajero1@demo.example.com y")
    print("cliente001@demo.example.com")


if __name__ == "__main__":
    main()
