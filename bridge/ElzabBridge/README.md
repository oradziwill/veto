# ElzabBridge (C#)

Local Windows agent that bridges VETO ↔ ELZAB MERA online.

## What it does (Phase 1)

- Exposes `POST /api/v1/fiscal/print-receipt` on `localhost`
- Queues fiscal print jobs and processes them in the background
- Uses a placeholder printer implementation until ELZAB SDK/protocol is added
- Posts a signed callback to VETO backend (`/api/billing/fiscal/callback/`)

## Run locally

1. Install .NET SDK 8+
2. Configure `Bridge:Veto:*` in `appsettings.json`:
   - `BaseUrl` (e.g. `http://localhost:8000`)
   - `FiscalCallbackPath` (default: `/api/billing/fiscal/callback/`)
   - `SharedSecret` (must match VETO)

```bash
cd bridge/ElzabBridge
dotnet restore
dotnet run
```

## Run on Windows (recommended workflow)

### 1) Build on Windows

From PowerShell in `bridge\ElzabBridge`:

```powershell
dotnet restore
dotnet publish -c Release -o .\publish
```

### 2) Configure the agent

Edit `publish\appsettings.json`:

- `Bridge:Veto:BaseUrl`: your backend URL (e.g. `http://127.0.0.1:8000` in dev, or your internal clinic URL)
- `Bridge:Veto:SharedSecret`: shared secret (must match what VETO expects for HMAC)

Optional:

- `Bridge:RequireBearerToken=true` and set `Bridge:BearerToken` to protect the local endpoint if needed.

### 3) Run (dev as console app)

```powershell
.\publish\ElzabBridge.exe
```

Verify:

```powershell
Invoke-RestMethod http://localhost:5190/health
```

### 4) Run as Windows Service (later hardening)

The host is service-capable (`UseWindowsService()`), but installation/packaging depends on your IT constraints.
For now, run it as a console app on the reception PC for PoC.

## API

### Health

`GET /health` → `200 { "status": "ok" }`

### Print receipt (async)

`POST /api/v1/fiscal/print-receipt` → `202 Accepted`

Example request:

```json
{
  "jobId": "11111111-1111-1111-1111-111111111111",
  "clinicId": 1,
  "invoiceId": 123,
  "paymentId": 456,
  "currency": "PLN",
  "paymentForm": "cash",
  "lines": [
    { "name": "Wizyta", "quantity": 1, "unitPriceGross": 150.00, "vatRate": 0.23 }
  ],
  "totals": { "amountGross": 150.00 },
  "requestedBy": { "userId": 9, "email": "user@example.com" },
  "idempotencyKey": "invoice:123/payment:456"
}
```

## How to test end-to-end with VETO (PoC)

At this moment, VETO still needs a backend endpoint to accept the callback:

- `POST /api/billing/fiscal/callback/` + HMAC verification using `Bridge:Veto:SharedSecret`

Once that exists:

1. Start VETO backend
2. Start the agent
3. Trigger `POST /api/v1/fiscal/print-receipt` (from Postman / PowerShell) and observe:
   - agent logs: job queued → printed
   - VETO backend logs: callback received → stored on the payment/invoice

If you want to test the agent even before VETO endpoint exists, temporarily point `Bridge:Veto:BaseUrl` to a local request bin / mock server, or stub the callback client.

## Next steps

- Replace `ElzabFiscalPrinterStub` with actual ELZAB MERA online integration (vendor SDK/protocol)
- Add durable storage for job statuses (optional) + retries/backoff
- Add production service installation instructions and packaging
