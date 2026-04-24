# LAB Connector Runbook

## 1) Szybki status

1. Sprawdz health:
   - `curl -fsS http://127.0.0.1:8765/health`
2. Sprawdz metryki:
   - `curl -fsS http://127.0.0.1:8765/metrics`
3. Sprawdz logi procesu/uslugi:
   - `systemctl status lab-connector` (Linux) lub `launchctl print system/com.veto.lab-connector` (macOS).

## 2) Gdy nie przychodza wyniki

1. Potwierdz, ze analizator wysyla na poprawny `LISTEN_HOST:LISTEN_PORT`.
2. Zweryfikuj, czy sa ACK:
   - rosnace `ack_aa_total` oznacza poprawne przyjecie ramek.
   - rosnace `ack_ae_total` oznacza blad parse/walidacji.
3. Jesli sa ACK, ale brak wynikow w Veto:
   - sprawdz `outbox_delivery_fail_total`, `outbox_retry_scheduled_total`, `outbox_dead_total`.
4. Zweryfikuj lacznosc HTTPS do API Veto i poprawny token `X-Lab-Ingest-Token`.

## 3) Interpretacja metryk

- `mllp_frames_received_total`: liczba odebranych ramek MLLP.
- `outbox_enqueued_total`: liczba rekordow zapisanych do kolejki.
- `outbox_delivered_total`: liczba rekordow dostarczonych do API Veto.
- `outbox_delivery_fail_total`: liczba nieudanych prob dostarczenia.
- `outbox_retry_scheduled_total`: liczba zaplanowanych retry.
- `outbox_dead_total`: liczba rekordow oznaczonych jako dead-letter.
- `hl7_parse_error_total`: krytyczne bledy parsera.
- `hl7_reject_total`: odrzucone wiadomosci HL7.
- `hl7_non_oru_total`: wiadomosci inne niz ORU^R01 (ACK bez ingestu).
- `ack_aa_total`, `ack_ae_total`: liczba wyslanych ACK.

## 4) Restart i recovery

1. Restart uslugi:
   - Linux: `sudo systemctl restart lab-connector`
   - macOS: `sudo launchctl kickstart -k system/com.veto.lab-connector`
2. Po restarcie sprawdz:
   - `/health` zwraca `ok`.
   - `outbox_delivered_total` zaczyna rosnac przy nowym ruchu.
3. Przy chwilowej awarii API Veto rekordy powinny zostac w outbox i wyslac sie po powrocie lacznosci.

## 5) Eskalacja

Eskaluj do zespolu dev/integracji, gdy:
- `ack_ae_total` rosnie stale przez >15 minut,
- `outbox_dead_total` > 0,
- brak wzrostu `mllp_frames_received_total` mimo pracy analizatora.
