# Veto — Baza Procedur Klinicznych
### Architektura danych + 8 scenariuszy MVP | Small animal GP | Psy i koty

> Źródła: WSAVA Global Guidelines (2022, 2024), ISFM Guidelines, ACVIM Consensus Statements, WAVD Guidelines, ISCAID Guidelines

---

## CZĘŚĆ I — ARCHITEKTURA DANYCH

### Model danych — schemat TypeScript

```typescript
// Główne typy węzłów — drzewo decyzyjne procedury
type NodeType = 'question' | 'action' | 'ddx' | 'triage_result' | 'referral'

type ProcedureNode = QuestionNode | ActionNode | DDxNode | TriageResultNode | ReferralNode

// Węzeł pytania — rozgałęzienie decyzyjne
type QuestionNode = {
  id: string
  type: 'question'
  label: string              // krótki label do breadcrumba
  text: string               // pełna treść pytania
  hint?: string              // dodatkowy kontekst dla lekarza
  options: {
    label: string
    nextId: string
    data?: Record<string, string>   // dane zbierane do stanu (np. species, duration)
    variant?: 'normal' | 'urgent' | 'cito'
  }[]
}

// Węzeł akcji — co zrobić, checklist
type ActionNode = {
  id: string
  type: 'action'
  label: string
  title: string
  body?: string
  urgency?: 'routine' | 'urgent' | 'cito'
  checklist?: {
    id: string
    text: string
    required: boolean
  }[]
  nextId?: string            // opcjonalne przejście dalej
  drugs?: DrugReference[]   // powiązane leki z bazy
  labTests?: LabTest[]      // zalecane badania
}

// Węzeł DDx — lista diagnoz różnicowych
type DDxNode = {
  id: string
  type: 'ddx'
  label: string
  clinicalSign: string      // objaw wejściowy
  species: ('dog' | 'cat')[]
  differentials: {
    rank: number            // 1 = najbardziej prawdopodobna
    name: string
    likelihood: 'common' | 'uncommon' | 'rare'
    keyFeatures: string[]  // cechy odróżniające
    nextStepId?: string    // link do algorytmu diagnostycznego
  }[]
  source: string           // np. "WSAVA 2022", "ACVIM 2020"
}

// Wynik triażu — obliczany dynamicznie
type TriageResultNode = {
  id: string
  type: 'triage_result'
  label: string
  dynamic: true
  compute: (data: Record<string, string>) => {
    urgency: 'cito' | 'urgent' | 'soon' | 'routine'
    title: string
    recommendation: string
    timeframe: string      // np. "dziś", "24-48h", "7 dni"
  }
}

// Skierowanie — kiedy GP powinien odesłać do specjalisty
type ReferralNode = {
  id: string
  type: 'referral'
  label: string
  specialty: string        // np. "neurolog", "kardiolog", "dermatolog"
  reason: string
  urgency: 'routine' | 'urgent' | 'cito'
  notes?: string
}

// Główna procedura
type ClinicalProcedure = {
  id: string
  name: string
  nameEn: string
  category: ProcedureCategory
  species: ('dog' | 'cat')[]
  entryNodeId: string
  nodes: Record<string, ProcedureNode>
  tags: string[]           // do wyszukiwania
  source: string           // źródło wytycznych
  lastReviewed: string     // ISO date
  reviewedBy?: string      // imię/specjalizacja weryfikującego wet.
}

type ProcedureCategory =
  | 'dermatology'
  | 'gastroenterology'
  | 'cardiology'
  | 'neurology'
  | 'internal_medicine'
  | 'preventive_care'
  | 'emergency'
  | 'urology'
  | 'orthopedics'
  | 'oncology'

// Referencja do leku
type DrugReference = {
  name: string
  dose?: string
  route?: string
  notes?: string
  plumbsRef?: string       // do przyszłej integracji z Plumb's
}

// Badanie laboratoryjne / diagnostyczne
type LabTest = {
  name: string
  type: 'bloodwork' | 'urinalysis' | 'imaging' | 'cytology' | 'culture' | 'other'
  priority: 'first_line' | 'second_line' | 'optional'
  notes?: string
}
```

