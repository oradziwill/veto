# GO-LIVE checklist (LAB Connector)

## A. Przed instalacja

- [ ] Potwierdzone modele urzadzen i formaty HL7 (BC-60R, vetXpert).
- [ ] Potwierdzona tabela mapowania `vendor_code -> test Veto`.
- [ ] Ustalony host dla connectora (stabilny, z auto-startem).

## B. Siec i bezpieczenstwo

- [ ] Skonfigurowany `LISTEN_HOST` i `LISTEN_PORT` oraz routing z analizatorow.
- [ ] Otwarty outbound HTTPS do `VETO_BASE_URL`.
- [ ] Ustawiony poprawny `VETO_INGEST_TOKEN`.
- [ ] Token zapisany bezpiecznie (poza publicznymi notatkami/repo).

## C. Deployment

- [ ] `.env` skonfigurowane i zweryfikowane.
- [ ] Usluga systemowa (`systemd` lub `launchd`) aktywna.
- [ ] Health endpoint odpowiada: `/health`.
- [ ] Metrics endpoint odpowiada: `/metrics`.

## D. Testy E2E (na miejscu)

- [ ] Co najmniej 3 testowe probki z BC-60R dochodza do Veto.
- [ ] Co najmniej 3 testowe probki z vetXpert dochodza do Veto.
- [ ] Symulacja chwilowego braku API Veto i potwierdzenie recovery z outbox.
- [ ] Brak rekordow dead-letter po testach (`outbox_dead_total = 0`).

## E. Akceptacja operacyjna

- [ ] Personel wie, jak sprawdzic status (`health`, `metrics`, logi).
- [ ] Runbook jest dostepny i uzgodniony.
- [ ] Wlasciciel operacyjny i sciezka eskalacji sa wskazane.
