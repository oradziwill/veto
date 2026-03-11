# Architecture

## Overview

Veto is a veterinary clinic management system. It runs two separate services — a Django REST API and a React SPA — both deployed on AWS ECS Fargate.

```
Browser
  └─▶ ALB (HTTPS)
        ├─▶ /api/*  → ECS backend (Django + Gunicorn)
        └─▶ /*      → ECS frontend (Nginx + React)
                           │
                           ▼
                    RDS PostgreSQL  (private subnet)
                    Secrets Manager (DB password, Django secret, CORS)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5, Django REST Framework, SimpleJWT |
| Frontend | React (Vite), react-i18next (PL/EN), react-router-dom |
| Database | PostgreSQL 15 on RDS |
| Container runtime | AWS ECS Fargate |
| Image registry | AWS ECR |
| Infrastructure | Terraform (modules in `terraform/`) |
| CI/CD | GitHub Actions with OIDC authentication |
| Secret storage | AWS Secrets Manager |

---

## Repository Layout

```
veto/
├── backend/                Django project
│   ├── apps/
│   │   ├── accounts/       Custom User model, roles, permissions
│   │   ├── billing/        Invoices, payments, services, KSeF
│   │   ├── clients/        Pet owners (Client model)
│   │   ├── inventory/      Clinic stock items
│   │   ├── labs/           Lab results
│   │   ├── medical/        Clinical exam records
│   │   ├── patients/       Animals (Patient model)
│   │   ├── scheduling/     Appointments, rooms, availability
│   │   └── tenancy/        Clinic model (multi-tenancy root)
│   ├── config/             Django settings, urls, wsgi
│   └── requirements.txt
├── frontend/               React app (Vite)
│   └── src/
│       ├── components/
│       │   ├── modals/     Create/edit forms (overlays)
│       │   └── tabs/       Main content tabs
│       ├── locales/        en.json / pl.json translations
│       ├── services/api.js Axios API client
│       └── views/          DoctorsView, ReceptionistView
├── terraform/              AWS infrastructure as code
├── .github/workflows/      CI (ci.yml) and deploy (deploy.yml)
└── docs/                   This documentation
```

---

## Backend App Responsibilities

| App | Key models | Notes |
|---|---|---|
| `tenancy` | `Clinic`, `ClinicHoliday` | Every other model is scoped to a clinic |
| `accounts` | `User` | Extends AbstractUser; has `role` field |
| `clients` | `Client`, `ClientClinic` | A client (owner) can belong to multiple clinics |
| `patients` | `Patient` | Animal; linked to one clinic and one owner |
| `scheduling` | `Appointment`, `Room`, `Vet` | Calendar, availability, waiting room queue |
| `billing` | `Invoice`, `InvoiceLine`, `Payment`, `Service` | Full billing cycle + KSeF XML |
| `inventory` | `InventoryItem` | Stock levels, low-stock alerts |
| `medical` | clinical exam data | Linked to appointments |
| `labs` | lab results | Linked to patients |

---

## Multi-tenancy

Every request is scoped to the clinic of the authenticated user (`request.user.clinic_id`). All querysets filter by `clinic_id`. A user without a clinic can log in but will receive empty results or permission errors.

---

## Frontend Views

| URL | Component | Who sees it |
|---|---|---|
| `/receptionist` | `ReceptionistView` | Receptionist users |
| `/doctors` | `DoctorsView` | Doctor and Admin users |

On login, `authAPI.me()` returns the user's `role` and the view redirects accordingly.