### Schemat bazy danych — PostgreSQL

```sql
-- Procedury kliniczne
CREATE TABLE clinical_procedures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug VARCHAR(100) UNIQUE NOT NULL,   -- np. 'pruritus-dog'
  name VARCHAR(200) NOT NULL,
  name_en VARCHAR(200),
  category VARCHAR(50) NOT NULL,
  species TEXT[] NOT NULL,             -- {'dog','cat'}
  entry_node_id VARCHAR(100) NOT NULL,
  nodes JSONB NOT NULL,                -- całe drzewo jako JSONB
  tags TEXT[],
  source TEXT,
  last_reviewed DATE,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Historia użycia procedury w wizytach
CREATE TABLE visit_procedure_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  visit_id UUID REFERENCES visits(id),
  procedure_id UUID REFERENCES clinical_procedures(id),
  doctor_id UUID REFERENCES users(id),
  patient_id UUID REFERENCES patients(id),
  path JSONB NOT NULL,                 -- przebyta ścieżka kroków
  collected_data JSONB,               -- zebrane dane (objawy, czas trwania etc.)
  result_node_id VARCHAR(100),        -- węzeł końcowy
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indeksy
CREATE INDEX idx_procedures_category ON clinical_procedures(category);
CREATE INDEX idx_procedures_species ON clinical_procedures USING GIN(species);
CREATE INDEX idx_procedures_tags ON clinical_procedures USING GIN(tags);
CREATE INDEX idx_sessions_visit ON visit_procedure_sessions(visit_id);
```

### Integracja z formularzem wizyty

Procedura jest dostępna jako **panel boczny** podczas wypełniania sekcji "Wywiad" i "Badanie". Lekarz może:
1. Kliknąć "Uruchom procedurę" → wybiera z listy per objaw
2. Przejść przez kroki → system zbiera dane
3. Wynik (DDx lista, checklist badań, zalecenie pilności) trafia automatycznie do odpowiednich pól wizyty
4. Lekarz akceptuje lub modyfikuje sugestie

---

## CZĘŚĆ II — 8 PROCEDUR KLINICZNYCH

---

## PROCEDURA 1 — Świąd (Pruritus)
**Kategoria:** Dermatologia | **Gatunki:** Pies, Kot  
**Źródło:** WSAVA Dermatology Guidelines; WAVD Demodicosis Guidelines 2020; ISCAID Superficial Bacterial Folliculitis Guidelines 2014

### Drzewo decyzyjne

```
START → [P1] Charakter świądu
  ├─ Sezonowy → [P2] Rozkład zmian
  │   ├─ Cały tułów / dogrzbietowy → DDx: alergia środowiskowa (atopia)
  │   └─ Okolica uszu, pyska, łap → DDx: atopia + wtórna infekcja
  └─ Całoroczny → [P3] Wiek wystąpienia
      ├─ < 6 mcy → [P4] Zeskrobiny skóry
      │   ├─ Demodex (+) → AKCJA: Protokół leczenia demodektozy
      │   └─ Demodex (-) → DDx: dermatofitoza, alergia pokarmowa
      └─ > 6 mcy → [P5] Lokalizacja
          ├─ Brzuch / pachwiny / pachy → DDx: alergia pokarmowa, Malassezia
          └─ Uszy + łapy + pysk → DDx: atopia, Malassezia, wtórna pyodermia
```

### Lista DDx — Świąd u psa (całoroczny, młody pacjent)

| Rank | Diagnoza | Częstość | Cechy kluczowe |
|------|----------|----------|----------------|
| 1 | Demodex spp. | Częsta | Zeskrobiny (+), łysienie, wiek <2 lat |
| 2 | Pyodermia powierzchowna | Częsta | Cytologia: neutrofile + bakterie |
| 3 | Alergia pokarmowa | Częsta | Całoroczna, brak sezonowości, biegunka |
| 4 | Dermatofitoza | Rzadka | DTM (+), okrągłe ogniska łysienia |
| 5 | Atopia | Częsta | Sezonowość, inne atopiki w wywiadzie rodzinnym |
| 6 | Malassezia | Częsta | Cytologia: drożdże, tłusty zapach |

