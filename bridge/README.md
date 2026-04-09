# Bridge modules (local integrations)

This directory contains **local bridge agents** that run at the reception workstation and integrate external hardware with VETO.

## `ElzabBridge` (C# / Windows)

Local agent intended to run on **Windows** near the fiscal device.

- Exposes local HTTP API for triggering fiscal actions (Phase 1: receipt print)
- Talks to ELZAB device using vendor SDK/protocol (placeholder in repo until SDK is provided)
- Calls back into VETO backend with signed payload (HMAC) so VETO can persist fiscal metadata next to billing payments

### Prerequisites

- .NET SDK 8+
- Windows 10/11 (recommended for production as a Windows Service)
- ELZAB SDK/protocol library and drivers (provided by vendor/installer)

### Build & run (dev)

```bash
cd bridge/ElzabBridge
dotnet restore
dotnet run
```

The agent will listen on `http://localhost:5190` by default.

### Integrating with VETO (backend)

`ElzabBridge` is designed to **call back into VETO** after printing. To complete the integration, VETO must expose an endpoint:

- `POST /api/billing/fiscal/callback/`

and verify:

- `X-Veto-Signature`: base64 HMAC-SHA256 of the **raw request body**, using a shared secret configured on both sides.

Until the backend endpoint exists, you can still validate the agent locally (health + queue processing), but VETO will not “see” the device.

### Production (Windows Service)

The project is designed so it can be hosted as a **Windows Service**. Packaging/installer steps depend on the clinic IT constraints and will be added during hardening.
