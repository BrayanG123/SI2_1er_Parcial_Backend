# Seeder de datos demostrativos

Este seeder prepara una base de desarrollo para demostrar principalmente el
catálogo, el inventario, las ventas y el dashboard. No descarga archivos, no
realiza cobros y no se conecta con Stripe.

## Datos generados por defecto

La configuración predeterminada inserta **3.565 filas nuevas**:

| Entidad                 | Cantidad |
|---                      |---: |
| Ciudades                | 10  |
| Sucursales              | 15  |
| Clientes                | 70  |
| Personal demostrativo   | 5   |
| Categorías              | 10  |
| Proveedores             | 10  |
| Tallas                  | 6   |
| Colores                 | 12  |
| Temporadas              | 4   |
| Colecciones             | 8   |
| Productos               | 160 |
| Variantes               | 480 |
| Imágenes de producto    | 160 |
| Registros de inventario | 480 |
| Pedidos                 | 240 |
| Detalles de pedido      | 399 |
| Pagos                   | 240 |
| Reservas                | 25  |
| Devoluciones            | 24  |
| Carritos activos        | 20  |
| Movimientos de inventario | 945 |
| Otros detalles, perfiles y relaciones | 242 |

Las ventas se distribuyen durante los 365 días anteriores a la fecha base y
usan los canales `WEB`, `MOBILE` y `POS`. También existen pedidos pendientes y
cancelados, reservas con distintos estados, devoluciones y seis reembolsos.

Los pagos digitales históricos usan `PASARELA_PRUEBA` y los presenciales usan
`CAJA`. El seeder nunca crea Payment Intents ni referencias Stripe falsas.

## Requisitos

1. Python y las dependencias del backend instaladas.
2. Una base PostgreSQL destinada a desarrollo o demostración.
3. Las migraciones aplicadas hasta `head`.
4. Las tablas de negocio vacías. Pueden existir los cuatro roles iniciales y
   una cuenta administrativa creada manualmente.

No ejecutes el seeder sobre una base de producción. Si encuentra ciudades,
catálogo, inventario, pedidos u otros datos de negocio, termina sin modificar
nada. No incluye una opción automática para borrar información existente.

## Preparación

Desde PowerShell, entra al repositorio backend y activa el entorno virtual:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
alembic upgrade head
```

Puedes revisar la configuración sin conectarte a PostgreSQL ni insertar filas:

```powershell
python -m app.scripts.seed_demo --dry-run
```

## Ejecución recomendada

Ejecuta:

```powershell
python -m app.scripts.seed_demo
```

El comando solicitará dos veces una contraseña. Esa contraseña se guarda como
hash Argon2 y se asigna únicamente a las cuentas demostrativas. No se muestra
en pantalla ni se guarda en el repositorio.

Al finalizar debe aparecer un resumen parecido a:

```text
Seeder completado: 3565 filas insertadas.
- ciudades: 10
- sucursales: 15
- clientes: 70
- productos: 160
- variantes: 480
- pedidos: 240
```

Toda la carga ocurre en una única transacción. Si se incumple una restricción,
PostgreSQL revierte el conjunto completo.

## Cuentas para probar la aplicación

Todas usan la contraseña ingresada durante la ejecución:

| Rol | Correo |
|---|---|
| Administrador | `admin@demo.example.com` |
| Encargado | `encargado1@demo.example.com` |
| Cajero | `cajero1@demo.example.com` |
| Cliente | `cliente001@demo.example.com` |

También se crean `encargado2@demo.example.com`,
`cajero2@demo.example.com` y los clientes numerados desde
`cliente001@demo.example.com` hasta `cliente070@demo.example.com`.

## Reparar una carga creada con la versión anterior

Una versión anterior usaba correos terminados en `.test`. Ese dominio está
reservado y Pydantic lo rechaza al validar las respuestas del catálogo. Si la
base ya fue poblada con esa versión, no es necesario borrar ni repetir el
seeder. Ejecuta una sola vez:

```powershell
python -m app.scripts.seed_demo --reparar-emails
```

La reparación actualiza exclusivamente las cuentas y proveedores reconocibles
del seeder antiguo dentro de una transacción. No solicita contraseña, no cambia
los hashes existentes y puede repetirse de forma segura: una segunda ejecución
indica cero correos actualizados.

## Ejecución no interactiva

Para automatización local se puede proporcionar temporalmente la contraseña
mediante una variable del proceso:

```powershell
$env:DEMO_SEED_PASSWORD = "UnaClaveSegura123"
python -m app.scripts.seed_demo
Remove-Item Env:DEMO_SEED_PASSWORD
```

No agregues `DEMO_SEED_PASSWORD` al archivo `.env` compartido ni la confirmes en
Git.

## Personalización

El volumen principal se puede modificar sin editar código:

```powershell
python -m app.scripts.seed_demo `
  --clientes 90 `
  --productos 200 `
  --pedidos 320 `
  --seed 20260906 `
  --fecha-base 2026-09-06
```

- `--seed` controla los identificadores reproducibles del conjunto.
- `--fecha-base` define el último día del historial de ventas.
- Cada producto genera tres variantes y una imagen principal.
- La configuración geográfica se mantiene en 10 ciudades y 15 sucursales.

Usa `python -m app.scripts.seed_demo --help` para consultar todas las opciones.

## Volver a ejecutar

El seeder no es acumulativo. Una segunda ejecución sobre la misma base se
rechaza para evitar duplicar ventas o alterar inventario. Para repetir la carga,
utiliza otra base de desarrollo vacía, aplica nuevamente las migraciones y
ejecuta el comando.

Las imágenes apuntan a `placehold.co`; la carga de la base no necesita Internet,
pero el navegador sí lo necesitará para mostrar esos placeholders.