### Badania pierwszej linii

1. **Zeskrobiny skóry** (głębokie + powierzchowne) → Demodex, Cheyletiella
2. **Cytologia odciskowa zmian** → bakterie, drożdże
3. **Taśma klejąca** → Malassezia, Cheyletiella
4. **DTM** (Dermatophyte Test Medium) → dermatofity, jeśli ogniska okrągłe

### Protokół — Demodekoza uogólniona (WAVD 2020)

**Leki pierwszego wyboru:**
- Isoxazoline (fluralaner / sarolaner / afoxolaner / lotilaner) — leczenie z wyboru
- Alternatywa: iwermektyna (ostrożnie — testy MDR1/ABCB1 u wrażliwych ras)

**Monitorowanie:** Zeskrobiny co 4 tygodnie → leczenie minimum do 2 ujemnych wyników

---

## PROCEDURA 2 — Wymioty ostre
**Kategoria:** Gastroenterologia | **Gatunki:** Pies, Kot  
**Źródło:** WSAVA Gastrointestinal Standardization Group; ACVIM Consensus Statements

### Triage wejściowy

```
START → [T1] Ocena stabilności pacjenta
  ├─ NIESTABILNY (wstrząs, ból brzucha, rozdęcie) 
  │   → CITO: podejrzenie GDV/wgłobienie/niedrożność → RTG + linia dożylna NATYCHMIAST
  └─ STABILNY → [T2] Czas trwania
      ├─ < 5 dni (ostre) → [T3] Zawartość wymiocin
      │   ├─ Krew (hematemesis) → pilne: NSAID/NLPZ w wywiadzie? wrzód? ciało obce?
      │   └─ Treść żołądkowa → [T4] Liczba epizodów / dobę
      │       ├─ < 3 → leczenie objawowe ambulatoryjne
      │       └─ > 3 lub postępujące → RTG + morfologia + biochemia
      └─ > 5 dni (przewlekłe) → Protokół przewlekłych wymiotów
```

### Lista DDx — Wymioty ostre u psa

| Rank | Diagnoza | Cechy kluczowe | Badanie |
|------|----------|----------------|---------|
| 1 | Gastroenteritis dietetica | Nagłe, po zmianie diety/wyskokach | Kliniczny |
| 2 | Ciało obce żołądka | Młody pies, zabawki | RTG, USG |
| 3 | Pancreatitis | Ból brzucha, tłusty posiłek, rasa | fPLI / spec cPL |
| 4 | GDV | Rozdęcie, nieproduktywne wymioty, duża rasa | RTG NATYCHMIAST |
| 5 | Parvowiroza | Nieszczepienny szczeniak, krwawa biegunka | Ag test |
| 6 | Leptospiroza | Nieszczepiony, kontakt z wodą, żółtaczka | Biochemia, serologia |
| 7 | Niedrożność jelitowa | Ból, anoreksja, progresja | RTG, USG |
| 8 | Niewydolność nadnerczy | Słabość, hiponatremia | Elektrolity, ACTH test |

### Czerwone flagi — odesłanie/hospitalizacja

- Rozdęcie brzucha → RTG CITO (podejrzenie GDV)
- Wymioty z krwią + anoreksja > 24h
- Odwodnienie > 8%
- Ból przy palpacji brzucha
- Podejrzenie połknięcia ciała obcego lub trucizny

### Badania — wymioty ostre z czerwonymi flagami

**Pierwsza linia:** Morfologia, biochemia pełna, elektrolity, RTG brzucha 2 projekcje  
**Druga linia:** USG jamy brzusznej, spec cPL (pancreatitis), Parvo Ag test

---

## PROCEDURA 3 — Poliuria / Polidypsja (PU/PD)
**Kategoria:** Interna | **Gatunki:** Pies, Kot  
**Źródło:** ACVIM; ISFM Hypertension Guidelines 2017; ACVIM Cardiomyopathy in Cats 2020

### Definicja progów klinicznych

