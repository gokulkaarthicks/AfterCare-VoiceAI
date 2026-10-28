"""DB service: the single writer for AfterCare's SQLite database.

Layout:
  repositories/  SQLAlchemy reads/writes, one module per domain
  seed/          demo fixtures for local runs
  routers/       FastAPI endpoint handlers
  schemas.py     request/response models

The FastAPI app and its RabbitMQ event consumers live in `app.api.db` and
`app.events`.
"""

SERVICE_NAME = "db_service"
SERVICE_PORT = 8003
