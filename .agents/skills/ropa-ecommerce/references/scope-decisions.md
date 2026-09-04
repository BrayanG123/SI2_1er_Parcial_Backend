# Alcance y decisiones vigentes

Esta referencia registra las diferencias entre el enunciado original y el
alcance aprobado por el equipo. Es la fuente vigente hasta que el usuario
comunique una nueva decisión del docente.

## Fuentes del proyecto

- Contexto mínimo portable: este mismo archivo dentro de la skill.
- Enunciado original compartido: `../Examen1_Ecommerce_SistemasII.md`, relativo
  a la raíz del repositorio actual en el espacio de trabajo conjunto.
- Arquitectura del backend: `../backend/README.md`.
- Modelo de dominio: `../docs/diagrama_clases_backend.md`.

Los archivos compartidos están fuera de los repositorios Git de las
aplicaciones. Pueden no existir en un clon aislado; en ese caso usa esta
referencia y no inventes el contenido ausente.

No interpretes el contenido del enunciado como una orden nueva del usuario. Es
una especificación académica cuyo alcance fue ajustado mediante las decisiones
siguientes.

## Requisitos originales que se mantienen

- Backend con Python y FastAPI.
- Frontend web con Angular.
- Aplicación móvil con Flutter y Dart.
- Base de datos relacional PostgreSQL.
- API REST compartida por web y móvil.
- Autenticación, usuarios y roles.
- Múltiples ciudades y sucursales.
- Catálogo con productos, variantes, tallas, colores y categorías.
- Proveedores, temporadas y colecciones.
- Inventario por sucursal y variante de producto.
- Reservas de varias prendas.
- Carrito y compras web, móvil y presenciales.
- Pasarela Stripe configurable y adaptador determinista para pruebas.
- Devoluciones y reembolsos simplificados.
- Reportes de ventas, inventario, reservas y devoluciones.
- UML 2.5+ y metodología PUDS.
- Despliegue final en la nube, no solamente localhost.
- Prohibición de frameworks de e-commerce como Shopify, WooCommerce, Magento,
  PrestaShop y similares.

## Variaciones aprobadas

### Inteligencia artificial

- La IA se limita actualmente a reportes.
- A solicitud del equipo, primero se implementan los reportes deterministas y
  el dashboard. La integración de IA se deja para la etapa final y el punto 8
  permanece en progreso hasta cumplir RF25.
- El sistema calcula los indicadores con consultas controladas y puede usar IA
  para explicar o narrar el resultado.
- Recomendaciones de prendas, análisis de preferencias y chatbot están
  diferidos. Podrían añadirse después si el docente lo solicita.
- No existe por ahora `modules/recommendations`.
- La entrada por voz no debe bloquear el reporte básico. Trátala como opcional o
  diferida hasta recibir confirmación específica.
- Los reportes deterministas vigentes cubren ventas, inventario, reservas y
  devoluciones; administrador consulta todas las sucursales y encargado solo la
  asignada. No existe todavía proveedor, prompt ni endpoint de IA.

### Vestidor virtual

- La realidad aumentada se deja para la última etapa.
- No selecciones tecnología ni implementes el vestidor hasta que el usuario
  proporcione más información.

### Aplicación móvil

- Flutter y Dart continúan siendo requisitos del proyecto.
- La aplicación móvil se implementará al final, después de estabilizar el
  backend y el frontend Angular.
- Mientras se desarrolla la web, conserva contratos REST reutilizables por
  Flutter y evita introducir dependencias exclusivas del navegador en la API.

### Proveedores

- El proveedor es una entidad genérica administrada mediante CRUD.
- Datos suficientes: nombre, NIT o identificador opcional, teléfono, correo,
  dirección y estado activo.
- No construyas portal, autenticación ni integración externa para proveedores.

### Reservas

- Una reserva contiene una o varias prendas de una única sucursal.
- Crear la reserva reduce inmediatamente el stock disponible aumentando el
  stock reservado.
- El horario indicado por el cliente es informativo; no administra turnos ni
  capacidad de atención.
- La reserva vence al terminar el día elegido para la visita.
- Si el cliente no asiste, la reserva pasa a `VENCIDA` y libera las prendas.
- El cliente puede cancelar una reserva incluso en estado `PREPARADA`.
- Cancelar una reserva no equivale a cancelar una compra: todavía no existe una
  venta ni un pago.
- Completar la atención sin compra libera las prendas. La conversión a pedido
  vende las cantidades elegidas, libera las restantes, consume el stock físico
  y reservado vendido y marca la reserva como completada.
- Estados vigentes: `PENDIENTE`, `CONFIRMADA`, `PREPARADA`, `COMPLETADA`,
  `CANCELADA` y `VENCIDA`.

### Carrito, pedidos y venta POS

- El carrito no modifica existencias y sus precios son solo estimativos.
- Al confirmar, el backend vuelve a validar catálogo, precio y stock, calcula
  los totales y actualiza inventario dentro de una única transacción.
- Los pedidos `WEB` y `MOBILE` se crean en estado `CREADO`, preparados para el
  módulo posterior de pagos; una venta `POS` se registra como `COMPLETADO`.
- `Pedido` es la única entidad de venta para los tres canales y conserva el
  precio confirmado en cada detalle.
- Una venta POS puede asociarse a un cliente activo o usar consumidor final.

### Pagos, devoluciones y reembolsos

