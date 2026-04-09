namespace ElzabBridge.Services;

public sealed class BridgeOptions
{
    public const string SectionName = "Bridge";

    public string AgentName { get; set; } = "ElzabBridge";
    public bool RequireBearerToken { get; set; } = false;
    public string BearerToken { get; set; } = string.Empty;
    public VetoOptions Veto { get; set; } = new();
}

public sealed class VetoOptions
{
    public string BaseUrl { get; set; } = "http://localhost:8000";
    public string FiscalCallbackPath { get; set; } = "/api/billing/fiscal/callback/";
    public string SharedSecret { get; set; } = "CHANGE_ME";
}
