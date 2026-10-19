import React, { useEffect, useState } from "react";
import { api } from "./api";
type Row = {
  id: number;
  faculty__user__username: string;
  kind: string;
  message: string;
  status: string;
  response: string;
  starts_on: string;
  ends_on: string;
  day: number;
  starts_at: string;
  ends_at: string;
};
export function Requests({ faculty }: { faculty: boolean }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [manager, setManager] = useState(false);
  const [kind, setKind] = useState("CONFLICT");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = () =>
    api("/api/requests/")
      .then((r) => {
        setRows(r.rows);
        setManager(r.manager);
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    setBusy(true);
    setError("");
    try {
      await api("/api/requests/", "POST", data);
      form.reset();
      setKind("CONFLICT");
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function review(row: Row, status: string) {
    const response = prompt(
      status === "REJECTED"
        ? "Reason for rejection:"
        : "Review comment (optional):",
    );
    if (response === null) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/requests/${row.id}/`, "POST", { status, response });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h1>Faculty requests and conflicts</h1>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {faculty && (
        <section>
          <h2>Submit a request</h2>
          <form onSubmit={submit}>
            <label>
              Request type
              <select
                name="kind"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
              >
                <option value="CONFLICT">Scheduling conflict</option>
                <option value="LEAVE">Leave</option>
                <option value="UNAVAILABLE">Unavailable weekly interval</option>
              </select>
            </label>
            <label>
              Details
              <input name="message" required maxLength={2000} />
            </label>
            {kind === "LEAVE" && (
              <div className="filters">
                <label>
                  Start date
                  <input type="date" name="starts_on" required />
                </label>
                <label>
                  End date
                  <input type="date" name="ends_on" required />
                </label>
              </div>
            )}
            {kind === "UNAVAILABLE" && (
              <div className="filters">
                <label>
                  Day
                  <select name="day">
                    {[
                      "Monday",
                      "Tuesday",
                      "Wednesday",
                      "Thursday",
                      "Friday",
                      "Saturday",
                      "Sunday",
                    ].map((d, i) => (
                      <option value={i} key={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Starts
                  <input type="time" name="starts_at" required />
                </label>
                <label>
                  Ends
                  <input type="time" name="ends_at" required />
                </label>
              </div>
            )}
            <button disabled={busy}>Submit request</button>
          </form>
        </section>
      )}
      <section>
        <h2>{manager ? "Department requests" : "Your requests"}</h2>
        {rows.map((r) => (
          <article className="request" key={r.id}>
            <h3>
              {r.kind} · {r.status}
            </h3>
            <p>
              {r.faculty__user__username} · {r.message}
            </p>
            <p>
              {r.starts_on} {r.ends_on} {r.starts_at} {r.ends_at}
            </p>
            <p>{r.response}</p>
            {manager && r.status === "PENDING" && (
              <div className="actions">
                <button disabled={busy} onClick={() => review(r, "APPROVED")}>
                  Approve
                </button>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => review(r, "REJECTED")}
                >
                  Reject
                </button>
              </div>
            )}
          </article>
        ))}
        {!rows.length && <p>No requests yet.</p>}
      </section>
    </>
  );
}
