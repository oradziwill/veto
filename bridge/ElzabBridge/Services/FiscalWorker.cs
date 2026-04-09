using ElzabBridge.Models;
using Microsoft.Extensions.Options;

namespace ElzabBridge.Services;

public sealed class FiscalWorker : BackgroundService
{
    private readonly IFiscalJobQueue _queue;
    private readonly IFiscalPrinter _printer;
    private readonly VetoCallbackClient _callbackClient;
    private readonly BridgeOptions _options;
    private readonly ILogger<FiscalWorker> _logger;

    public FiscalWorker(
        IFiscalJobQueue queue,
        IFiscalPrinter printer,
        VetoCallbackClient callbackClient,
        IOptions<BridgeOptions> options,
        ILogger<FiscalWorker> logger
    )
    {
        _queue = queue;
        _printer = printer;
        _callbackClient = callbackClient;
        _options = options.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Starting {AgentName} worker loop", _options.AgentName);

        await foreach (var job in _queue.DequeueAllAsync(stoppingToken))
        {
            try
            {
                _logger.LogInformation(
                    "Printing receipt jobId={JobId} clinicId={ClinicId} invoiceId={InvoiceId} paymentId={PaymentId}",
                    job.JobId,
                    job.ClinicId,
                    job.InvoiceId,
                    job.PaymentId
                );

                var result = await _printer.PrintReceiptAsync(job, stoppingToken);
                var payload = BuildCallbackPayload(job, result);

                await _callbackClient.PostFiscalCallbackAsync(payload, stoppingToken);
                _logger.LogInformation("Callback posted for jobId={JobId} status={Status}", job.JobId, payload.Status);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unhandled error while processing fiscal job");
            }
        }
    }

    private static FiscalCallbackPayload BuildCallbackPayload(FiscalPrintReceiptRequest job, FiscalPrintResult result)
    {
        if (result.Success)
        {
            return new FiscalCallbackPayload(
                JobId: job.JobId,
                Status: "printed",
                PrintedAt: DateTimeOffset.UtcNow,
                ReceiptNumber: result.ReceiptNumber,
                ReceiptTotalGross: result.ReceiptTotalGross,
                DeviceSerial: result.DeviceSerial,
                Error: null
            );
        }

        return new FiscalCallbackPayload(
            JobId: job.JobId,
            Status: "failed",
            PrintedAt: DateTimeOffset.UtcNow,
            ReceiptNumber: null,
            ReceiptTotalGross: null,
            DeviceSerial: result.DeviceSerial,
            Error: new FiscalCallbackError(
                Code: result.ErrorCode ?? "unknown_error",
                Message: result.ErrorMessage ?? "Unknown fiscal printer error",
                Raw: result.ErrorRaw
            )
        );
    }
}
