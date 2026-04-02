# Frontend handoff: staff app — portal follow-ups (KPI, RODO, powiadomienia)

**Dla kogo:** zespół FE budujący **aplikację dla personelu** (nie owner portal).
**Auth:** zwykły staff JWT z `POST /api/auth/token/`:

```http
Authorization: Bearer <staff_access>
```

Nie wysyłaj tokena portalowego (`/api/portal/*`) do tych endpointów.

**Repozytorium:** pracuj na **feature branchu** i włączaj zmiany przez PR do `main` (unikaj committów wprost na `main` poza hotfixami).

---

## 1. Metryki rezerwacji z portalu (KPI)

| | |
|--|--|
| **Method** | `GET` |
| **Path** | `/api/reports/portal-booking-metrics/` |
| **Permissions** | Zalogowany użytkownik z kliniką + rola staff (`IsStaffOrVet`: lekarz, recepcja, admin). |

**Query (wszystkie opcjonalne):**

| Param | Opis |
|-------|------|
| `from` lub `date_from` | `YYYY-MM-DD` — początek zakresu (domyślnie: dziś − 30 dni) |
| `to` lub `date_to` | `YYYY-MM-DD` — koniec zakresu włącznie (domyślnie: dziś w kalendarzu serwera) |

**Response 200** (JSON):

```json
{
  "from": "2026-03-01",
  "to": "2026-03-30",
  "appointments_total": 120,
  "appointments_booked_via_portal": 18,
  "share_portal": 0.15
}
```

- `share_portal` — ułamek wizyt z portalu względem `appointments_total` (0 gdy brak wizyt).
- Liczone po **`starts_at`** wizyty w zadanym przedziale, tylko wizyty **bieżącej kliniki**.

**Błędy:** `400` — zły format daty lub `from` > `to`; `401` / `403` jak przy innych endpointach staff.

**UI:** wykres / kafelek nad kalendarzem, zakres dat (np. miesiąc), nie trzeba cache’ować agresywnie.

---

## 2. Eksport danych właściciela (RODO / pakiet JSON)

| | |
|--|--|
| **Method** | `GET` |
| **Path** | `/api/clients/<client_id>/gdpr-export/` |
| **Permissions** | **Tylko clinic admin** (`role === "admin"`). Recepcja / lekarz dostanie **403**. |

**Response 200:** JSON z pakietem ograniczonym do **tej kliniki** m.in. `client`, `membership`, `patients` (bez pól AI / notatek wewnętrznych), `appointments`, `invoices` (+ linie), `vaccinations`. Na końcu `_note` wyjaśnia pominięcia.

**Inne statusy:**

| Status | Znaczenie |
|--------|-----------|
| `404` | Klient bez aktywnego członkostwa w tej klinice (lub brak rekordu) |
| `403` | Brak uprawnień admina lub brak kliniki |

Backend zapisuje w audit: `client_gdpr_export_downloaded` (`entity_type=client`).
**UI:** przycisk na profilu klienta / liście tylko dla admina; możliwość `save as` / `download` z odpowiedzi JSON (np. `client-<id>-export.json`).

---

## 3. Powiadomienia in-app — nowa wizyta z portalu

Gdy właściciel zarezerwuje online, **wszyscy** lekarze / recepcja / admin **danej kliniki** mogą dostać wpis w skrzynce powiadomień (flag serwerowa `PORTAL_NOTIFY_STAFF_ON_BOOKING`, domyślnie włączona).

| | |
|--|--|
| **List / retrieve** | `GET /api/notifications/` (paginacja, jak dotąd) |
| **Nowy `kind`** | `portal_appointment_booked` |

Typowy payload (jak inne notyfikacje): `id`, `kind`, `title`, `body`, `link_tab`, `is_read`, `created_at`, …
Dla tego typu **`link_tab`** ustawiane jest na **`"appointments"`** — możesz użyć do nawigacji w SPA (np. zakładka wizyty / kalendarz).

**UI:** rozpoznaj `kind === "portal_appointment_booked"` jeśli chcesz ikonę „online booking”; w przeciwnym razie `title` / `body` są już czytelne dla użytkownika.

---

## 4. Kalendarz / lista wizyt — filtr „z portalu”

Bez nowego endpointu: istniejący **`GET /api/appointments/`** (staff JWT).

**Query:** `booked_via_portal=true` | `false` | `1` | `0` — filtrowanie po polu **`booked_via_portal`** na modelu wizyty.
W odpowiedzi listy / szczegółów pole jest **read-only**.

---

## 5. Powiązana dokumentacja

- Owner portal (OTP, booking, Stripe): [FRONTEND_HANDOFF_CLIENT_PORTAL.md](FRONTEND_HANDOFF_CLIENT_PORTAL.md), [CLIENT_PORTAL_BOOKING.md](CLIENT_PORTAL_BOOKING.md)
- Pakiet „bundla” z innymi feature’ami: [FRONTEND_HANDOFF_RECENT_WORK.md](FRONTEND_HANDOFF_RECENT_WORK.md)
- Audit (w tym eksport RODO): [AUDIT_LOG.md](AUDIT_LOG.md)
