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

## Preparación local

Requisitos:

- Python 3.12.
- PostgreSQL; la base puede crearse después de levantar y comprobar la API.

En PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

El archivo `.env` es local y está ignorado por Git. La conexión predeterminada
espera una base llamada `ropa` en PostgreSQL local:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ropa
```

Ajusta usuario, contraseña, puerto o nombre de base antes de ejecutar las
migraciones. Cambia también `JWT_SECRET` antes de cualquier despliegue.

## Ejecución y estado de servicios

```powershell
uvicorn app.main:app --reload
```

- `GET http://localhost:8000/health`: confirma que el proceso FastAPI está vivo
  sin requerir PostgreSQL.
- `GET http://localhost:8000/api/v1/health`: ejecuta `SELECT 1` y confirma la
  conexión real con PostgreSQL.
- `http://localhost:8000/docs`: documentación OpenAPI interactiva.

Si la base todavía no existe, el endpoint versionado responde `503` con el
código `database_unavailable`. Este comportamiento permite desarrollar la
interfaz sin confundir una API activa con una base ya preparada.

## Migraciones

Alembic obtiene la URL desde `.env`. La primera migración crea `usuarios`,
`roles`, `usuario_roles` y `perfiles_cliente`; la segunda crea `ciudades` y
`sucursales` y agrega la relación opcional del usuario con su sucursal; la
tercera crea `categorias` y `proveedores`; la cuarta crea tallas, colores,
temporadas, colecciones, productos, variantes e imágenes:

```powershell
alembic upgrade head
```

Los roles iniciales son `cliente`, `administrador`, `encargado` y `cajero`. No
se incluye ninguna contraseña predeterminada.

Después de migrar, crea la primera cuenta administrativa mediante entrada
interactiva para que la contraseña no quede en el historial del terminal:

```powershell
python -m app.scripts.create_admin --email admin@tienda.com --nombres Ada --apellidos Admin
```

## Autenticación y usuarios

Endpoints principales:

- `POST /api/v1/auth/register`: registro público con rol `cliente`.
- `POST /api/v1/auth/login`: emisión de JWT mediante correo y contraseña.
- `GET /api/v1/auth/me`: sesión actual autenticada.
- `/api/v1/users`: administración de cuentas, protegida por rol
  `administrador`.
- `/api/v1/roles`: administración de roles. Los cuatro roles iniciales no se
  pueden eliminar.

Las contraseñas se guardan con Argon2 y nunca forman parte de las respuestas.
El token de desarrollo expira según `ACCESS_TOKEN_EXPIRE_MINUTES`. El campo
nullable `sucursal_id` permite asociar empleados con una sucursal activa.

## Ciudades y sucursales

Los endpoints `/api/v1/cities` y `/api/v1/branches` ofrecen CRUD administrativo,
búsqueda y paginación. Una sucursal registra ciudad, dirección, teléfono
opcional, horario informativo y estado. No se permite eliminar una ciudad con
sucursales ni una sucursal con empleados asignados.

## Categorías y proveedores

Los endpoints administrativos `/api/v1/categories` y `/api/v1/suppliers`
ofrecen CRUD, búsqueda, paginación y activación/desactivación. El proveedor es
un registro genérico con NIT opcional, teléfono, correo y dirección; no posee
portal, credenciales ni integraciones externas. Los nombres de categorías y
proveedores son únicos, al igual que el NIT cuando se proporciona.

## Catálogo de prendas

`/api/v1/catalog` expone el catálogo público, detalle, tallas, colores,
temporadas, colecciones y categorías activas. La búsqueda permite filtrar por
texto, categoría, temporada, talla y color. `/api/v1/admin/catalog` contiene el
CRUD administrativo protegido de datos auxiliares, productos y variantes.

Cada producto conserva al menos una variante; el SKU y la combinación
producto–talla–color son únicos. Una variante puede heredar `precio_base` o
definir su propio precio. Las imágenes se almacenan como URLs y solo una se
marca como principal. La disponibilidad pública por sucursal se obtiene de
`/api/v1/catalog/products/{id}/availability` y no duplica existencias en el
catálogo.

## Inventario por sucursal

`/api/v1/inventory` permite consultar por ciudad, sucursal, producto, variante
y estado. Los roles `administrador` y `encargado` registran recepciones y
ajustes; el `cajero` tiene consulta. Los empleados no administradores quedan
limitados a su sucursal asignada.

Las operaciones de recepción, reserva, liberación, venta, devolución y ajuste
se ejecutan en el servicio de inventario con bloqueo de fila y generan un
`MovimientoInventario` dentro de la misma transacción. La migración
`20260902_0005` crea las restricciones e índices correspondientes.

