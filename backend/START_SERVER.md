# How to Start Django Server

## Quick Start

```bash
cd backend
./venv/bin/python manage.py runserver
```

The server will start on `http://127.0.0.1:8000` or `http://localhost:8000`

## Verify Server is Running

Open in browser or use curl:
- `http://localhost:8000/api/clients/` - Should return JSON data
- `http://localhost:8000/admin/` - Django admin interface

## Troubleshooting

If you get "port already in use":
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Then start server again
./venv/bin/python manage.py runserver
```

## Running in Background

To run the server in the background:
```bash
cd backend
./venv/bin/python manage.py runserver > server.log 2>&1 &
```

To stop it:
```bash
lsof -ti:8000 | xargs kill
```
