import React, { useEffect, useState } from "react";
import { api } from "./api";
export function Activity({
  page,
  timezone,
}: {
  page: string;
  timezone: string;
}) {
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () =>
    api(`/api/${page}/`)
      .then((result) =>
        setRows(result.notifications || result.logs || result.rows || []),
      )
      .catch((e) => setError(e.message));
  useEffect(() => {
    setRows([]);
    setError("");
    load();
  }, [page]);
  async function markRead() {
    setBusy(true);
    try {
      await api("/api/notifications/", "POST", {});
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="titlebar">
        <h1>{page}</h1>
        {page === "notifications" && (
          <button disabled={busy} onClick={markRead}>
            Mark all as read
          </button>
        )}
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {page === "reports" && (
        <section>
          <h2>Authorized reports</h2>
          <p>Reports contain only published schedules within your access.</p>
          <div className="toolbar">
            <a href="/api/exports/pdf/">Download timetable PDF</a>
            <a href="/api/exports/xlsx/">Download Excel report</a>
            <button className="secondary" onClick={() => window.print()}>
              Print
            </button>
          </div>
        </section>
      )}
      <section>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {Object.keys(rows[0] || {}).map((key) => (
                  <th key={key}>{key.replaceAll("_", " ")}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {Object.entries(row).map(([key, value]) => (
                    <td key={key}>
                      {typeof value === "object"
                        ? JSON.stringify(value)
                        : key.endsWith("_at") && typeof value === "string"
                          ? new Date(value).toLocaleString(undefined, {
                              timeZone: timezone,
                            })
                          : String(value ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!rows.length && <p>No records available.</p>}
      </section>
    </>
  );
}
