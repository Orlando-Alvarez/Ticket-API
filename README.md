# ticket-api

Backend API de tickets e incidentes orientada a portafolio para roles junior de backend, cloud o platform. Esta primera fase entrega una base limpia de FastAPI con versionado de rutas, healthcheck y manejo básico de errores.

## Requisitos

- Python 3.11+
- `pip`

## Instalacion local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Ejecutar la API

```bash
uvicorn app.main:app --reload
```

La API quedara disponible en:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`
- `http://127.0.0.1:8000/api/v1/health`

## Endpoint disponible

### `GET /api/v1/health`

Respuesta esperada:

```json
{
  "status": "ok",
  "service": "ticket-api",
  "version": "0.1.0"
}
```

## Estructura actual

```text
app/
  api/
    routes/
  core/
  schemas/
  main.py
```

## Manejo de errores incluido

- `404` en formato JSON consistente
- `422` para errores de validacion
- `500` con mensaje generico sin exponer detalles internos

## Siguiente fase

La siguiente fase agregara persistencia con PostgreSQL y modelos de dominio, sin romper la estructura creada aqui.
