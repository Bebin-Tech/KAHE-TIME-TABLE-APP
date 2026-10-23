import React, { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import { Records } from "./Records";
import { Timetables } from "./Timetable";
import { Activity } from "./Activity";
import { Dashboard } from "./Dashboard";
import { Requests } from "./Requests";
import { Sidebar } from "./Sidebar";
import { moduleGroups } from "./navigation";
import { csrf } from "./api";
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
  const [page, setPage] = useState(() => location.hash.slice(1) || "dashboard");
  const [menuOpen, setMenuOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [actionError, setActionError] = useState("");
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  useEffect(() => {
    const media = matchMedia("(min-width: 901px)");
    const resize = () => {
      if (media.matches) setMenuOpen(false);
    };
    media.addEventListener("change", resize);
    return () => media.removeEventListener("change", resize);
  }, []);
  useEffect(() => {
    const back = () => {
      if (confirmNavigation()) setPage(location.hash.slice(1) || "dashboard");
      else history.pushState(null, "", "#" + page);
    };
    window.addEventListener("popstate", back);
    return () => window.removeEventListener("popstate", back);
  }, [page]);
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
  const groups = moduleGroups(user.institution_admin, user.role);
  const current = groups
    .flatMap((group) => group.items)
    .find(([id]) => id === page);
  const navigate = (target: string) => {
    if (target !== page && !confirmNavigation()) return;
    setPage(target);
    history.pushState(null, "", "#" + target);
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  const logout = async () => {
    if (!confirmNavigation()) return;
    setSigningOut(true);
    setActionError("");
    try {
      const response = await fetch("/accounts/logout/", {
        method: "POST",
        headers: { "X-CSRFToken": csrf() },
      });
      if (!response.ok) throw Error("Sign out failed. Please try again.");
      location.assign("/accounts/login/");
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "Sign out failed.",
      );
      setSigningOut(false);
    }
  };
  let content: React.ReactNode;
  if (!current)
    content = (
      <section>
        <h1>Module unavailable</h1>
        <p>This module is not available for your account.</p>
        <button onClick={() => navigate("dashboard")}>Go to dashboard</button>
      </section>
    );
  else if (page === "dashboard") content = <Dashboard role={user.role} />;
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
      <a
        className="skip-link"
        href="#workspace-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("workspace-content")?.focus();
        }}
      >
        Skip to content
      </a>
      <Sidebar
        groups={groups}
        page={page}
        open={menuOpen}
        close={closeMenu}
        navigate={navigate}
        username={user.username}
        role={user.role}
        confirmLeave={confirmNavigation}
        logout={logout}
        signingOut={signingOut}
      />
      <main id="workspace-content" tabIndex={-1} inert={menuOpen}>
        <header className="workspace-header">
          <div className="header-location">
            <button
              className="menu-toggle secondary"
              onClick={() => setMenuOpen(true)}
              aria-expanded={menuOpen}
              aria-controls="workspace-navigation"
              aria-label="Open navigation"
            >
              ☰
            </button>
            <div>
              <small>INSTITUTION WORKSPACE</small>
              <strong>{current?.[1] || "Module unavailable"}</strong>
            </div>
          </div>
          <span className="role-chip">
            {user.role.toLowerCase()} · {user.username}
          </span>
        </header>
        {actionError && (
          <p className="error" role="alert">
            {actionError}
          </p>
        )}
        <div className="page-content" key={page}>
          {content}
        </div>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