- **Polidypsja:** > 90 ml/kg/dobę (pies) / > 45 ml/kg/dobę (kot)
- **Poliuria:** > 50 ml/kg/dobę

### Drzewo decyzyjne

```
START → [P1] Gatunek
  ├─ KOT → [K1] Wiek
  │   ├─ > 7 lat → DDx: nadczynność tarczycy, CKD, cukrzyca, nadciśnienie
  │   └─ < 7 lat → DDx: cukrzyca, CKD, akromegalia
  └─ PIES → [P2] Płeć / status reprodukcyjny
      ├─ Niekastrowana suka → [P3] Faza cyklu / wydzielina z sromu
      │   ├─ Tak → DDx: pyometra (CITO)
      │   └─ Nie → panel PU/PD
      └─ Reszta → [P4] Panel podstawowy PU/PD
```

### Panel diagnostyczny PU/PD — kolejność badań

**Etap 1 — Badania podstawowe (zawsze):**
1. Morfologia
2. Biochemia pełna (kreatynina, BUN, ALT, ALP, glukoza, białko)
3. Elektrolity (Na, K, Ca)
4. Badanie moczu ze stosunkiem białko:kreatynina (UPC) + sedyment
5. Ciężar właściwy moczu (przed pobraniem IV)

**Etap 2 — W zależności od wyników etapu 1:**
- Glukoza moczu (+) → krzywa glukozowa / fruktozoamina → cukrzyca
- ALP ↑↑ u psa → kortyzol bazalny / test hamowania deksametazonem → Cushing
- T4 u kota > 7 lat → nadczynność tarczycy
- Kreatynina ↑ → IRIS staging CKD → UPC, ciśnienie krwi
- Ca ↑ → PTH, PTHrP → hiperkalcemia (onkologiczna vs. pierwotna)

### Lista DDx — PU/PD u psa

| Rank | Diagnoza | Kluczowe cechy | Badanie potwierdzające |
|------|----------|----------------|------------------------|
| 1 | Hiperadrenokortycyzm (Cushing) | ALP ↑↑, wielki brzuch, łysienie | LDDS test / ACTH stim |
| 2 | Cukrzyca | Glukoza ↑, glukozuria | Fruktozoamina |
| 3 | CKD | Kreatynina ↑, UPC ↑ | IRIS staging |
| 4 | Pyometra | Niekastrowana suka | USG macicy |
| 5 | Hiperkalcemia | Ca ↑, osłabienie | PTH, RTG klatki, USG |
| 6 | Moczówka prosta | Ciężar właściwy moczu <1.006 | Test głodzenia wodnego |
| 7 | Hepatopatia | ALT↑ ALP↑ | USG wątroby, biopsja |
| 8 | Pielonefritis | Gorączka, leukocytoza | Posiew moczu |

---

## PROCEDURA 4 — Duszność / Kaszel
**Kategoria:** Kardiologia / Pulmonologia | **Gatunki:** Pies, Kot  
**Źródło:** ACVIM Consensus Statement Cardiomyopathies in Cats 2020; ACVIM MVD Guidelines 2019

### TRIAGE — stabilizacja przed diagnostyką

```
START → OCENA KRYTYCZNA (30 sekund)
  ├─ Sinica / ortopnoe / otwarte usta u kota → CITO
  │   → minimum stresu, tlen, RTG klatki w pozycji stojącej, bez manipulacji
  └─ Stabilny oddech → [D1] Charakter kaszlu
      ├─ Produktywny / mokry → DDx: zapalenie płuc, wysięk opłucnowy
      ├─ Suchy / napadowy → DDx: kaszel sercowy (MVD), zapalenie tchawicy, ciało obce
      └─ Nocny / po wysiłku → DDx: CHF (zastoinowa niewydolność serca)
```

### Lista DDx — Kaszel u psa

