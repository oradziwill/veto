import { useEffect, useMemo, useState } from "react";
import { deviceManagementAPI } from "../../services/api";

const statusColor = {
  active: "#16a34a",
  confirmed: "#2563eb",
  discovered: "#f59e0b",
  offline: "#6b7280",
};

const chipStyle = (color) => ({
  display: "inline-block",
  borderRadius: "999px",
  padding: "2px 10px",
  fontSize: "12px",
  fontWeight: 700,
  color: "white",
  background: color,
});

export default function IntegratedDevicesTab() {
  const [devices, setDevices] = useState([]);
  const [events, setEvents] = useState([]);
  const [receipts, setReceipts] = useState([]);
  const [typeFilter, setTypeFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [dRes, eRes, rRes] = await Promise.all([
        deviceManagementAPI.listDevices(),
        deviceManagementAPI.listEvents({ limit: 20 }),
        deviceManagementAPI.listFiscalReceipts({ limit: 20 }),
      ]);
      setDevices(dRes.data?.results || dRes.data || []);
      setEvents(eRes.data?.results || eRes.data || []);
      setReceipts(rRes.data?.results || rRes.data || []);
    } catch (err) {
      setError(err?.response?.data?.detail || "Nie udało się pobrać danych urządzeń.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const filteredDevices = useMemo(() => {
    if (typeFilter === "all") return devices;
    return devices.filter((d) => d.device_type === typeFilter);
  }, [devices, typeFilter]);

  const labCount = devices.filter((d) => d.device_type === "lab").length;
  const fiscalCount = devices.filter((d) => d.device_type === "fiscal").length;
  const offlineCount = devices.filter((d) => d.lifecycle_state === "offline").length;

  return (
    <div style={{ display: "grid", gap: "16px" }}>
      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <button className="btn-secondary" onClick={load}>Odśwież</button>
        <button className={`btn-secondary ${typeFilter === "all" ? "active" : ""}`} onClick={() => setTypeFilter("all")}>
          Wszystkie
        </button>
        <button className={`btn-secondary ${typeFilter === "lab" ? "active" : ""}`} onClick={() => setTypeFilter("lab")}>
          LAB
        </button>
        <button className={`btn-secondary ${typeFilter === "fiscal" ? "active" : ""}`} onClick={() => setTypeFilter("fiscal")}>
          Fiskalne
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px" }}>
        {[["Urządzenia", devices.length], ["LAB", labCount], ["FISKALNE", fiscalCount], ["Offline", offlineCount]].map(
          ([label, value]) => (
            <div
              key={label}
              style={{
                background: "white",
                border: "1px solid #e2e8f0",
                borderRadius: "12px",
                padding: "12px",
              }}
            >
              <strong>{label}</strong>
              <div style={{ fontSize: "22px", fontWeight: 700 }}>{value}</div>
            </div>
          )
        )}
      </div>

      {loading ? <div>Ładowanie...</div> : null}
      {error ? <div style={{ color: "#dc2626" }}>{error}</div> : null}

      <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "12px", padding: "12px" }}>
        <h3>Integrated Devices</h3>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th>Nazwa</th>
                <th>Typ</th>
                <th>Vendor / Model</th>
                <th>Połączenie</th>
                <th>Status</th>
                <th>Capabilities</th>
              </tr>
            </thead>
            <tbody>
              {filteredDevices.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>{d.device_type?.toUpperCase()}</td>
                  <td>{[d.vendor, d.model].filter(Boolean).join(" / ") || "-"}</td>
                  <td>{d.connection_type || "-"}</td>
                  <td>
                    <span style={chipStyle(statusColor[d.lifecycle_state] || "#6b7280")}>{d.lifecycle_state}</span>
                  </td>
                  <td>{(d.capabilities || []).map((c) => c.code).join(", ") || "-"}</td>
                </tr>
              ))}
              {filteredDevices.length === 0 ? (
                <tr><td colSpan={6}>Brak urządzeń.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "12px", padding: "12px" }}>
        <h3>Recent Device Events</h3>
        <div style={{ display: "grid", gap: "8px" }}>
          {events.slice(0, 10).map((e) => (
            <div key={e.id} style={{ padding: "8px", border: "1px solid #e2e8f0", borderRadius: "8px" }}>
              <strong>{e.severity?.toUpperCase()}</strong> [{e.event_type}] {e.message || "-"}
            </div>
          ))}
          {events.length === 0 ? <div>Brak eventów.</div> : null}
        </div>
      </div>

      <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "12px", padding: "12px" }}>
        <h3>Fiscal Queue & Failures</h3>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Total</th>
                <th>NIP</th>
                <th>Akcja</th>
              </tr>
            </thead>
            <tbody>
              {receipts.slice(0, 20).map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{r.status}</td>
                  <td>{r.gross_total} {r.currency}</td>
                  <td>{r.buyer_tax_id || "-"}</td>
                  <td>
                    {(r.status === "failed" || r.status === "unknown") ? (
                      <button className="btn-secondary" onClick={() => deviceManagementAPI.retryFiscalReceipt(r.id).then(load)}>
                        Retry
                      </button>
                    ) : "-"}
                  </td>
                </tr>
              ))}
              {receipts.length === 0 ? (
                <tr><td colSpan={5}>Brak paragonów w kolejce.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
