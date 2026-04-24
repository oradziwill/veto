// ── Triage matrix: symptom × time → priority ──────────────────────────────
// Time index: 0=dziś, 1=48h, 2=<2tyg, 3=>2tyg postępujące, 4=>2tyg stabilne
export const TRIAGE_MATRIX = {
  a: ['CITO', 'CITO', 'CITO', 'CITO', 'Normalny'],
  b: ['Pilne', 'Pilne', 'Pilne', 'Pilne', 'Normalny'],
  c: ['CITO', 'Pilne', 'Najbliższy', 'Najbliższy', 'Normalny'],
  d: ['CITO', 'CITO', 'Najbliższy', 'Najbliższy', 'Normalny'],
  e: ['CITO', 'Pilne', 'Najbliższy', 'Najbliższy', 'Normalny'],
  f: ['CITO', 'Pilne', 'Najbliższy', 'Najbliższy', 'Normalny'],
  g: ['Pilne', 'Pilne', 'Najbliższy', 'Najbliższy', 'Normalny'],
  h: ['Pilne', 'Pilne', 'Pilne', 'Najbliższy', 'Normalny'],
  i: ['Najbliższy', 'Najbliższy', 'Najbliższy', 'Najbliższy', 'Normalny'],
}

export const TRIAGE_CONFIG = {
  CITO: {
    variant: 'cito',
    body: 'Zdecydowanie odradzamy samą konsultację bez diagnostyki. Pacjent wymaga pilnej oceny tego samego dnia.',
    checklist: [
      'Zaproponuj termin DZIŚ lub jutro rano',
      'Poinformuj lekarza dyżurnego o nagłym przypadku',
      'Zapytaj czy klient woli diagnostykę od razu czy najpierw konsultację',
      'Odnotuj tryb CITO w systemie',
    ],
  },
  Pilne: {
    variant: 'urgent',
    body: 'Zalecamy wizytę w ciągu 2–3 dni. Stan wymaga oceny, ale nie jest bezpośrednim zagrożeniem życia.',
    checklist: [
      'Zaproponuj termin w ciągu 2–3 dni',
      'Odnotuj tryb "Pilny" w systemie',
      'Zapytaj czy klient woli diagnostykę od razu czy najpierw konsultację',
    ],
  },
  Najbliższy: {
    variant: 'normal',
    body: 'Umów na najbliższy wolny termin u neurologa.',
    checklist: [
      'Znaleźć najbliższy wolny termin',
      'Poinformować o kosztach konsultacji',
    ],
  },
  Normalny: {
    variant: 'normal',
    body: 'Standardowy zapis — brak pilności.',
    checklist: [
      'Umów w standardowym terminie',
      'Poinformuj o kosztach i czasie trwania wizyty',
    ],
  },
}

// ── Shared checklists ──────────────────────────────────────────────────────
const DIAG_CHECKLIST = [
  'Sprawdź kartę (nasza / z innej lecznicy / brak)',
  'Jeśli z innej lecznicy — poprosić o skierowanie/wypis',
  'Krew: max 1 miesiąc; zweryfikować czy pacjent może być znieczulany',
  'USG/ECHO: max 6 miesięcy; ECHO obowiązkowe u psów pow. 7 lat i ras: doberman, dalmatyńczyk, rotwailer, york, wilczarz, bokser, owczarek niemiecki, nowofunland, berneńczyk, chart afgański; u kotów: main coon, ragdoll, norweski leśny, syberyjski, brytyjski, pers, devon, sfinx, chartreux',
  'RTG / MRI / TK — zabrać w formie elektronicznej',
  'Na czczo: pies/kot = 8h, szczeniak = 4h; woda — tak',
  'Leki: normalnie (wyjątek: leki na nadciśnienie — zapytać lekarza)',
]

const ZABIEG_CHECKLIST = [
  'Skierowanie od neurologa (aktualne)',
  'Krew: max 1 miesiąc',
  'USG/ECHO — zweryfikuj rasę i wiek (jak wyżej)',
  'Badania obrazowe (MRI/TK/RTG) w formie elektronicznej',
  'Dane pacjenta kompletne w systemie',
  'Poinformować neurologa — lekarz oddzwoni ws. terminu',
]

