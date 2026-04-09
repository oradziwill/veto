using ElzabBridge.Models;

namespace ElzabBridge.Services;

/// <summary>
/// Placeholder implementation until ELZAB SDK/protocol is added.
/// Replace with real device calls (USB/COM/LAN) per vendor documentation.
/// </summary>
public sealed class ElzabFiscalPrinterStub : IFiscalPrinter
{
    public Task<FiscalPrintResult> PrintReceiptAsync(
        FiscalPrintReceiptRequest request,
        CancellationToken cancellationToken
    )
    {
        // Simulate a successful print for wiring tests.
        var receiptNumber = $"SIM-{DateTimeOffset.UtcNow:yyyyMMddHHmmss}-{request.JobId.ToString()[..8]}";
        return Task.FromResult(
            new FiscalPrintResult(
                Success: true,
                ReceiptNumber: receiptNumber,
                ReceiptTotalGross: request.Totals.AmountGross,
                DeviceSerial: "ELZAB-SIMULATOR",
                ErrorCode: null,
                ErrorMessage: null,
                ErrorRaw: null
            )
        );
    }
}
