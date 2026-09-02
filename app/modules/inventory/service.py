"""Casos de uso transaccionales de inventario."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.branches.models import Sucursal
from app.modules.branches.repository import BranchRepository
from app.modules.catalog.models import VarianteProducto
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.service import CatalogService
from app.modules.inventory.models import Inventario, MovimientoInventario, TipoMovimiento
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import AjusteCreate, EstadoStock, RecepcionCreate
from app.modules.users.models import Usuario


class InventoryService:
    """Autoridad unica para leer y modificar existencias."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory = InventoryRepository(db)
        self.branches = BranchRepository(db)
        self.catalog = CatalogRepository(db)

    def list_inventory(
        self,
        *,
        user: Usuario,
        page: int,
        page_size: int,
        branch_id: UUID | None,
        city_id: UUID | None,
        product_id: UUID | None,
        variant_id: UUID | None,
        state: EstadoStock | None,
    ) -> tuple[list[Inventario], int]:
        branch_id = self._scoped_branch(user, branch_id)
        if not self._is_admin(user):
            city_id = None
        return self.inventory.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            branch_id=branch_id,
            city_id=city_id,
            product_id=product_id,
            variant_id=variant_id,
            state=state,
        )

    def get_inventory(self, inventory_id: UUID, *, user: Usuario) -> Inventario:
        item = self.inventory.get_by_id(inventory_id)
        if item is None:
            raise NotFoundError("Registro de inventario no encontrado.")
        self._ensure_branch_scope(user, item.sucursal_id)
        return item

    def list_movements(
        self, inventory_id: UUID, *, user: Usuario, page: int, page_size: int
    ) -> tuple[list[MovimientoInventario], int]:
        self.get_inventory(inventory_id, user=user)
        return self.inventory.list_movements(
            inventory_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    def options(self, *, user: Usuario) -> tuple[list[Sucursal], list[object]]:
        if self._is_admin(user):
            branches, _ = self.branches.list(
                offset=0, limit=200, query=None, city_id=None, active=True
            )
        else:
            branch_id = self._scoped_branch(user, None)
            branch = self.branches.get_by_id(branch_id)
            branches = [branch] if branch and branch.activa else []
        products, _ = CatalogService(self.db).list_products(
            page=1,
            page_size=100,
            query=None,
            category_id=None,
            season_id=None,
            size_id=None,
            color_id=None,
            public=True,
        )
        return branches, products

    def public_availability(self, product_id: UUID) -> list[Inventario]:
        if self.catalog.get_product(product_id, public=True) is None:
            raise NotFoundError("Producto no encontrado.")
        return self.inventory.list_public_availability(product_id)

    def receive(self, data: RecepcionCreate, *, user: Usuario) -> Inventario:
        self._ensure_branch_scope(user, data.sucursal_id)
        _branch, variant = self._validate_active_references(data.sucursal_id, data.variante_id)
        item = self._get_or_create_locked(data.sucursal_id, data.variante_id)
        item.stock_fisico += data.cantidad
        self._add_movement(
            item,
            TipoMovimiento.RECEPCION,
            data.cantidad,
            reference_type="PROVEEDOR",
            reference_id=variant.producto.proveedor_id,
            observation=data.observacion,
        )
        return self._complete(item, commit=True)

    def adjust(self, data: AjusteCreate, *, user: Usuario) -> Inventario:
        self._ensure_branch_scope(user, data.sucursal_id)
        self._validate_active_references(data.sucursal_id, data.variante_id)
        item = self.inventory.get_by_branch_variant(
            data.sucursal_id, data.variante_id, for_update=True
        )
        if item is None:
            if data.cantidad < 0:
                raise ConflictError("El ajuste dejaria el stock fisico en negativo.")
            item = self._get_or_create_locked(data.sucursal_id, data.variante_id)
        resulting_physical = item.stock_fisico + data.cantidad
        if resulting_physical < 0:
            raise ConflictError("El ajuste dejaria el stock fisico en negativo.")
        if resulting_physical < item.stock_reservado:
            raise ConflictError("El ajuste no puede reducir el stock por debajo de lo reservado.")
        item.stock_fisico = resulting_physical
        self._add_movement(
            item,
            TipoMovimiento.AJUSTE,
            data.cantidad,
            observation=data.motivo,
        )
        return self._complete(item, commit=True)

    def reserve(
        self,
        branch_id: UUID,
        variant_id: UUID,
        quantity: int,
        *,
        reference_id: UUID | None = None,
        commit: bool = False,
    ) -> Inventario:
        self._ensure_positive(quantity)
        item = self._get_existing_locked(branch_id, variant_id)
        if item.stock_disponible < quantity:
            raise ConflictError("Stock disponible insuficiente para la reserva.")
        item.stock_reservado += quantity
        self._add_movement(
            item,
            TipoMovimiento.RESERVA,
            quantity,
            reference_type="RESERVA" if reference_id else None,
            reference_id=reference_id,
        )
        return self._complete(item, commit=commit)

    def release_reservation(
        self,
        branch_id: UUID,
        variant_id: UUID,
        quantity: int,
        *,
        reference_id: UUID | None = None,
        commit: bool = False,
    ) -> Inventario:
        self._ensure_positive(quantity)
        item = self._get_existing_locked(branch_id, variant_id)
        if item.stock_reservado < quantity:
            raise ConflictError("No existe suficiente stock reservado para liberar.")
        item.stock_reservado -= quantity
        self._add_movement(
            item,
            TipoMovimiento.LIBERACION_RESERVA,
            -quantity,
            reference_type="RESERVA" if reference_id else None,
            reference_id=reference_id,
        )
        return self._complete(item, commit=commit)

    def sell(
        self,
        branch_id: UUID,
        variant_id: UUID,
        quantity: int,
        *,
        from_reservation: bool = False,
        reference_id: UUID | None = None,
        commit: bool = False,
    ) -> Inventario:
        self._ensure_positive(quantity)
        item = self._get_existing_locked(branch_id, variant_id)
        if from_reservation:
            if item.stock_reservado < quantity:
                raise ConflictError("Stock reservado insuficiente para completar la venta.")
            item.stock_reservado -= quantity
        elif item.stock_disponible < quantity:
            raise ConflictError("Stock disponible insuficiente para completar la venta.")
        item.stock_fisico -= quantity
        self._add_movement(
            item,
            TipoMovimiento.VENTA,
            -quantity,
            reference_type="VENTA" if reference_id else None,
            reference_id=reference_id,
        )
        return self._complete(item, commit=commit)

    def return_stock(
        self,
        branch_id: UUID,
        variant_id: UUID,
        quantity: int,
        *,
        reference_id: UUID | None = None,
        commit: bool = False,
    ) -> Inventario:
        self._ensure_positive(quantity)
        item = self._get_or_create_locked(branch_id, variant_id)
        item.stock_fisico += quantity
        self._add_movement(
            item,
            TipoMovimiento.DEVOLUCION,
            quantity,
            reference_type="DEVOLUCION" if reference_id else None,
            reference_id=reference_id,
        )
        return self._complete(item, commit=commit)

    def _validate_active_references(
        self, branch_id: UUID, variant_id: UUID
    ) -> tuple[Sucursal, VarianteProducto]:
        branch = self.branches.get_by_id(branch_id)
        if branch is None:
            raise NotFoundError("Sucursal no encontrada.")
        if not branch.activa:
            raise ConflictError("La sucursal debe estar activa para modificar inventario.")
        variant = self.catalog.get_variant(variant_id)
        if variant is None:
            raise NotFoundError("Variante de producto no encontrada.")
        if not variant.activa or not variant.producto.activo:
            raise ConflictError("El producto y su variante deben estar activos.")
        return branch, variant

    def _get_or_create_locked(self, branch_id: UUID, variant_id: UUID) -> Inventario:
        item = self.inventory.get_by_branch_variant(branch_id, variant_id, for_update=True)
        if item is None:
            item = Inventario(
                sucursal_id=branch_id,
                variante_id=variant_id,
                stock_fisico=0,
                stock_reservado=0,
            )
            self.inventory.add_inventory(item)
            self._flush_or_conflict("Ya existe inventario para esa sucursal y variante.")
        return item

    def _get_existing_locked(self, branch_id: UUID, variant_id: UUID) -> Inventario:
        item = self.inventory.get_by_branch_variant(branch_id, variant_id, for_update=True)
        if item is None:
            raise ConflictError("No existe stock para la sucursal y variante indicadas.")
        return item

    def _add_movement(
        self,
        item: Inventario,
        movement_type: TipoMovimiento,
        quantity: int,
        *,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
        observation: str | None = None,
    ) -> None:
        if item.id is None:
            self.db.flush()
        self.inventory.add_movement(
            MovimientoInventario(
                inventario_id=item.id,
                tipo=movement_type.value,
                cantidad=quantity,
                referencia_tipo=reference_type,
                referencia_id=reference_id,
                observacion=observation,
            )
        )

    def _complete(self, item: Inventario, *, commit: bool) -> Inventario:
        self._flush_or_conflict("No se pudo registrar el movimiento de inventario.")
        if not commit:
            return item
        inventory_id = item.id
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo registrar el movimiento de inventario.") from exc
        return self.inventory.get_by_id(inventory_id)  # type: ignore[return-value]

    def _flush_or_conflict(self, message: str) -> None:
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(message) from exc

    def _scoped_branch(self, user: Usuario, requested: UUID | None) -> UUID | None:
        if self._is_admin(user):
            return requested
        if user.sucursal_id is None:
            raise ForbiddenError("Tu usuario no tiene una sucursal asignada.")
        if requested is not None and requested != user.sucursal_id:
            raise ForbiddenError("Solo puedes consultar el inventario de tu sucursal.")
        return user.sucursal_id

    def _ensure_branch_scope(self, user: Usuario, branch_id: UUID) -> None:
        self._scoped_branch(user, branch_id)

    @staticmethod
    def _is_admin(user: Usuario) -> bool:
        return any(role.nombre == "administrador" for role in user.roles)

    @staticmethod
    def _ensure_positive(quantity: int) -> None:
        if quantity <= 0:
            raise ConflictError("La cantidad debe ser mayor que cero.")
