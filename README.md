Superuser pass:
Login: test
email: test@veto.pl
password: test

Clinic
 ├── Users (vets/staff)
 ├── Patients (pets)
 │     └── owned by Client
 └── ClientClinic (membership)
        └── Client (global person)
setup pre commit: pip install pre-commit
pre-commit install
