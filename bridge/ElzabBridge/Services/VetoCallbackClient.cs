using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using ElzabBridge.Models;
using Microsoft.Extensions.Options;

namespace ElzabBridge.Services;

public sealed class VetoCallbackClient
{
    private readonly HttpClient _httpClient;
    private readonly BridgeOptions _options;
    private readonly JsonSerializerOptions _jsonOptions =
        new(JsonSerializerDefaults.Web)
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull
        };

    public VetoCallbackClient(HttpClient httpClient, IOptions<BridgeOptions> options)
    {
        _httpClient = httpClient;
        _options = options.Value;
    }

    public async Task PostFiscalCallbackAsync(FiscalCallbackPayload payload, CancellationToken cancellationToken)
    {
        var json = JsonSerializer.Serialize(payload, _jsonOptions);
        using var req = new HttpRequestMessage(HttpMethod.Post, _options.Veto.FiscalCallbackPath)
        {
            Content = new StringContent(json, Encoding.UTF8, "application/json"),
        };

        req.Headers.Add("X-Veto-Agent", _options.AgentName);
        req.Headers.Add("X-Veto-Signature", ComputeHmacSha256Base64(json, _options.Veto.SharedSecret));

        using var resp = await _httpClient.SendAsync(req, cancellationToken);
        resp.EnsureSuccessStatusCode();
    }

    private static string ComputeHmacSha256Base64(string body, string secret)
    {
        var key = Encoding.UTF8.GetBytes(secret);
        var bytes = Encoding.UTF8.GetBytes(body);
        using var hmac = new HMACSHA256(key);
        return Convert.ToBase64String(hmac.ComputeHash(bytes));
    }
}
