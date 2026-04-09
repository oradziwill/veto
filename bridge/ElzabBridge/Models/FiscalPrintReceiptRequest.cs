namespace ElzabBridge.Models;

public sealed record FiscalPrintReceiptRequest(
    Guid JobId,
    int ClinicId,
    int InvoiceId,
    int? PaymentId,
    string Currency,
    string PaymentForm,
    FiscalReceiptLine[] Lines,
    FiscalReceiptTotals Totals,
    RequestedBy RequestedBy,
    string? IdempotencyKey
);

public sealed record FiscalReceiptLine(
    string Name,
    decimal Quantity,
    decimal UnitPriceGross,
    decimal VatRate
);

public sealed record FiscalReceiptTotals(decimal AmountGross);

public sealed record RequestedBy(int UserId, string Email);
