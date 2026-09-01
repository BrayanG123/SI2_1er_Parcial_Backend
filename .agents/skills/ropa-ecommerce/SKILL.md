---
name: ropa-ecommerce
description: "Trabajar en uno de los repositorios del e-commerce de ropa: analizar, diseñar, documentar o implementar FastAPI, Angular, Flutter, PostgreSQL, inventario, reservas, pedidos, pagos, devoluciones y reportes con IA. No usar para otros proyectos."
---

# E-commerce de ropa

Continúa el MVP académico respetando las decisiones vigentes y el límite del
repositorio actual.

## Recuperar el contexto

Antes de modificar requisitos, modelo de datos, arquitectura, reglas de negocio
o código funcional, lee por completo
[references/scope-decisions.md](references/scope-decisions.md).

Lee también el `README.md` de la raíz del repositorio actual, ubicado en
`../../../README.md` desde esta skill.

Cuando los tres proyectos estén abiertos como carpetas hermanas dentro del
espacio de trabajo original, puedes consultar:

- Enunciado: `../../../../Examen1_Ecommerce_SistemasII.md`.
- Plan de módulos: `../../../../docs/plan_modulos_implementacion.md`.
- Diagrama de clases: `../../../../docs/diagrama_clases_backend.md`.
- Arquitectura backend: `../../../../backend/README.md`.
- Información frontend: `../../../../frontend/README.md`.

Esas rutas externas son complementarias y pueden no existir en un clon aislado.
Si faltan, continúa con la referencia local y pide el documento únicamente
cuando su contenido exacto sea necesario.

## Respetar los repositorios separados

- Backend, frontend y móvil tienen historiales Git independientes.
- Modifica solamente el repositorio actual, salvo que el usuario pida
  explícitamente un cambio coordinado en más de uno.
- Usa la API REST versionada y OpenAPI como contrato entre aplicaciones; no
  compartas código mediante rutas relativas entre repositorios.
- No supongas que los documentos externos estarán presentes en CI o después de
  clonar un único repositorio.

## Resolver contradicciones

Aplica esta precedencia:

1. Instrucción explícita más reciente del usuario.
2. Decisiones aprobadas en `references/scope-decisions.md`.
3. Enunciado original para requisitos que no fueron modificados.
4. Documentación arquitectónica y diagrama de clases.
5. Código actual como evidencia de lo que ya está implementado.

Si el docente cambia el alcance, no mezcles instrucciones incompatibles.
Actualiza la referencia local y los documentos afectados que estén dentro del
alcance autorizado.

## Mantener la arquitectura

- Usa un monolito modular en FastAPI; no introduzcas microservicios sin una
  decisión nueva del equipo.
- En backend separa `router`, `schemas`, `service`, `repository` y `models`.
- En Angular organiza componentes standalone por funcionalidades bajo
  `features`, con `core` y `shared` para elementos transversales.
- Mantén PostgreSQL, Angular y Flutter/Dart como tecnologías obligatorias.
- No uses Shopify, WooCommerce, Magento, PrestaShop ni frameworks similares.
- Mantén pagos e IA detrás de adaptadores.
- No configures AWS, Azure ni Google Cloud hasta que el usuario confirme uno.
- No reintroduzcas funcionalidades diferidas sin una nueva indicación.

## Proteger las reglas del dominio

- Trata `inventory` como única autoridad para modificar existencias.
- Ejecuta la operación de negocio y su movimiento de inventario en una misma
  transacción.
- Impide reservar o vender más que el stock disponible.
- Guarda contraseñas únicamente como hash y aplica autorización por roles.
- Calcula reportes con consultas controladas; la IA solo recibe datos agregados
  y validados, nunca SQL libre.

## Terminar los cambios

- Verifica compilación, pruebas, endpoints o migraciones según el cambio.
- Mantén estable el contrato API consumido por Angular y, después, Flutter.
- Actualiza UML cuando cambien entidades, atributos o cardinalidades.
- Distingue qué quedó implementado, simulado o diferido.

