# Arquitectura del backend

El backend se organiza como un **monolito modular** con FastAPI. Todos los
módulos se ejecutan en una sola aplicación y comparten PostgreSQL, pero cada
uno conserva una responsabilidad de negocio definida.

## Estructura

```text
backend/
├── app/
│   ├── main.py
│   ├── core/                 # Configuración, seguridad y errores comunes
│   ├── db/                   # Sesiones, base ORM y conexión a PostgreSQL
│   ├── modules/
│   │   ├── auth/             # Login, tokens y autorización
│   │   ├── users/            # Usuarios, roles y perfil del cliente
│   │   ├── catalog/          # Productos, variantes, temporadas y colecciones
│   │   ├── categories/       # Categorías como módulo independiente
│   │   ├── branches/         # Ciudades y sucursales
│   │   ├── suppliers/        # Datos básicos de proveedores
│   │   ├── inventory/        # Existencias y movimientos
│   │   ├── reservations/     # Reservas y preparación de prendas
│   │   ├── cart/             # Carritos y sus detalles
│   │   ├── orders/           # Compras web, móvil y POS
│   │   ├── payments/         # Pagos y reembolsos
│   │   ├── returns/          # Devoluciones
│   │   ├── reports/          # Reportes normales y narrados con IA
│   │   └── promotions/       # Promociones, posterior al núcleo del MVP
│   ├── integrations/
│   │   ├── payment_gateway/  # Adaptador de la pasarela de pruebas
│   │   └── ai_reports/       # Adaptador del servicio de IA
│   └── shared/               # Utilidades realmente compartidas
├── alembic/                  # Migraciones de base de datos
├── tests/                    # Pruebas unitarias y de integración
├── Dockerfile
├── requirements.txt
└── requirements-dev.txt
```

## Capas de un módulo

Cada módulo puede incorporar estos archivos cuando se implemente:

- `router.py`: endpoints HTTP y dependencias de FastAPI.
- `schemas.py`: solicitudes y respuestas de Pydantic.
- `service.py`: reglas de negocio y control de transacciones.
- `repository.py`: consultas y persistencia en PostgreSQL.
- `models.py`: modelos ORM del módulo.

`auth` no contiene modelos ni repositorios de usuario. Usa el módulo `users`
para evitar duplicar cuentas y roles.

## Decisiones de alcance

- `categories` permanece como módulo independiente.
- Temporadas y colecciones forman parte de `catalog`.
- `orders` representa ventas web, móvil y POS mediante el campo `channel`.
- El perfil de cliente pertenece a `users`; no existe otro módulo `customers`.
- Las devoluciones se gestionan en `returns` y los reembolsos en `payments`.
- La IA solamente narra o explica reportes calculados por el sistema.
- El recomendador queda fuera del código actual y puede añadirse luego como
  `modules/recommendations` sin modificar los módulos existentes.
- El vestidor virtual queda fuera de esta etapa.
- Docker es independiente del proveedor de nube que el grupo elija después.

## Regla central de inventario

El módulo `inventory` es el único responsable de modificar existencias. Los
servicios de reservas, pedidos y devoluciones solicitan sus operaciones a este
módulo en la misma transacción de base de datos.

```text
stock_disponible = stock_fisico - stock_reservado
```

- Crear una reserva aumenta `stock_reservado`.
- Cancelar o vencer una reserva disminuye `stock_reservado`.
- Comprar prendas reservadas disminuye `stock_fisico` y `stock_reservado`.
- Una compra directa disminuye `stock_fisico`.
- Una devolución completada aumenta `stock_fisico`.
- Toda modificación genera un movimiento de inventario.