| Rank | Diagnoza | Cechy | Badanie |
|------|----------|-------|---------|
| 1 | MVD (Myxomatous Mitral Valve Disease) | Szmer sercowy, małe rasy, starszy wiek | RTG, ECHO |
| 2 | Zapalenie tchawicy (kennelkaszel) | Suchy, napadowy, niedawny kontakt z psami | Kliniczny |
| 3 | Zapalenie płuc | Gorączka, produktywny kaszel | RTG, morfologia |
| 4 | Kolaps tchawicy | Gęsie pohukiwanie, małe rasy | Fluoroskopia, RTG |
| 5 | Heartworm | Obszary endemiczne, eozynofilia | Ag test |
| 6 | Nowotwór płuca | Starszy wiek, chudnięcie | RTG, CT |

### Lista DDx — Duszność u kota

| Rank | Diagnoza | Cechy | Badanie |
|------|----------|-------|---------|
| 1 | HCM (Hypertrophic Cardiomyopathy) | Szmer lub rytm cwałowy, ECHO | ECHO — złoty standard |
| 2 | Astma/Bronchitis | Kaszel z wydechem, młodszy wiek | RTG, bronchoskopia |
| 3 | Wysięk opłucnowy | Matowość przy osłuchiwaniu | RTG, USG |
| 4 | Chylothorax | Mętny wysięk | Analiza płynu |
| 5 | Pyothorax | Gorączka, sepsa | RTG, analiza płynu |

### Ważna reguła kliniczna — kot z dusznością

> **Nie badaj kota w duszności dopóki nie jest stabilny.**  
> Stres podczas badania może spowodować zatrzymanie oddechu.  
> Kolejność: tlen → minimalna manipulacja → RTG → dopiero pełne badanie

---

## PROCEDURA 5 — Kulawizna (Kończyna piersiowa / miedniczna)
**Kategoria:** Ortopedia | **Gatunki:** Pies, Kot  
**Źródło:** WSAVA Pain Management Guidelines 2022; ACVIM

### Drzewo decyzyjne

```
START → [O1] Typ kulawizny
  ├─ Nagła (< 24h, uraz) → [O2] Ocena bólu
  │   ├─ Ból silny + niemożność oparcia → RTG PILNE (złamanie?)
  │   └─ Kulawizna bez oparcia → badanie ortopedyczne + RTG
  └─ Przewlekła / postępująca → [O3] Wiek
      ├─ < 18 mcy → DDx: HD, OCD, pano, deformacje wzrostowe
      └─ > 5 lat → DDx: artroza, DJD, guz kości, pęknięcie LCA
```

### Lokalizacja kulawizny — kończyna miedniczna u psa

| Rank | Diagnoza | Wiek | Rasa | Test |
|------|----------|------|------|------|
| 1 | Dysplazja biodra (HD) | < 18 mcy | Duże rasy | RTG bioder PennHIP / OFA |
| 2 | Pęknięcie LCA | 3-8 lat | Wszystkie | Szuflada, test kompresji piszczeli |
| 3 | DJD / artroza | > 5 lat | Wszystkie | RTG |
| 4 | Panostitis | 5-18 mcy | Duże rasy | RTG (zamazanie jamy szpikowej) |
| 5 | OCD kolana/skoku | 6-18 mcy | Duże rasy | RTG, artroskopia |
| 6 | Guz kości (osteosarcoma) | > 7 lat | Duże rasy | RTG (agresywna zmiana), biopsja |

### Ocena bólu — Skala Glasgow CMPS-SF (WSAVA 2022)

Skala 0-24 pkt. Próg interwencji bólowej: **≥ 6 pkt**

Parametry: wokalizacja, wyraz pyska, pozycja, ruchliwość, odpowiedź na dotyk

### Skierowanie do specjalisty ortopedycznego

- Podejrzenie złamania wymagającego stabilizacji
- Pęknięcie LCA → TPLO / TTA
- Dysplazja biodra kwalifikująca do TPO
- Podejrzenie guza kości

---

## PROCEDURA 6 — Szczepienia (Wizyta profilaktyczna)
**Kategoria:** Medycyna zapobiegawcza | **Gatunki:** Pies, Kot  
**Źródło:** WSAVA Vaccination Guidelines 2024

### Szczepionki CORE (obowiązkowe) — Pies

