import { useEffect, useRef, useState } from "react";
import type { ModuleGroup } from "./navigation";

export function ModuleIcon({ name }: { name: string }) {
  const path =
    name === "dashboard"
      ? "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z"
      : name === "timetables" || name === "periods"
        ? "M4 5h16v16H4z M8 3v4 M16 3v4 M4 11h16 M8 15h2 M14 15h2"
        : ["faculty", "students", "users", "department-access"].includes(name)
          ? "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M13 4a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-4 M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8"
          : name === "notifications"
            ? "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4"
            : name === "settings"
              ? "M4 7h16 M4 17h16 M8 4v6 M16 14v6"
              : name === "conflicts"
                ? "M12 3 2 21h20L12 3z M12 9v5 M12 17v1"
                : "M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8 M8 16h6";
  return (
    <svg
      className="module-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}
export function Sidebar({
  groups,
  page,
  open,
  close,
  navigate,
  username,
  role,
  confirmLeave,
  logout,
  signingOut,
}: {
  groups: ModuleGroup[];
  page: string;
  open: boolean;
  close: () => void;
  navigate: (target: string) => void;
  username: string;
  role: string;
  confirmLeave: () => boolean;
  logout: () => void;
  signingOut: boolean;
}) {
  const [search, setSearch] = useState("");
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // Flush the drawer's visibility change before moving keyboard focus.
    panel.current?.getBoundingClientRect();
    panel.current?.querySelector<HTMLElement>("button")?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
      if (event.key !== "Tab") return;
      const elements = Array.from(
        panel.current?.querySelectorAll<HTMLElement>(
          "button,input,a[href],summary",
        ) || [],
      ).filter(
        (el) => el.getClientRects().length > 0 && !el.hasAttribute("disabled"),
      );
      const first = elements[0],
        last = elements.at(-1);
      if (!panel.current?.contains(document.activeElement)) {
        event.preventDefault();
        first?.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.body.style.overflow = oldOverflow;
      document.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, [open, close]);
  const query = search.trim().toLowerCase();
  const filtered = groups
    .map((group) => ({
      ...group,
      items: group.items.filter(([, label]) =>
        label.toLowerCase().includes(query),
      ),
    }))
    .filter((group) => group.items.length);
  return (
    <>
      {open && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={close}
          tabIndex={-1}
        />
      )}
      <aside
        id="workspace-navigation"
        ref={panel}
        className={"workspace-sidebar " + (open ? "is-open" : "")}
        aria-label="Workspace navigation"
        role={open ? "dialog" : undefined}
        aria-modal={open ? true : undefined}
      >
        <div className="sidebar-brand">
          <span className="brand-mark">
            <ModuleIcon name="timetables" />
          </span>
          <div>
            <strong>CTMS</strong>
            <span>College workspace</span>
          </div>
          <button
            className="mobile-close secondary"
            onClick={close}
            aria-label="Close navigation"
          >
            ×
          </button>
        </div>
        <label className="module-search">
          <span>Find a module</span>
          <input
            type="search"
            placeholder="Search modules…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <nav aria-label="Modules">
          {filtered.map((group) => (
            <details
              className="nav-group"
              key={group.title}
              open={!!query || !collapsed.includes(group.title)}
            >
              <summary
                onClick={(event) => {
                  event.preventDefault();
                  setCollapsed((previous) =>
                    previous.includes(group.title)
                      ? previous.filter((title) => title !== group.title)
                      : [...previous, group.title],
                  );
                }}
              >
                {group.title}
                <span aria-hidden="true">⌄</span>
              </summary>
              <div className="nav-group-items">
                {group.items.map(([id, label]) => (
                  <button
                    key={id}
                    className={"nav " + (page === id ? "selected" : "")}
                    aria-current={page === id ? "page" : undefined}
                    onClick={() => navigate(id)}
                  >
                    <ModuleIcon name={id} />
                    <span>{label}</span>
                    {page === id && (
                      <span className="active-dot" aria-hidden="true" />
                    )}
                  </button>
                ))}
              </div>
            </details>
          ))}
          {!filtered.length && (
            <p className="nav-empty" role="status">
              No matching modules.
            </p>
          )}
        </nav>
        <div className="sidebar-account">
          <div className="account-identity">
            <span className="avatar">{username.slice(0, 2).toUpperCase()}</span>
            <div>
              <strong>{username}</strong>
              <small>{role.toLowerCase()}</small>
            </div>
          </div>
          <a
            href="/accounts/password_change/"
            onClick={(e) => {
              if (!confirmLeave()) e.preventDefault();
            }}
          >
            Change password
          </a>
          <button className="secondary" disabled={signingOut} onClick={logout}>
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </aside>
    </>
  );
}
