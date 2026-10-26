# CamisetaLibre Backend

API Python 3.12+ con FastAPI, PostgreSQL, SQLAlchemy y migraciones Alembic.
El frontend está en `../camisetalibre` y consume `/api` mediante el proxy Vite.

## Ejecutar

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m app --reload
```

API: http://127.0.0.1:3001. Documentación: http://127.0.0.1:3001/docs.
`GET /api/health` comprueba también la conexión PostgreSQL.
La configuración local y las credenciales están en `.env`, excluido del repositorio.
No es necesario volver a crear la base en cada arranque.

## Inicializar en otro entorno

Crear una base PostgreSQL vacía, un usuario propio y configurar `DATABASE_URL` en
`.env` a partir de `.env.example`. Las variables del entorno tienen prioridad.
Para crear una base local con el usuario PostgreSQL del sistema:

```bash
python scripts/create_local_database.py
```

El script crea solo `camisetalibre` y `camisetalibre_app`, genera una contraseña
aleatoria y escribe `.env` con permisos privados. Si ya existen `.env`, la base o
el rol, se detiene sin sobrescribirlos. Se puede indicar `POSTGRES_ADMIN_URL` para
una conexión administrativa diferente. Las credenciales de aplicación no tienen
permisos para crear bases ni roles.

Después de configurar la conexión:

```bash
python -m alembic upgrade head
python -m app.manage seed
python -m app.manage import-json
```

`seed` carga productos, opciones de tela y talles faltantes. No sobrescribe precios
existentes. `import-json` respalda e importa `data/store.json` en una transacción,
conserva identificadores y hashes scrypt, y puede repetirse sin duplicar registros.
Si encuentra un conflicto entre cuentas, cancela la importación. El servidor ya
no lee ni escribe el JSON; `DATA_FILE` se utiliza únicamente para la importación.
Mantener el mismo `AUTH_SECRET` conserva las sesiones anteriores. Antes de exponer
la API fuera del entorno local, reemplazar la clave de desarrollo por una privada;
ese cambio invalida las sesiones anteriores.

## Datos

| Tabla | Contenido |
| --- | --- |
| `customers` | Clientes, email único normalizado, teléfono y hash de contraseña |
| `customer_addresses` | Direcciones y destinatarios asociados al cliente |
| `products` | Camiseta, chomba, musculosa y short, valor base y cantidad mínima |
| `fabric_tiers` | Precio 1 / Eco, Precio 2 / Pro y Precio 3 / Premium |
| `sizes` | XS, S, M, L, XL, XXL y 3XL |
| `projects` | Diseños JSONB del cliente, opcionalmente vinculados a un producto |
| `orders` | Compras, cliente, estado, total, moneda y dirección histórica |
| `order_items` | Producto, tela, talle, cantidad, precio y diseño al comprar |
| `payments` | Estructura para registros de un futuro proveedor de pagos |

Las relaciones usan claves foráneas. Los importes se calculan con `Decimal` y se
almacenan con `NUMERIC`; los errores HTTP mantienen `{ "error": "mensaje" }`.
Fechas almacenadas con zona horaria y serializadas en UTC.

Precios iniciales por unidad en ARS: camiseta $28.000, chomba $31.000,
musculosa $20.000 y short $18.000. Eco conserva el base; Pro suma 20% y Premium
30%. El mínimo de ocho prendas se valida **por producto**, sumando sus talles.
Cuatro camisetas y cuatro shorts no cumplen el mínimo; cuatro camisetas M y
cuatro camisetas L sí. El servidor calcula los precios de las compras y rechaza
precios, totales o estados enviados por el cliente.

Los pedidos guardan copias de precios, nombres, dirección y diseño para que
cambios posteriores no modifiquen su historial. Crear una compra la deja en
`pending`: no realiza cobros ni crea pagos ficticios. No hay proveedor de pagos
integrado ni interfaz de checkout en esta etapa.

## Rutas

Registro y login devuelven `{ "user": {...}, "token": "..." }`. Las rutas de
cliente usan `Authorization: Bearer <token>`. Cada cliente accede solo a sus datos.

| Método | Ruta | Función |
| --- | --- | --- |
| POST | `/api/auth/register` | Registro: `name`, `email`, `password` |
| POST | `/api/auth/login` | Ingreso: `email`, `password` |
| GET | `/api/auth/me` | Sesión actual |
| GET/PATCH | `/api/customers/me` | Perfil y teléfono |
| GET/POST | `/api/customers/me/addresses` | Direcciones propias |
| GET | `/api/catalog` | Productos activos, precios base, telas y talles |
| POST | `/api/quotes` | Presupuesto público calculado con valores de PostgreSQL |
| GET/POST | `/api/projects` | Listar y crear diseños propios |
| PUT | `/api/projects/{id}` | Actualizar un diseño propio |
| GET/POST | `/api/orders` | Listar y crear compras propias |
| GET | `/api/orders/{id}` | Detalle de compra propia |
| POST | `/api/orders/{id}/cancel` | Cancelar una compra propia pendiente |

Ejemplo para presupuestar o crear una compra (POST `/api/quotes` o `/api/orders`):

```json
{
  "items": [
    { "productId": "camiseta", "fabricId": "pro", "sizeId": "M", "quantity": 8 }
  ]
}
```

Una compra también acepta `addressId`, `notes` y `projectId` por ítem. Los importes
de estas respuestas son cadenas decimales (por ejemplo, `"33600.00"`). La lista de
compras admite `limit` (1–100) y `offset`.

## Pruebas y migraciones

```bash
python -m unittest discover -s tests -v
python -m alembic check
```

Las pruebas usan PostgreSQL real y crean un esquema temporal único por prueba,
que eliminan al terminar. No vacían ni modifican las tablas de clientes de la
aplicación. Para usar otra instancia, configurar `TEST_DATABASE_URL`.

Al cambiar modelos, generar y revisar una migración antes de aplicarla:

```bash
python -m alembic revision --autogenerate -m "descripcion"
python -m alembic upgrade head
```

El esquema se administra con migraciones; el arranque del servidor no crea ni
borra tablas automáticamente. El presupuesto del frontend obtiene los precios
desde `/api/catalog` sin duplicar los valores iniciales en el código React.

## Guardado del frontend por cliente

El frontend activo está en `/Users/emilianofaro/Downloads/camisetalibre-frontend`.
El editor sincroniza automáticamente el conjunto con la cuenta autenticada y
permite guardarlo inmediatamente con **Guardar en mi cuenta**. Al volver a entrar
recupera el documento completo y la vista activa desde PostgreSQL. IndexedDB
queda como copia local opcional y como fuente de importación de borradores
anteriores: solo se importa el borrador de ese cliente si su cuenta todavía no
tiene uno remoto. Los visitantes pueden calcular presupuestos sin autenticarse;
las selecciones se guardan en PostgreSQL únicamente para clientes autenticados.

Modelos adicionales:

| Tabla | Contenido |
| --- | --- |
| `editor_workspaces` | Un espacio de trabajo por cliente, proyecto asociado, vista y revisión |
| `customer_preferences` | Producto, tela y cantidad del último presupuesto del cliente |

El documento completo se almacena en `projects.design` como JSONB validado:
modelo de prenda, patrón, colores, camiseta y short, frente y espalda, orden de
capas, textos, posiciones, medidas, tipografías, logos, sponsors, diseños propios,
configuración de patrones y personalizaciones de cada diseño del catálogo. Los
recursos raster se conservan dentro del documento como imágenes base64, hasta
32 MB por conjunto. No se guardan imágenes de la interfaz ni el historial de
Deshacer/Rehacer; el resultado editable sí se conserva.

| Método | Ruta | Función |
| --- | --- | --- |
| GET/PUT | `/api/customers/me/workspace` | Recuperar y guardar el conjunto y la vista activa |
| GET/PUT | `/api/customers/me/preferences` | Recuperar y guardar las selecciones de presupuesto |

En cada PUT se envía `expectedRevision` (0 para el primer guardado). La revisión
se incrementa en cada escritura. Si otra pestaña cambió los datos, la API responde
409 y la interfaz permite cargar la versión de la cuenta; el editor conserva la
opción de descargar el JSON antes de reemplazar cambios locales. Los tokens se
mantienen asociados a la instancia de cada cuenta para que un guardado pendiente
al cerrar sesión no termine enviado con las credenciales de otro cliente.

El cliente no puede elegir `customerId`, `ownerId` ni el proyecto remoto en estos
endpoints: los determina el servidor a partir de la autenticación. Los errores
de red no se muestran como guardados exitosos. El navegador avisa al cerrar una
página con cambios sin confirmar.
