import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import { Records } from "./Records";
import { Timetables } from "./Timetable";
import { Activity } from "./Activity";
import { Dashboard } from "./Dashboard";
import { Requests } from "./Requests";
type Session = {
  username: string;
  role: string;
  institution_admin: boolean;
  timezone: string;
};
function confirmNavigation() {
  return (
    !document.querySelector('[data-unsaved="true"]') ||
    confirm("Discard unsaved timetable changes?")
  );
}
function App() {
  const [user, setUser] = useState<Session>();
  const [error, setError] = useState("");
  const [page, setPage] = useState("dashboard");
  useEffect(() => {
    fetch("/api/session/")
      .then((r) => {
        if (!r.ok || r.redirected) throw Error("Please sign in again.");
        return r.json();
      })
      .then(setUser)
      .catch((e) => setError(e.message));
  }, []);
  if (error)
    return (
      <main role="alert">
        {error} <a href="/accounts/login/">Sign in</a>
      </main>
    );
  if (!user) return <main aria-busy="true">Loading your account…</main>;
  const editor = user.institution_admin || user.role === "HOD";
  const resources = user.institution_admin
    ? [
        "users",
        "departments",
        "department-rules",
        "programs",
        "years",
        "semesters",
        "sections",
        "subjects",
        "faculty",
        "students",
        "department-access",
        "rooms",
        "room-availability",
        "periods",
        "settings",
        "assignments",
        "availability",
        "leave",
      ]
    : [
        "department-rules",
        "subjects",
        "faculty",
        "assignments",
        "availability",
        "leave",
        "rooms",
        "periods",
      ];
  const navigate = (target: string) => {
    if (confirmNavigation()) setPage(target);
  };
  const nav = (target: string) => (
    <button
      className={"nav " + (page === target ? "selected" : "")}
      key={target}
      onClick={() => navigate(target)}
    >
      {target.replaceAll("-", " ")}
    </button>
  );
  let content: React.ReactNode;
  if (page === "dashboard") content = <Dashboard role={user.role} />;
  else if (page === "timetables")
    content = <Timetables editor={editor} admin={user.institution_admin} />;
  else if (page === "requests")
    content = (
      <Requests faculty={user.role === "FACULTY" || user.role === "HOD"} />
    );
  else if (["notifications", "reports", "audit", "conflicts"].includes(page))
    content = <Activity key={page} page={page} timezone={user.timezone} />;
  else content = <Records key={page} resource={page} />;
  return (
    <div className="layout">
      <aside>
        <strong>CTMS</strong>
        <p>
          College Timetable
          <br />
          Management System
        </p>
        <nav>
          {[
            "dashboard",
            "timetables",
            "notifications",
            "reports",
            ...(user.role !== "STUDENT" || user.institution_admin
              ? ["requests"]
              : []),
            ...(user.institution_admin ? ["audit"] : []),
          ].map(nav)}
          {editor && <small className="nav-heading">ACADEMIC MANAGEMENT</small>}
          {editor && nav("conflicts")}
          {editor && resources.map(nav)}
          <a
            href="/accounts/password_change/"
            onClick={(e) => {
              if (!confirmNavigation()) e.preventDefault();
            }}
          >
            Change password
          </a>
        </nav>
      </aside>
      <main>
        <header>
          <span>INSTITUTION WORKSPACE</span>
          <span>
            {user.username} · {user.role}
          </span>
        </header>
        {content}
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
