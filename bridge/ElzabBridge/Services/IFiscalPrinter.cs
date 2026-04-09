using ElzabBridge.Models;

namespace ElzabBridge.Services;

public interface IFiscalPrinter
{
    Task<FiscalPrintResult> PrintReceiptAsync(
        FiscalPrintReceiptRequest request,
        CancellationToken cancellationToken
    );
}

public sealed record FiscalPrintResult(
    bool Success,
    string? ReceiptNumber,
    decimal? ReceiptTotalGross,
    string? DeviceSerial,
    string? ErrorCode,
    string? ErrorMessage,
    string? ErrorRaw
);