| Choroba | Preparat | Pierwsze szczepienie | Booster |
|---------|----------|---------------------|---------|
| Nosówka / Parwowiroza / Adeno | DHPPiL (combo) | 6-8 tydz., co 2-4 tyg. do 16 tydz. | Po roku, potem co 3 lata |
| Wścieklizna | Monovalent | 12 tydz. | Wg przepisów krajowych |

### Szczepionki CORE — Kot

| Choroba | Preparat | Schemat |
|---------|----------|---------|
| Panleukopenia / Herpeswirus / Caliciwirus | FHVCPi | 6-8 tydz., co 2-4 tydz. do 16 tydz., po roku, co 3 lata |
| Wścieklizna | Monovalent | Wg przepisów |

### Kluczowa zmiana WSAVA 2024

> Szczenięta i kocięta powinny otrzymać dawkę core vaccines **w wieku 26+ tygodni** (nie jak poprzednio 12-16 mcy) jeśli przegapiły wcześniejszy schemat — eliminuje ryzyko okna immunologicznego.

### Drzewo decyzyjne — czy szczepić dziś?

```
START → Sprawdź historię szczepień w karcie pacjenta
  ├─ Brak szczepień → Zaplanuj pełny schemat
  ├─ Szczepienia aktualne → Brak działania, odnotuj kontrolę
  ├─ Szczepienia przeterminowane < 3 miesiące → Pojedyncza dawka booster
  └─ Szczepienia przeterminowane > 3 miesiące → Restart schematu jak szczenię
```

### Checklist wizyty profilaktycznej

- [ ] Odpchlenie / odrobaczenie — aktualność
- [ ] Profilaktyka przeciw Heartworm (obszary endemiczne)
- [ ] Ocena uzębienia (dental score 0-4)
- [ ] Pomiar masy ciała + BCS (Body Condition Score 1-9)
- [ ] Badanie ogólne: węzły chłonne, auskultacja, palpacja brzucha
- [ ] Badanie krwi — zalecane rocznie u psów > 7 lat i kotów > 7 lat
- [ ] Pomiar ciśnienia — zalecany u kotów > 7 lat

---

## PROCEDURA 7 — Zatrzymanie moczu u kota (Urethral Obstruction)
**Kategoria:** Urologia | **Gatunki:** Kot (głównie samce)  
**Źródło:** Standards of Care — Blocked Cat Protocol; ISFM

### TRIAGE — ZAWSZE CITO

> **Zablokowany kot = nagły przypadek.**  
> Śmierć może nastąpić w ciągu 24-48h z powodu hiperkaliemii i mocznicy.

```
START → Objawy: wysiłkowe oddawanie moczu, wchodzenie do kuwety bez efektu
  → CITO: pęcherz powiększony i bolesny przy palpacji?
      ├─ TAK → Hospitalizacja natychmiastowa
      └─ NIE → Wykluczyć blokadę (FLUTD bez obstrukcji)
```

### Protokół stabilizacji (przed odblokowanie)

1. **EKG** — ocena hiperkaliemii (piki T, szerokie QRS)
2. **Linia dożylna** → NaCl 0.9% (nie PWE — zawiera K)
3. **Elektrolity** → K+, Na+, kreatynina, BUN, pH
4. **Leczenie hiperkaliemii** jeśli K > 6.5 mEq/L:
   - Glukonian wapnia IV (kardioprotekcja)
   - Insulina + glukoza (przesunięcie K do komórek)
5. **Odblokowanie cewnikiem** po stabilizacji

### Lista DDx — FLUTD (Feline Lower Urinary Tract Disease)

| Diagnoza | Częstość | Obstrukcja? | Cechy |
|----------|----------|-------------|-------|
| Idiopatyczne FIC | 55-65% | Nie | Stres, nagłe, samoistnie mija |
| Urolithiasis (struwyty) | 15-20% | Możliwa | Widoczne w RTG |
| Urolithiasis (szczawian Ca) | 10% | Możliwa | RTG, USG |
| Zatkanie cewki (czop, kamień) | 20% samców | TAK | Powiększony pęcherz |
| Infekcja bakteryjna UTI | < 5% (koty) | Rzadko | Posiew moczu (+) |

### Edukacja właściciela po hospitalizacji

