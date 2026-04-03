Feature: Drug catalog (vademecum) API
  Staff can search the global catalog and doctors can add manual products.

  Scenario: Search requires authentication
    When I request drug catalog search without auth
    Then the response status is 401

  Scenario: Doctor can create a manual product and find it in search
    Given a clinic with a doctor and a receptionist
    When the doctor creates a manual reference product "Behave Test Drug"
    Then the response status is 201
    When the doctor searches the catalog for "Behave Test"
    Then the response status is 200
    And the search results contain "Behave Test Drug"

  Scenario: Receptionist cannot create manual catalog products via API
    Given a clinic with a doctor and a receptionist
    When the receptionist creates a manual reference product "Should Fail"
    Then the response status is 403
