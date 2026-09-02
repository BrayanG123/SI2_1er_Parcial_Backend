# Migraciones

La configuración de Alembic obtiene `DATABASE_URL` desde `.env`. La primera
migración crea usuarios, roles, perfiles de cliente y sus asignaciones:

```bash
alembic upgrade head
```

La migración también inserta los roles `cliente`, `administrador`, `encargado`
y `cajero`. No crea una cuenta administrativa ni guarda contraseñas iniciales.
