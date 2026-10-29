# Próxima sesión: migrar imágenes al backend

Primera tarea acordada: reemplazar las imágenes base64 guardadas dentro de
`projects.design` por archivos gestionados por el backend, respetando su usuario.

Estado actual:

- FastAPI y PostgreSQL conectados, con migraciones Alembic.
- Diseños completos guardados por cliente, incluidos logos, sponsors y diseños propios.
- Borradores y presupuestos sincronizados; control de versiones entre pestañas.
- Las imágenes de clientes siguen como data URI base64 en JSONB.
- 25 pruebas del backend y 34 del frontend aprobadas; flujos de guardado,
  recuperación y separación entre cuentas verificados en Chrome.

Orden previsto:

1. Crear el modelo y la migración de recursos multimedia, asociados al cliente.
2. Agregar subida, validación y acceso autenticado a imágenes en FastAPI.
3. Guardar archivos en almacenamiento privado y referencias en PostgreSQL.
4. Migrar las imágenes existentes con respaldo y un proceso repetible, sin perder
   los diseños ni alterar sus propietarios.
5. Actualizar el editor para utilizar referencias de recursos, conservando la
   edición y la vista previa en el navegador.
6. Comprobar compatibilidad con importaciones/exportaciones y copias históricas
   de las compras, permisos entre clientes y eliminación de archivos sin uso.

El frontend activo está en `/Users/emilianofaro/Downloads/camisetalibre-frontend`.
Su código se mantiene separado de este repositorio de backend.
