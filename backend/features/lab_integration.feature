Feature: Lab instrument ingestion API
  Inbound JSON payloads are idempotent and materialize result components on lab order lines.

  Scenario: Ingest with barcode idempotency
    Given a clinic lab ingest setup with three tests and barcode "INGEST-BC-1"
    When I POST the same lab ingest payload twice
    Then the second response status is 200
    And only one lab ingestion envelope exists for that idempotency pattern
    And the lab order has 3 result components

  Scenario: Unmatched observation can be resolved to a line
    Given a clinic lab ingest setup with one test and barcode "INGEST-BC-2"
    When I ingest observations without identifiers
    Then the observation has match_status "unmatched"
    When the doctor resolves the observation to the order line
    Then the response status is 200
    And the lab order line has a result component