const KONTROLA_CHECKLIST = [
  'Historia choroby jeśli pacjent nie był u nas',
  'Na czczo: 8h (pies/kot)',
  'Podać termin i koszt kontroli',
]

// ── Decision tree ──────────────────────────────────────────────────────────
export const ASSISTANT_TREE = {
  start: {
    id: 'start',
    type: 'question',
    label: 'Start',
    question: 'W czym mogę pomóc? Czego dotyczy zapis?',
    options: [
      { label: 'Konsultacja / neurolog', nextId: 'konsultacja_objawy' },
      { label: 'Diagnostyka', nextId: 'diag_typ' },
      { label: 'Zabieg', nextId: 'zabieg_status' },
      { label: 'Kontrola', nextId: 'kontrola_lekarz' },
      { label: 'Pogorszenie stanu', nextId: 'pogorszenie_karta' },
    ],
  },

  // ── Ścieżka 1: Konsultacja neurologiczna ──────────────────────────────
  konsultacja_objawy: {
    id: 'konsultacja_objawy',
    type: 'question',
    label: 'Objawy',
    question: 'Jakie główne objawy zgłasza pacjent?',
    options: [
      { label: 'Nie chodzi / porażenie kończyn', nextId: 'konsultacja_czas', data: { sym: 'a' }, variant: 'cito' },
      { label: 'Niedowład — zachowany częściowy ruch', nextId: 'konsultacja_czas', data: { sym: 'b' }, variant: 'urgent' },
      { label: 'Ból kręgosłupa', nextId: 'konsultacja_czas', data: { sym: 'c' } },
      { label: 'Drgawki — nieleczone', nextId: 'konsultacja_czas', data: { sym: 'd' }, variant: 'cito' },
      { label: 'Drgawki — leczone (nowy epizod)', nextId: 'konsultacja_czas', data: { sym: 'e' }, variant: 'urgent' },
      { label: 'Zaburzenia równowagi / ataksja', nextId: 'konsultacja_czas', data: { sym: 'f' }, variant: 'urgent' },
      { label: 'Nagła ślepota lub głuchota', nextId: 'konsultacja_czas', data: { sym: 'g' }, variant: 'urgent' },
      { label: 'Dezorientacja / zmiany zachowania', nextId: 'konsultacja_czas', data: { sym: 'h' } },
      { label: 'Zaburzenia oddawania moczu', nextId: 'konsultacja_czas', data: { sym: 'i' } },
    ],
  },

  konsultacja_czas: {
    id: 'konsultacja_czas',
    type: 'question',
    label: 'Czas trwania',
    question: 'Od kiedy trwają objawy?',
    options: [
      { label: 'Pojawiły się dziś (nagłe)', nextId: 'triage_result', data: { time: '0' }, variant: 'cito' },
      { label: 'Ostatnie 48 godzin', nextId: 'triage_result', data: { time: '1' }, variant: 'urgent' },
      { label: 'Mniej niż 2 tygodnie', nextId: 'triage_result', data: { time: '2' } },
      { label: 'Ponad 2 tygodnie — postępujące', nextId: 'triage_result', data: { time: '3' } },
      { label: 'Ponad 2 tygodnie — stabilne', nextId: 'triage_result', data: { time: '4' } },
    ],
  },

  triage_result: {
    id: 'triage_result',
    type: 'action',
    label: 'Wynik triażu',
    title: 'Wynik triażu neurologicznego',
    dynamic: true,
  },

  // ── Ścieżka 2: Diagnostyka ─────────────────────────────────────────────
  diag_typ: {
    id: 'diag_typ',
    type: 'question',
    label: 'Typ badania',
    question: 'Jakie badanie jest wymagane?',
    options: [
      { label: 'MRI (rezonans) — 1,5h', nextId: 'diag_checklist', data: { diag: 'MRI', duration: '1,5h' } },
      { label: 'TK (tomografia) — 1,5h', nextId: 'diag_checklist', data: { diag: 'TK', duration: '1,5h' } },
      { label: 'EEG — 1,5h', nextId: 'diag_checklist', data: { diag: 'EEG', duration: '1,5h' } },
      { label: 'EMG / ENG — 2h', nextId: 'diag_checklist', data: { diag: 'EMG/ENG', duration: '2h' } },
      { label: 'BAER — 1h', nextId: 'diag_checklist', data: { diag: 'BAER', duration: '1h' } },
      { label: 'Pobranie płynu m-r — 1h', nextId: 'diag_checklist', data: { diag: 'Płyn m-r', duration: '1h' } },
      { label: 'Endoskopia uszu — 2,5h', nextId: 'diag_checklist', data: { diag: 'Endoskopia uszu', duration: '2,5h' } },
      { label: 'Diagnostyka uszu pełna — 4h', nextId: 'diag_checklist', data: { diag: 'Diagnostyka uszu pełna', duration: '4h' } },
    ],
  },

  diag_checklist: {
    id: 'diag_checklist',
    type: 'action',
    label: 'Checklist',
    title: 'Checklist diagnostyczny',
    body: 'Zanim zapiszesz pacjenta, zweryfikuj poniższe punkty:',
    checklist: DIAG_CHECKLIST,
  },

  // ── Ścieżka 3: Zabieg ──────────────────────────────────────────────────
  zabieg_status: {
    id: 'zabieg_status',
    type: 'question',
    label: 'Status pacjenta',
    question: 'Czy pacjent był wcześniej badany w związku z tym problemem?',
    options: [
      { label: 'Tak — zbadany u nas', nextId: 'zabieg_u_nas' },
      { label: 'Skierowanie z innej lecznicy', nextId: 'zabieg_skierowanie_wiek' },
      { label: 'Niezbadany / brak dokumentacji', nextId: 'zabieg_niezbadany' },
    ],
  },

  zabieg_skierowanie_wiek: {
    id: 'zabieg_skierowanie_wiek',
    type: 'question',
    label: 'Wiek skierowania',
    question: 'Jak stare jest skierowanie z innej lecznicy?',
    options: [
      { label: 'Świeże — mniej niż 1 miesiąc', nextId: 'zabieg_checklist' },
      { label: 'Starsze — ponad 1 miesiąc', nextId: 'zabieg_konsultacja_pre' },
    ],
  },

  zabieg_u_nas: {
    id: 'zabieg_u_nas',
    type: 'action',
    label: 'Nasza karta',
    title: 'Pacjent zbadany u nas',
    body: 'Sprawdź kartę pacjenta: czy jest aktualne skierowanie na zabieg i na co dokładnie. Następnie zweryfikuj checklist.',
    checklist: ZABIEG_CHECKLIST,
  },

  zabieg_checklist: {
    id: 'zabieg_checklist',
    type: 'action',
    label: 'Checklist zabiegu',
    title: 'Checklist przed zapisem na zabieg',
    body: 'Skierowanie aktualne. Zweryfikuj poniższe punkty przed potwierdzeniem terminu:',
    checklist: ZABIEG_CHECKLIST,
  },

  zabieg_konsultacja_pre: {
    id: 'zabieg_konsultacja_pre',
    type: 'action',
    label: 'Konsultacja przedzabiegowa',
    title: 'Wymagana konsultacja przedzabiegowa',
    body: 'Skierowanie jest starsze niż 1 miesiąc. Umów pacjenta najpierw na konsultację przedzabiegową u neurologa.',
    checklist: [
      'Sprawdź dostępność neurologa na konsultację przedzabiegową',
      'Poinformuj klienta o konieczności konsultacji przed zabiegiem',
      'Zapytaj o aktualną historię choroby i leki',
    ],
  },

  zabieg_niezbadany: {
    id: 'zabieg_niezbadany',
    type: 'action',
    label: 'Konsultacja wymagana',
    title: 'Pacjent niezbadany — konsultacja obowiązkowa',
    body: 'Pacjent nie posiada dokumentacji. Przed zabiegiem wymagana konsultacja przedzabiegowa.',
    checklist: [
      'Umów na konsultację przedzabiegową u neurologa',
      'Poinformuj o przebiegu i kosztach',
      'Zapytaj czy był badany gdziekolwiek wcześniej',
    ],
  },

  // ── Ścieżka 4: Kontrola ────────────────────────────────────────────────
  kontrola_lekarz: {
    id: 'kontrola_lekarz',
    type: 'question',
    label: 'Preferencja lekarza',
    question: 'Czy klient chce wizytę u konkretnego lekarza?',
    options: [
      { label: 'Tak — konkretny lekarz', nextId: 'kontrola_termin' },
      { label: 'Dowolny neurolog', nextId: 'kontrola_checklist' },
    ],
  },

  kontrola_termin: {
    id: 'kontrola_termin',
    type: 'question',
    label: 'Dostępność terminu',
    question: 'Jaki jest najbliższy wolny termin u tego lekarza?',
    options: [
      { label: 'Dostępny w ciągu 1–2 tygodni', nextId: 'kontrola_checklist' },
      { label: 'Termin bardzo odległy (ponad 2 tygodnie)', nextId: 'kontrola_inny_lekarz' },
    ],
  },

  kontrola_inny_lekarz: {
    id: 'kontrola_inny_lekarz',
    type: 'action',
    label: 'Propozycja innego lekarza',
    title: 'Zaproponuj innego neurologa',
    body: 'Termin u wybranego lekarza jest odległy. Zaproponuj innego neurologa — ten sam standard opieki, lekarze konsultują się wspólnie.',
    checklist: [
      'Poinformować klienta że neurolog X jest niedostępny',
      'Zaproponować innego neurologa z wyjaśnieniem (wspólne konsultacje)',
      ...KONTROLA_CHECKLIST,
    ],
  },

  kontrola_checklist: {
    id: 'kontrola_checklist',
    type: 'action',
    label: 'Checklist kontroli',
    title: 'Checklist wizyty kontrolnej',
    checklist: KONTROLA_CHECKLIST,
  },

  // ── Ścieżka 5: Pogorszenie ─────────────────────────────────────────────
  pogorszenie_karta: {
    id: 'pogorszenie_karta',
    type: 'question',
    label: 'Karta pacjenta',
    question: 'Czy pacjent ma kartę w naszej klinice?',
    options: [
      { label: 'Tak — ma kartę u nas', nextId: 'pogorszenie_zalecenie' },
      { label: 'Nie — brak karty / nowy pacjent', nextId: 'pogorszenie_brak_karty' },
    ],
  },

  pogorszenie_zalecenie: {
    id: 'pogorszenie_zalecenie',
    type: 'question',
    label: 'Zalecenie kontroli',
    question: 'Sprawdź kartę: czy neurolog zalecił kontrolę i czy minął wskazany czas?',
    options: [
      { label: 'Tak — kontrola zalecona i czas minął', nextId: 'pogorszenie_umow' },
      { label: 'Brak zalecenia kontroli w karcie', nextId: 'pogorszenie_memo' },
    ],
  },

  pogorszenie_umow: {
    id: 'pogorszenie_umow',
    type: 'action',
    label: 'Umów kontrolę',
    title: 'Umów wizytę kontrolną',
    body: 'Czas na kontrolę minął. Umów pacjenta na wizytę kontrolną u neurologa prowadzącego.',
    checklist: KONTROLA_CHECKLIST,
  },

  pogorszenie_memo: {
    id: 'pogorszenie_memo',
    type: 'action',
    label: 'Memo do neurologa',
    title: 'Dodaj zadanie w Skrzynce',
    body: 'Brak zalecenia kontroli w karcie. Dodaj zadanie dla neurologa prowadzącego: "Klient pyta o pogorszenie — telefon czy wizyta?"',
    checklist: [
      'Dodaj zadanie w Skrzynce dla neurologa prowadzącego (typ: Oddzwonienie)',
      'Poinformuj klienta, że lekarz się skontaktuje',
      'Odnotuj zgłaszane objawy pogorszenia',
    ],
  },

  pogorszenie_brak_karty: {
    id: 'pogorszenie_brak_karty',
    type: 'question',
    label: 'Kierunek',
    question: 'Brak karty. Co zaproponować klientowi?',
    options: [
      { label: 'Wyraźne objawy neurologiczne → diagnostyka', nextId: 'diag_typ' },
      { label: 'Objawy niecharakterystyczne → konsultacja', nextId: 'konsultacja_objawy' },
    ],
  },
}
