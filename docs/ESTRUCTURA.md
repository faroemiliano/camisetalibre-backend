# Estructura del backend

Este repositorio contiene la API FastAPI y el esquema de PostgreSQL. El frontend
se mantiene en su propio repositorio y ventana de VS Code. Cada repositorio
conserva su Git, configuración y dependencias.

```text
app/
  main.py         Creación de FastAPI y registro de rutas
  __main__.py     Arranque: python -m app --reload
  dependencies.py Sesión SQLAlchemy y cliente autenticado de cada solicitud
  manage.py       Comandos de carga inicial e importación histórica
  core/           Configuración y seguridad (contraseñas y tokens)
  db/             Conexión, modelos SQLAlchemy y catálogo inicial
  schemas/        Validación Pydantic de API y documentos del editor
  routes/         Endpoints HTTP por funcionalidad
  services/       Cálculos de precios y serialización de respuestas
migrations/       Historial versionado de Alembic
scripts/          Herramientas administrativas de instalación
tests/           Pruebas de API y workspace (esquemas PostgreSQL temporales)
docs/             Arquitectura y tareas pendientes
data/            Importaciones y respaldos locales, excluidos de Git
```

`app/db/session.py` administra la conexión; `app/db/models.py` define las tablas;
`app/db/seed.py` carga los registros iniciales faltantes. La base real sigue en
PostgreSQL: no es una carpeta que deba trasladarse. `migrations/` y `alembic.ini`
conservan su ubicación e historial. No hace falta crear ni migrar tablas por
esta reorganización de archivos.

`app/core/config.py` carga el `.env` de la raíz del backend independientemente de
la profundidad del módulo. Se conservan el mismo `AUTH_SECRET`, la conexión y
los datos. Las credenciales no deben copiarse al frontend.

Las rutas coordinan HTTP y autenticación. Los cálculos compartidos pertenecen a
`services/`, las validaciones a `schemas/` y el acceso a tablas usa la sesión
SQLAlchemy de la solicitud. Para nuevas funcionalidades, ampliar estos módulos
antes de introducir nuevas capas o dependencias.

Desde la raíz de este repositorio:

```bash
source .venv/bin/activate
python -m app --reload
python -m unittest discover -s tests -v
python -m alembic check
```

El arranque sigue en el puerto 3001 y conserva todos los endpoints. Las pruebas
usan esquemas temporales propios y los eliminan al terminar. Las revisiones de
Alembic se generan solo cuando cambia el esquema de datos, no al mover módulos.

No hace falta reinstalar dependencias ni recrear `.venv` por esta reorganización.
Ver [tareas pendientes](./TODO.md) para la futura gestión de imágenes privadas;
esa migración funcional no forma parte de esta organización de carpetas.
