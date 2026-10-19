import React, { useEffect, useState } from "react";
import { api, csrf } from "./api";
type Data = {
  institution: string;
  date: string;
  timezone: string;
  counts: Record<string, number>;
  unread_notifications: number;
  today: {
    section: string;
    subject: string;
    faculty: string;
    room: string;
    starts_at: string;
    duration: number;
  }[];
};
export function Dashboard({ role }: { role: string }) {
  const [data, setData] = useState<Data>();
  const [error, setError] = useState("");
  useEffect(() => {
    api("/api/dashboard/")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);
  if (error)
    return (
      <p role="alert" className="error">
        {error}
      </p>
    );
  if (!data) return <p aria-busy="true">Loading dashboard…</p>;
  return (
    <>
      <div className="titlebar">
        <div>
          <small>{data.institution}</small>
          <h1>{role.toLowerCase()} dashboard</h1>
          <p>
            {data.date} · {data.timezone}
          </p>
        </div>
        <form action="/accounts/logout/" method="post">
          <input type="hidden" name="csrfmiddlewaretoken" value={csrf()} />
          <button className="secondary">Sign out</button>
        </form>
      </div>
      <div className="metrics">
        {Object.entries(data.counts).map(([status, count]) => (
          <section key={status}>
            <small>{status}</small>
            <h2>{count}</h2>
            <p>Timetable versions</p>
          </section>
        ))}
        <section>
          <small>NOTIFICATIONS</small>
          <h2>{data.unread_notifications}</h2>
          <p>Unread announcements</p>
        </section>
      </div>
      <section>
        <h2>Today's schedule</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {[
                  "Time",
                  "Section",
                  "Subject",
                  "Faculty",
                  "Room",
                  "Periods",
                ].map((v) => (
                  <th key={v}>{v}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.today.map((r, i) => (
                <tr key={i}>
                  <td>{r.starts_at.slice(0, 5)}</td>
                  <td>{r.section}</td>
                  <td>{r.subject}</td>
                  <td>{r.faculty}</td>
                  <td>{r.room}</td>
                  <td>{r.duration}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!data.today.length && <p>No published classes for today.</p>}
      </section>
    </>
  );
}
