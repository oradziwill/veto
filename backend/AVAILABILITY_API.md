# Availability API (Scheduling)

This document describes how to use the Availability API to display free appointment slots for veterinarians.

## Authentication

All endpoints require JWT authentication.

Authorization: Bearer <access_token>

## Endpoint

GET /api/availability/

Returns available appointment slots for a given vet on a given date.

### Query parameters

- date (YYYY-MM-DD, required)
- vet (integer, optional)
- slot_minutes (integer, optional, default 30)

### Example request

GET /api/availability/?date=2025-12-23&vet=1

## Response

{
  "date": "2025-12-23",
  "timezone": "UTC",
  "clinic_id": 2,
  "vet_id": 1,
  "slot_minutes": 30,
  "workday": {
    "start": "2025-12-23T09:00:00Z",
    "end": "2025-12-23T17:00:00Z"
  },
  "work_intervals": [
    {
      "start": "2025-12-23T09:00:00Z",
      "end": "2025-12-23T17:00:00Z"
    }
  ],
  "busy": [],
  "free": [
    {
      "start": "2025-12-23T09:00:00Z",
      "end": "2025-12-23T09:30:00Z"
    }
  ]
}

## Frontend usage

- Render free[] as selectable appointment slots
- Do not calculate availability client-side
- Slots already respect vet working hours and existing appointments

## Creating an appointment

POST /api/appointments/

{
  "vet": 1,
  "patient": 5,
  "starts_at": "2025-12-23T09:30:00Z",
  "ends_at": "2025-12-23T10:00:00Z"
}

## Status

Implemented and ready for frontend integration
