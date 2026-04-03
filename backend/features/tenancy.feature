Feature: Clinic network tenancy (API)
  Multi-clinic access is enforced via helpers such as accessible_clinic_ids and
  clinic_id_for_mutation. These scenarios document behaviour at the HTTP layer.

  Scenario: Unauthenticated me returns 401
    When I request me without authentication
    Then the response status is 401

  Scenario: Network admin me includes network and role
    Given a network with two clinics each having one vet
    And a network admin for that network without a clinic membership
    When the network admin requests me
    Then the response status is 200
    And the me payload has role "network_admin"
    And the me payload includes a network reference

  Scenario: Clinic vet me includes clinic
    Given a standalone clinic with one vet
    When the standalone vet requests me
    Then the response status is 200
    And the me payload has role "doctor"
    And the me payload includes the user clinic id

  Scenario: Network admin sees vets from all clinics in the network
    Given a network with two clinics each having one vet
    And a network admin for that network without a clinic membership
    When the network admin lists vets
    Then the response status is 200
    And the vets list includes usernames "behave_vet_clinic_a" and "behave_vet_clinic_b"

  Scenario: Vet only sees peers in their own clinic
    Given a network with two clinics each having one vet
    When the vet from clinic A lists vets
    Then the response status is 200
    And the vets list does not include username "behave_vet_clinic_b"
