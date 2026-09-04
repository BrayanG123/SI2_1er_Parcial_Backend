"""Pruebas de reportes reproducibles, filtros y alcance por sucursal."""

from datetime import UTC, date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.branches.models import Sucursal
from app.modules.catalog.models import VarianteProducto
from tests.integration.test_cart_orders import (
    add_to_cart,
    auth_identity,
    client,
    db,
    load_stock,
    sales_context,
)


def _prepare_report_data(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> dict[str, object]:
    branch = sales_context["branch"]
    other_branch = sales_context["other_branch"]
    variants = sales_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(other_branch, Sucursal)
    assert isinstance(variants, list) and all(
        isinstance(item, VarianteProducto) for item in variants
    )

    admin, admin_headers = auth_identity(
        client, db, "administrador", suffix="reports-admin"
    )
    customer, customer_headers = auth_identity(
        client, db, "cliente", suffix="reports-customer"
    )
    _, manager_headers = auth_identity(
        client, db, "encargado", suffix="reports-manager", branch=branch
    )
    _, other_manager_headers = auth_identity(
        client, db, "encargado", suffix="reports-other-manager", branch=other_branch
    )
    _, cashier_headers = auth_identity(
        client, db, "cajero", suffix="reports-cashier", branch=branch
    )
    load_stock(client, admin_headers, branch, variants)

    add_to_cart(client, customer_headers, variants[0], 2)
    web_response = client.post(
        "/api/v1/orders/checkout",
        headers=customer_headers,
        json={"sucursal_id": str(branch.id)},
    )
    assert web_response.status_code == 201, web_response.text
    web_order = web_response.json()
    payment = client.post(
        f"/api/v1/payments/orders/{web_order['id']}", headers=customer_headers
    )
    assert payment.status_code == 201, payment.text
    confirmed = client.post(
        f"/api/v1/payments/{payment.json()['id']}/confirm",
        headers=customer_headers,
        json={"resultado_prueba": "APROBAR"},
    )
    assert confirmed.status_code == 200, confirmed.text

    pos_response = client.post(
        "/api/v1/orders/pos",
        headers=admin_headers,
        json={
            "sucursal_id": str(branch.id),
            "detalles": [{"variante_id": str(variants[1].id), "cantidad": 1}],
        },
    )
    assert pos_response.status_code == 201, pos_response.text

    requested = client.post(
        "/api/v1/returns",
        headers=customer_headers,
        json={
            "pedido_id": web_order["id"],
            "detalles": [
                {
                    "detalle_pedido_id": web_order["detalles"][0]["id"],
                    "cantidad": 1,
                }
            ],
        },
    )
    assert requested.status_code == 201, requested.text
    return_id = requested.json()["id"]
    approved = client.patch(
        f"/api/v1/returns/manage/{return_id}/status",
        headers=manager_headers,
        json={"estado": "APROBADA"},
    )
    assert approved.status_code == 200, approved.text
    completed = client.patch(
        f"/api/v1/returns/manage/{return_id}/status",
        headers=manager_headers,
        json={
            "estado": "COMPLETADA",
            "reingresar_stock": True,
            "generar_reembolso": True,
        },
    )
    assert completed.status_code == 200, completed.text

    reservation = client.post(
        "/api/v1/reservations",
        headers=customer_headers,
        json={
            "sucursal_id": str(branch.id),
            "fecha_visita": str(date.today() + timedelta(days=1)),
            "detalles": [{"variante_id": str(variants[0].id), "cantidad": 2}],
        },
    )
    assert reservation.status_code == 201, reservation.text
    cancelled = client.post(
        f"/api/v1/reservations/{reservation.json()['id']}/cancel",
        headers=customer_headers,
    )
    assert cancelled.status_code == 200, cancelled.text

    return {
        "branch": branch,
        "other_branch": other_branch,
        "admin": admin,
        "admin_headers": admin_headers,
        "customer_headers": customer_headers,
        "manager_headers": manager_headers,
        "other_manager_headers": other_manager_headers,
        "cashier_headers": cashier_headers,
    }


def _state_count(rows: list[dict], state: str) -> int:
    return next(item["cantidad"] for item in rows if item["estado"] == state)


def test_dashboard_has_known_sales_inventory_reservations_and_returns(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    context = _prepare_report_data(client, db, sales_context)
    branch = context["branch"]
    assert isinstance(branch, Sucursal)
    today = datetime.now(UTC).date()
    response = client.get(
        "/api/v1/reports/dashboard",
        headers=context["admin_headers"],
        params={
            "branch_id": str(branch.id),
            "date_from": str(today),
            "date_to": str(today),
        },
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["filtros"] == {
        "fecha_desde": str(today),
        "fecha_hasta": str(today),
        "sucursal_id": str(branch.id),
    }
    sales = report["ventas"]
    assert sales["resumen"] == {
        "pedidos": 2,
        "unidades": 3,
        "venta_bruta": "255.00",
        "reembolsos": "80.00",
        "venta_neta": "175.00",
        "ticket_promedio": "127.50",
    }
    assert sum(item["pedidos"] for item in sales["por_canal"]) == 2
    assert sales["productos_destacados"][0]["producto_nombre"] == "Polera básica"
    assert sales["productos_destacados"][0]["unidades"] == 3

    inventory = report["inventario"]["resumen"]
    assert inventory["registros"] == 2
    assert inventory["stock_fisico"] == 18
    assert inventory["stock_reservado"] == 0
    assert inventory["stock_disponible"] == 18
    assert inventory["agotados"] == 0 and inventory["stock_bajo"] == 0

    reservations = report["reservas"]
    assert reservations["resumen"]["reservas"] == 1
    assert reservations["resumen"]["unidades"] == 2
    assert _state_count(reservations["por_estado"], "CANCELADA") == 1

    returns = report["devoluciones"]
    assert returns["resumen"] == {
        "devoluciones": 1,
        "unidades": 1,
        "monto_solicitado": "80.00",
        "monto_reembolsado": "80.00",
    }
    assert _state_count(returns["por_estado"], "COMPLETADA") == 1


def test_report_period_filters_apply_only_to_historical_sections(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    context = _prepare_report_data(client, db, sales_context)
    past = date(2020, 1, 1)
    response = client.get(
        "/api/v1/reports/dashboard",
        headers=context["admin_headers"],
        params={"date_from": str(past), "date_to": str(past)},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["ventas"]["resumen"]["pedidos"] == 0
    assert report["reservas"]["resumen"]["reservas"] == 0
    assert report["devoluciones"]["resumen"]["devoluciones"] == 0
    assert report["inventario"]["resumen"]["stock_fisico"] == 18

    invalid = client.get(
        "/api/v1/reports/sales",
        headers=context["admin_headers"],
        params={"date_from": "2026-09-10", "date_to": "2026-09-01"},
    )
    assert invalid.status_code == 409


def test_report_roles_and_branch_scope_are_enforced(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    context = _prepare_report_data(client, db, sales_context)
    branch = context["branch"]
    other_branch = context["other_branch"]
    assert isinstance(branch, Sucursal) and isinstance(other_branch, Sucursal)

    options = client.get(
        "/api/v1/reports/options", headers=context["manager_headers"]
    )
    assert options.status_code == 200
    assert [item["id"] for item in options.json()["sucursales"]] == [str(branch.id)]

    own = client.get(
        "/api/v1/reports/sales", headers=context["manager_headers"]
    )
    assert own.status_code == 200 and own.json()["resumen"]["pedidos"] == 2
    assert client.get(
        "/api/v1/reports/sales",
        headers=context["manager_headers"],
        params={"branch_id": str(other_branch.id)},
    ).status_code == 403
    other = client.get(
        "/api/v1/reports/dashboard", headers=context["other_manager_headers"]
    )
    assert other.status_code == 200
    assert other.json()["ventas"]["resumen"]["pedidos"] == 0
    assert client.get(
        "/api/v1/reports/dashboard", headers=context["customer_headers"]
    ).status_code == 403
    assert client.get(
        "/api/v1/reports/dashboard", headers=context["cashier_headers"]
    ).status_code == 403


def test_individual_report_endpoints_return_controlled_results(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    context = _prepare_report_data(client, db, sales_context)
    headers = context["admin_headers"]
    for path, key in (
        ("sales", "pedidos"),
        ("inventory", "registros"),
        ("reservations", "reservas"),
        ("returns", "devoluciones"),
    ):
        response = client.get(f"/api/v1/reports/{path}", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["resumen"][key] > 0