## Reservas

`POST /api/v1/reservations` permite al cliente reservar una o varias variantes
de una única sucursal. La operación incrementa `stock_reservado` y crea los
movimientos de inventario dentro de la misma transacción. `GET
/api/v1/reservations/mine` expone el historial del cliente y `POST
/api/v1/reservations/{id}/cancel` libera las prendas incluso desde el estado
`PREPARADA`.

La bandeja `GET /api/v1/reservations/branch` está disponible para administrador
y encargado; el encargado queda limitado a su sucursal. Las transiciones
válidas son `PENDIENTE → CONFIRMADA → PREPARADA → COMPLETADA`, con cancelación
desde cualquiera de los tres estados activos. Completar la atención sin una
compra libera las prendas. Convertirla en pedido vende las cantidades elegidas,
libera las restantes y consume simultáneamente el stock físico y reservado.

La migración `20260902_0006` crea reservas y detalles. El vencimiento al final
del día elegido se ejecuta de forma portable, sin proveedor de nube específico:

```powershell
python -m app.scripts.expire_reservations --limit 100
```

## Carrito, pedidos y venta POS

`/api/v1/cart` mantiene un único carrito activo por cliente y permite agregar,
editar, retirar o vaciar líneas. Los precios mostrados allí son estimativos: al
confirmar, el backend vuelve a consultar prendas, precios y disponibilidad.

`POST /api/v1/orders/checkout` crea pedidos `WEB` o `MOBILE` desde el carrito y
`POST /api/v1/orders/from-reservation/{id}` convierte únicamente las cantidades
elegidas de una reserva. Ambos generan un `Pedido` en estado `CREADO`, conservan
el precio confirmado en sus detalles y registran los movimientos de inventario
en la misma transacción. Los clientes consultan `/orders/mine` y su detalle.

La venta presencial reutiliza la misma entidad con canal `POS` y estado
`COMPLETADO`. Administrador y cajero pueden buscar existencias por SKU mediante
`GET /api/v1/orders/pos/variants` y registrar `POST /api/v1/orders/pos`; el
cliente es opcional. `/orders/manage` ofrece historial y filtros operativos con
alcance de sucursal para encargado y cajero. La migración
`20260902_0007` crea carritos, pedidos y sus detalles.

## Pagos, devoluciones y reembolsos

`app/integrations/payment_gateway` define el contrato independiente de la
pasarela. La implementación actual es `TestPaymentGateway`: una simulación
determinista identificada como ambiente `PRUEBA` que no solicita ni almacena
tarjetas, cuentas o credenciales. `POST /api/v1/payments/orders/{pedido_id}`
inicia un pago usando exclusivamente el total persistido del pedido y `POST
/api/v1/payments/{pago_id}/confirm` permite simular aprobación o rechazo.

Un pago aprobado deja el pedido digital en `PAGADO`. Un rechazo simple lo pasa
a `CANCELADO` y repone el inventario descontado, dejando un movimiento trazable
referenciado al pago. Las ventas POS crean automáticamente un pago `CAJA`
aprobado dentro de la misma transacción del pedido.

`POST /api/v1/returns` registra devoluciones parciales contra detalles vendidos;
el acumulado de solicitudes no canceladas nunca puede superar la compra. El
cliente consulta `/returns/mine` y puede cancelar solicitudes aún no aprobadas.
Administrador y encargado gestionan `/returns/manage` con alcance por sucursal
y las transiciones `SOLICITADA → APROBADA → COMPLETADA` o `CANCELADA`.

Al completar se decide explícitamente si la prenda reingresa al inventario y si
se genera el reembolso. Stock, movimiento, devolución y reembolso se guardan en
la misma transacción. Los reembolsos usan precios históricos y referencias de
prueba; el pedido y pago pasan a `REEMBOLSADO` al reintegrarse el monto total.
La migración `20260902_0008` crea pagos, reembolsos, devoluciones y detalles.

## Pruebas

```powershell
python -m pytest -q
```

Las pruebas de API usan sustitución de dependencias y pueden ejecutarse sin una
base local. Alembic se valida adicionalmente contra PostgreSQL mediante
`alembic upgrade head` y `alembic check`.

## Docker

```powershell
docker build -t ropa-backend .
docker run --env-file .env -p 8000:8000 ropa-backend
```

Al ejecutar el contenedor contra PostgreSQL instalado en el equipo anfitrión,
ajusta el host de `DATABASE_URL` según Docker Desktop. La imagen no depende de
AWS, Azure ni Google Cloud.