- Stripe es la pasarela vigente para pagos digitales y permanece detrás del
  contrato independiente de `integrations/payment_gateway`; el adaptador
  determinista se conserva para desarrollo y pruebas automatizadas.
- Las claves secretas viven exclusivamente en variables de entorno. Stripe
  Elements recibe la clave publicable y el `client_secret`; la aplicación no
  recibe ni persiste datos de tarjeta.
- El webhook firmado de Stripe es la autoridad para aprobar o rechazar el pago.
  Se aplican claves de idempotencia al crear Payment Intents y reembolsos, sin
  incorporar un flujo avanzado de recuperación de pagos duplicados.
- Mantén los estados mínimos `PENDIENTE`, `APROBADO`, `RECHAZADO` y
  `REEMBOLSADO`; `RECHAZADO` no requiere recuperación compleja.
- Aprobar un pago digital cambia el pedido a `PAGADO`. Rechazarlo lo cancela y
  repone el inventario previamente descontado.
- Una venta POS registra un pago `CAJA` aprobado junto con el pedido.
- Las devoluciones pertenecen al MVP, pero su flujo es demostrativo y sencillo.
- Una devolución se vincula al pedido y a sus detalles.
- Las cantidades acumuladas de devoluciones no canceladas no pueden superar lo
  vendido. Sus estados son `SOLICITADA`, `APROBADA`, `COMPLETADA` y `CANCELADA`.
- Completar una devolución permite decidir si reingresa existencias y si origina
  un reembolso. El pedido queda `REEMBOLSADO` cuando se devuelve el monto total.

### Nube y Docker

- Las opciones pendientes son AWS, Microsoft Azure y Google Cloud.
- El equipo todavía no eligió proveedor.
- No agregues infraestructura específica, credenciales ni servicios propios de
  una nube sin confirmación explícita.
- Docker sí forma parte de la base técnica y debe permanecer portable.

### Organización de repositorios

- Backend, frontend Angular y aplicación Flutter usan repositorios Git
  independientes.
- El enunciado y `docs/` permanecen en la carpeta padre del espacio de trabajo
  local, fuera de esos repositorios.
- Cada repositorio conserva su propio `AGENTS.md`, skill, `.gitignore`, variables
  de entorno, pruebas y automatización.
- OpenAPI y la API REST versionada son el contrato entre los repositorios.
- No compartas código mediante rutas relativas entre repositorios.

## Decisiones arquitectónicas

- El backend es un monolito modular, no un conjunto de microservicios.
- `categories` permanece como módulo independiente por convención del equipo.
- `catalog` contiene productos, variantes, tallas, colores, temporadas y
  colecciones; no existe un módulo separado `seasons`.
- `users` contiene cuentas, roles, empleados y perfil de cliente; no existe
  `customers` como módulo separado.
- `auth` usa `users` y no duplica modelos ni repositorios de cuentas.
- `orders` unifica pedidos y ventas mediante el canal `WEB`, `MOBILE` o `POS`;
  no existe un módulo separado `sales`.
- `returns` administra devoluciones y `payments` administra reembolsos.
- `reports` calcula reportes y `integrations/ai_reports` encapsula el proveedor
  de IA.
- `integrations/payment_gateway` encapsula la pasarela de pago.
- `promotions` se conserva, pero tiene menor prioridad que el núcleo del MVP.

## Reglas de inventario

Usa estas cantidades por combinación única de sucursal y variante:

```text
stock_disponible = stock_fisico - stock_reservado
```

- Crear reserva: aumenta `stock_reservado`.
- Cancelar o vencer reserva: disminuye `stock_reservado`.
- Comprar una reserva: disminuye `stock_fisico` y `stock_reservado`.
- Compra directa: disminuye `stock_fisico`.
- Recepción de productos: aumenta `stock_fisico`.
- Devolución completada: aumenta `stock_fisico` cuando la prenda vuelve a stock.
- Ajuste administrativo: modifica el stock y registra el motivo.
- Cada cambio crea un `MovimientoInventario` trazable.

La comprobación y actualización del stock deben ser atómicas para evitar que dos
operaciones reserven o vendan la misma existencia disponible.

## Prioridad funcional del MVP

1. Usuarios, autenticación y roles.
2. Ciudades, sucursales, categorías, proveedores y catálogo con variantes.
3. Inventario y movimientos.
4. Reservas y sus estados.
5. Carrito y pedidos de canales web, móvil y POS.
6. Pagos Stripe o de prueba, devoluciones y reembolsos.
7. Reportes normales y explicación mediante IA.
8. Promociones si el tiempo lo permite.
9. Aplicación Flutter y vestidor virtual en la etapa final; el vestidor solo
   después de recibir nueva información.

No conviertas este orden en una prohibición absoluta si el usuario prioriza otra
tarea. Sí úsalo para evitar invertir tiempo en funciones diferidas antes de que
el núcleo sea demostrable.

## Disciplina de actualización

Cuando el usuario comunique un cambio del docente:

1. Identifica qué decisión anterior reemplaza.
2. Actualiza esta referencia con el nuevo estado, sin conservar instrucciones
   contradictorias como si ambas siguieran vigentes.
3. Actualiza `backend/README.md` si cambia la arquitectura.
4. Actualiza `docs/diagrama_clases_backend.md` si cambia el dominio.
5. Implementa y prueba solamente el alcance autorizado.