- Dieta mokra (zwiększenie nawodnienia)
- Woda dostępna w wielu miejscach (fontanna)
- Eliminacja stresorów środowiskowych
- Kontrola za 7-14 dni
- Ryzyko nawrotu: ~30-40% w ciągu roku

---

## PROCEDURA 8 — Letarg / Osłabienie ogólne
**Kategoria:** Interna | **Gatunki:** Pies, Kot  
**Źródło:** WSAVA; ACVIM; ISFM

> Letarg to jeden z najtrudniejszych objawów — bardzo szeroka lista DDx. Procedura pomaga zawęzić przez pytania ukierunkowane.

### Drzewo decyzyjne

```
START → [L1] Charakter objawów
  ├─ Nagłe (< 24h) → TRIAGE PILNY
  │   ├─ Bladość błon śluzowych → DDx: anemia, krwawienie wewnętrzne, śledziona
  │   ├─ Żółtaczka → DDx: hemoliza, wątrobowa, pozawątrobowa
  │   └─ Gorączka > 39.5°C → DDx: infekcja, immunologiczne, nowotwór
  └─ Postępujące (dni–tygodnie) → [L2] Wiek i sygnalment
      ├─ Młody (< 3 lat) → DDx: choroby zakaźne, wady wrodzone, alergie
      └─ Starszy (> 7 lat) → [L3] Dodatkowe objawy
          ├─ Utrata masy ciała → DDx: nowotwór, IBD, hipertyreoza (kot), cukrzyca
          ├─ PU/PD → patrz Procedura 3
          └─ Brak apetytu → DDx: ból, nerkowa, wątrobowa, dentystyczna
```

### Minimalne badania przy letargu niewyjaśnionym

**Zawsze (first line):**
- Morfologia z rozmazem
- Biochemia pełna (panel narządowy)
- Elektrolity
- Badanie moczu
- Pomiar temperatury

**W zależności od wyników:**
- Żółtaczka → bilirubina, USG wątroby
- Anemia → retikulocyty, Coombs, hemogram
- Gorączka → posiewy, panel zakaźny (Leishmania, Leptospira, Ehrlichia)
- Starszy kot → T4

### Czerwone flagi — hospitalizacja/skierowanie

- Bladość + tachykardia → podejrzenie krwawienia wewnętrznego (CITO)
- Temperatura > 41°C lub < 37°C
- Żółtaczka intensywna + zmiana świadomości
- Postępująca utrata masy > 10% w ciągu 4 tygodni

---

## CZĘŚĆ III — PLAN ROZBUDOWY BAZY

### Kolejne procedury (po MVP)

| Priorytet | Procedura | Kategoria |
|-----------|-----------|-----------|
| 9 | Ból brzucha / Napięty brzuch | Gastro / Chirurgia |
| 10 | Anemia | Interna / Hematologia |
| 11 | Drgawki / Napady padaczkowe | Neurologia |
| 12 | Choroba przewlekła nerek (CKD) — kontrola | Nefrologia |
| 13 | Cukrzyca — kontrola i kryzys | Endokrynologia |
| 14 | Nowotwór — podejrzenie / staging | Onkologia |
| 15 | Gorączka niewyjaśniona (FUO) | Interna |
| 16 | Ból oka / Czerwone oko | Okulistyka |
| 17 | Zaburzenia neurologiczne — chód / ataksja | Neurologia |
| 18 | Ból zębów / Choroba przyzębia | Stomatologia |

### Proces utrzymania bazy

- **Przegląd co 12 miesięcy** — weryfikacja z nowymi wytycznymi WSAVA/ISFM/ACVIM
- **Weryfikacja przez lekarza weterynarza** przed publikacją każdej procedury
- **Pole `last_reviewed` + `reviewed_by`** w każdej procedurze — widoczne dla lekarza
- **Disclaimer** na każdej procedurze: "Narzędzie pomocnicze. Nie zastępuje oceny klinicznej."

---

*Dokument: Veto Clinical Procedures v1.0 | Przygotowany: 2026-04 | Źródła: WSAVA 2022/2024, ISFM, ACVIM, WAVD, ISCAID*
