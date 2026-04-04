Feature: Inventory barcode (wholesale EAN/GTIN)
  Staff can store a package barcode on inventory lines and resolve it for stock-in workflows.

  Scenario: Resolve barcode requires authentication
    When I request inventory resolve_barcode without auth
    Then the response status is 401

  Scenario: Vet creates item with barcode and resolves it
    Given a clinic with a vet for inventory
    When the vet creates an inventory item with barcode "5901234123457"
    Then the response status is 201
    When the vet resolves barcode "5901234123457"
    Then the response status is 200
    And the resolved item has barcode "5901234123457"

  Scenario: Duplicate barcode in same clinic is rejected
    Given a clinic with a vet for inventory
    When the vet posts inventory line barcode "5901234123457" sku "SKU_ONE"
    Then the response status is 201
    When the vet posts inventory line barcode "5901234123457" sku "SKU_TWO"
    Then the response status is 400
