using ElzabBridge.Models;
using ElzabBridge.Services;
using Microsoft.AspNetCore.Http.Json;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);

builder.Services.Configure<JsonOptions>(o =>
{
    o.SerializerOptions.PropertyNamingPolicy = System.Text.Json.JsonNamingPolicy.CamelCase;
    o.SerializerOptions.DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull;
});

builder.Services.AddOptions<BridgeOptions>()
    .Bind(builder.Configuration.GetSection(BridgeOptions.SectionName))
    .Validate(o => !string.IsNullOrWhiteSpace(o.Veto.BaseUrl), "Bridge:Veto:BaseUrl is required")
    .Validate(o => !string.IsNullOrWhiteSpace(o.Veto.FiscalCallbackPath), "Bridge:Veto:FiscalCallbackPath is required")
    .Validate(o => !string.IsNullOrWhiteSpace(o.Veto.SharedSecret), "Bridge:Veto:SharedSecret is required")
    .ValidateOnStart();

builder.Services.AddSingleton<IFiscalJobQueue, FiscalJobQueue>();

// Phase 1: stub until ELZAB SDK is provided
builder.Services.AddSingleton<IFiscalPrinter, ElzabFiscalPrinterStub>();

builder.Services.AddHttpClient<VetoCallbackClient>((sp, client) =>
{
    var opts = sp.GetRequiredService<IOptions<BridgeOptions>>().Value;
    client.BaseAddress = new Uri(opts.Veto.BaseUrl.TrimEnd('/'));
    client.Timeout = TimeSpan.FromSeconds(10);
});

builder.Services.AddHostedService<FiscalWorker>();

builder.Host.UseWindowsService();

var app = builder.Build();

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.MapPost("/api/v1/fiscal/print-receipt", async (
    FiscalPrintReceiptRequest request,
    IFiscalJobQueue queue,
    IOptions<BridgeOptions> options,
    HttpContext httpContext,
    CancellationToken ct
) =>
{
    var opts = options.Value;
    if (opts.RequireBearerToken)
    {
        if (!httpContext.Request.Headers.TryGetValue("Authorization", out var auth) ||
            auth.Count == 0 ||
            auth[0] != $"Bearer {opts.BearerToken}")
        {
            return Results.Unauthorized();
        }
    }

    if (request.JobId == Guid.Empty)
        return Results.BadRequest(new { error = "jobId is required" });
    if (request.Lines is null || request.Lines.Length == 0)
        return Results.BadRequest(new { error = "lines must be non-empty" });

    await queue.EnqueueAsync(request, ct);
    return Results.Accepted(value: new { jobId = request.JobId, status = "queued" });
});

app.Run();
