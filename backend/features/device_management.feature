Feature: Device management and fiscal printing workflow
  Cloud backend coordinates local agent commands for fiscal printing.

  Scenario: Agent executes fiscal print command successfully
    Given a clinic device management setup with one fiscal device
    When the agent registers itself
    And an admin creates a fiscal receipt
    Then receipt status is "sent_to_agent"
    And one pending fiscal_print command exists for this receipt
    When the agent pulls pending commands
    Then the pulled command type is "fiscal_print"
    When the agent reports command success with fiscal number "MOCK-ABC123"
    Then receipt status is "printed"
    And receipt has 1 print attempt with status "succeeded"

  Scenario: Failed receipt can be retried without changing idempotency key
    Given a clinic device management setup with one fiscal device
    When the agent registers itself
    And an admin creates a fiscal receipt
    And the agent pulls pending commands
    When the agent reports command failure "paper_out"
    Then receipt status is "failed"
    When admin retries the fiscal receipt
    Then receipt status is "sent_to_agent"
    And retry created a new pending fiscal_print command
    And receipt idempotency key stays the same
