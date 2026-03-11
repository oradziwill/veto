# Docker – uruchomienie backendu i frontendu

## Wymagania

- Docker i Docker Compose (v2)

## Uruchomienie

```bash
# Z katalogu głównego projektu (veto/)
docker compose up --build
```

- **Backend (Django):** http://localhost:8000  
- **Frontend (Vite):** http://localhost:5174 (proxy `/api` → backend)

## Pierwsze uruchomienie – migracje i dane testowe

Po pierwszym `docker compose up` w innym terminalu:

```bash
# Migracje
docker compose exec backend python manage.py migrate

# Opcjonalnie: dane testowe (klinika, użytkownicy, sale, pacjenci)
docker compose exec backend python manage.py seed_data
```

Logowanie: użytkownik `drsmith`, hasło `password123` (jeśli uruchomiono `seed_data`).

## Przydatne komendy

```bash
# Zatrzymanie
docker compose down

# Logi
docker compose logs -f backend
docker compose logs -f frontend

# Shell w kontenerze backendu
docker compose exec backend bash

# Migracje po zmianach w modelach
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
```

## Zmienne środowiskowe

- **Backend:** `ALLOWED_HOSTS` (domyślnie w compose: `localhost,127.0.0.1,backend`).  
  Baza: SQLite w `backend/db.sqlite3` (zapis w volume przy montowaniu `./backend`).
- **Frontend:** `VITE_API_PROXY_TARGET` – adres API (w compose: `http://backend:8000`).
