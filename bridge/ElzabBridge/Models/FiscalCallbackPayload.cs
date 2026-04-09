namespace ElzabBridge.Models;

public sealed record FiscalCallbackPayload(
    Guid JobId,
    string Status,
    DateTimeOffset PrintedAt,
    string? ReceiptNumber,
    decimal? ReceiptTotalGross,
    string? DeviceSerial,
    FiscalCallbackError? Error
);

public sealed record FiscalCallbackError(
    string Code,
    string Message,
    string? Raw
);
