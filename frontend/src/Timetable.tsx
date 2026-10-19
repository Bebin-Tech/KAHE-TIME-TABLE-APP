import React, { useEffect, useState } from "react";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import { api, ApiError, Issue } from "./api";
import { useModalFocus } from "./useModalFocus";
export type Entry = {
  id?: number;
  subject: number;
  faculty: number;
  room: number;
  day: number;
  period: number;
  duration: number;
  subject_name?: string;
  subject_code?: string;
  faculty_name?: string;
  room_name?: string;
};
export type Table = {
  id: number;
  section: number;
  section_name: string;
  department: string;
  program: string;
  semester: string;
  year: string;
  status: string;
  version: number;
  revision: number;
  entries: Entry[];
  history: {
    previous_state: string;
    new_state: string;
    comments: string;
    created_at: string;
    actor__username: string;
  }[];
};
type Period = {
  id: number;
  name: string;
  starts_at: string;
  ends_at: string;
  is_break: boolean;
};
type Assignment = {
  id: number;
  subject: number;
  faculty: number;
  name: string;
  semester: number;
  year: number;
  duration: number;
  weekly_periods: number;
  room_type: string;
};
type Config = {
  sections: {
    id: number;
    name: string;
    semester: number;
    year: number;
    department: number;
    can_publish: boolean;
  }[];
  assignments: Assignment[];
  rooms: {
    id: number;
    code: string;
    name: string;
    room_type: string;
    capacity: number;
  }[];
  periods: Period[];
  working_days: number[];
  require_approval: boolean;
  timezone: string;
};
const DAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];
function DragItem({
  id,
  children,
  disabled = false,
}: {
  id: string;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id, disabled });
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={"drag-item " + (isDragging ? "dragging" : "")}
      style={
        transform
          ? {
              transform: `translate3d(${transform.x}px,${transform.y}px,0)`,
              zIndex: 10,
            }
          : undefined
      }
    >
      {children}
    </div>
  );
}
function Slot({
  day,
  period,
  children,
  disabled,
  onClick,
}: {
  day: number;
  period: number;
  children: React.ReactNode;
  disabled: boolean;
  onClick: () => void;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `slot:${day}:${period}`,
    disabled,
  });
  return (
    <td ref={setNodeRef} className={"slot " + (isOver ? "drop-target" : "")}>
      <div>{children}</div>
      {!disabled && (
        <button
          className="slot-add secondary"
          aria-label={`Add class on ${DAYS[day]}`}
          onClick={onClick}
        >
          ＋
        </button>
      )}
    </td>
  );
}
export function ConflictList({ issues }: { issues: Issue[] }) {
  return issues.length ? (
    <div className="issues" aria-live="polite">
      {issues.map((i, n) => (
        <article key={n} className={i.severity === "error" ? "error" : ""}>
          <strong>
            {i.type.replaceAll("_", " ")} · {i.severity}
          </strong>
          <p>
            {i.day === null ? "" : DAYS[i.day] + " · "}
            {i.message}
          </p>
          <small>
            {i.faculty} {i.room} {i.conflicting_assignment}
          </small>
          <p>{i.suggestion}</p>
        </article>
      ))}
    </div>
  ) : null;
}
export function Timetables({
  editor,
  admin,
}: {
  editor: boolean;
  admin: boolean;
}) {
  const [tables, setTables] = useState<Table[]>([]);
  const [config, setConfig] = useState<Config>();
  const [periods, setPeriods] = useState<Period[]>([]);
  const [days, setDays] = useState<number[]>([]);
  const [table, setTable] = useState<Table>();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [past, setPast] = useState<Entry[][]>([]);
  const [future, setFuture] = useState<Entry[][]>([]);
  const [section, setSection] = useState("");
  const [filter, setFilter] = useState("");
  const [paletteSearch, setPaletteSearch] = useState("");
  const [dayFilter, setDayFilter] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [issues, setIssues] = useState<Issue[]>([]);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(false);
  const [editing, setEditing] = useState<{
    index: number;
    day: number;
    period: number;
    assignment?: number;
  }>();
  useModalFocus(editing !== undefined, () => setEditing(undefined));
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );
  const dirty =
    !!table && JSON.stringify(entries) !== JSON.stringify(table.entries);
  const editable = editor && table?.status === "DRAFT" && !preview;
  async function load() {
    const result = await api("/api/timetables/");
    setTables(result.timetables);
  }
  useEffect(() => {
    let active = true;
    Promise.all([
      api("/api/timetables/"),
      api(editor ? "/api/editor-config/" : "/api/periods/"),
    ])
      .then(([result, c]) => {
        if (!active) return;
        setTables(result.timetables);
        setPeriods(c.periods);
        setDays(c.working_days);
        if (editor) setConfig(c);
      })
      .catch((e) => setError(e.message));
    return () => {
      active = false;
    };
  }, [editor]);
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  function select(t: Table) {
    if (dirty && !confirm("Discard unsaved changes?")) return;
    setTable(t);
    setEntries(t.entries);
    setPast([]);
    setFuture([]);
    setIssues([]);
    setError("");
    setNotice("");
    setPreview(false);
  }
  function fail(e: unknown) {
    setError((e as Error).message);
    setIssues(e instanceof ApiError ? e.issues : []);
  }
  async function stage(next: Entry[], history = true) {
    if (!table) return false;
    setBusy(true);
    setError("");
    try {
      const result = await api(`/api/timetables/${table.id}/`, "POST", {
        action: "check",
        revision: table.revision,
        entries: next,
      });
      setIssues(result.issues);
      if (history) {
        setPast((p) => [...p, entries]);
        setFuture([]);
      }
      setEntries(next);
      return true;
    } catch (e) {
      fail(e);
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function undo() {
    const previous = past.at(-1);
    if (!previous) return;
    if (await stage(previous, false)) {
      setPast((p) => p.slice(0, -1));
      setFuture((f) => [entries, ...f]);
    }
  }
  async function redo() {
    const next = future[0];
    if (!next) return;
    if (await stage(next, false)) {
      setPast((p) => [...p, entries]);
      setFuture((f) => f.slice(1));
    }
  }
  async function create(parent?: Table) {
    if (!config || (!section && !parent)) return;
    if (dirty && !confirm("Discard unsaved changes?")) return;
    setBusy(true);
    try {
      const result = await api("/api/timetables/", "POST", {
        section: parent?.section || Number(section),
        parent: parent?.id,
        request_id: crypto.randomUUID(),
      });
      setTable(result);
      setEntries(result.entries);
      setPast([]);
      setFuture([]);
      setIssues([]);
      setNotice("Draft created.");
      await load();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  async function action(name: string) {
    if (!table) return;
    setError("");
    setBusy(true);
    try {
      if (!["save", "validate"].includes(name) && dirty)
        throw Error("Save or reset unsaved changes before changing status.");
      let comment = "";
      if (name === "return") {
        const reason = prompt("Reason for returning this timetable:");
        if (!reason) return;
        comment = reason;
      }
      if (
        ["publish", "archive", "withdraw"].includes(name) &&
        !confirm(`${name} timetable v${table.version}?`)
      )
        return;
      const result = await api(`/api/timetables/${table.id}/`, "POST", {
        action: name,
        revision: table.revision,
        entries,
        comment,
      });
      setIssues(result.issues);
      setNotice(
        name === "validate" ? "Validation passed." : `${name} completed.`,
      );
      if (name !== "validate") {
        setTable(result.timetable);
        setEntries(result.timetable.entries);
        setPast([]);
        setFuture([]);
        await load();
      }
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  function dragEnd(event: DragEndEvent) {
    if (!editable || busy || !event.over) return;
    const target = String(event.over.id).split(":");
    if (target[0] !== "slot") return;
    const [kind, id] = String(event.active.id).split(":");
    setEditing({
      index: kind === "entry" ? Number(id) : -1,
      day: Number(target[1]),
      period: Number(target[2]),
      assignment: kind === "assignment" ? Number(id) : undefined,
    });
  }
  const selectedSection = config?.sections.find((s) => s.id === table?.section);
  const assignments =
    config?.assignments.filter(
      (a) =>
        a.semester === selectedSection?.semester &&
        a.year === selectedSection?.year,
    ) || [];
  async function saveModal(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const data = new FormData(event.currentTarget);
    const assignment = assignments.find(
      (a) => a.id === Number(data.get("assignment")),
    );
    if (!assignment) return;
    const entry: Entry = {
      subject: assignment.subject,
      faculty: assignment.faculty,
      room: Number(data.get("room")),
      day: Number(data.get("day")),
      period: Number(data.get("period")),
      duration: Number(data.get("duration")),
    };
    const next = entries.slice();
    if (editing.index < 0) next.push(entry);
    else next[editing.index] = entry;
    if (await stage(next)) setEditing(undefined);
  }
  const nameFor = (entry: Entry) =>
    entry.subject_name ||
    assignments
      .find((a) => a.subject === entry.subject)
      ?.name.split(" · ")[0] ||
    String(entry.subject);
  const facultyFor = (entry: Entry) =>
    entry.faculty_name ||
    assignments
      .find((a) => a.faculty === entry.faculty && a.subject === entry.subject)
      ?.name.split(" · ")
      .slice(1)
      .join(" · ");
  const filteredTables = tables.filter((t) =>
    `${t.section_name} ${t.department} ${t.program} ${t.semester} ${t.year} ${t.status}`
      .toLowerCase()
      .includes(filter.toLowerCase()),
  );
  return (
    <>
      <div data-unsaved={dirty} className="titlebar">
        <div>
          <small>
            {editor ? "SCHEDULING WORKSPACE" : "YOUR PUBLISHED SCHEDULE"}
          </small>
          <h1>Timetables</h1>
        </div>
        <button className="secondary no-print" onClick={() => window.print()}>
          Print / Save PDF
        </button>
      </div>
      <div className="filters no-print">
        <label>
          Filter year, department, program, semester or section
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </label>
        <label>
          Version
          <select
            value={table?.id || ""}
            onChange={(e) => {
              const t = tables.find((t) => t.id === Number(e.target.value));
              if (t) select(t);
            }}
          >
            <option value="">Choose a timetable…</option>
            {filteredTables.map((t) => (
              <option key={t.id} value={t.id}>
                {t.section_name} · v{t.version} · {t.status}
              </option>
            ))}
          </select>
        </label>
      </div>
      {editor && config && (
        <section className="no-print">
          <div className="filters">
            <label>
              Section for new draft
              <select
                value={section}
                onChange={(e) => setSection(e.target.value)}
              >
                <option value="">Choose section…</option>
                {config.sections.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <button disabled={busy || !section} onClick={() => create()}>
              Create draft
            </button>
          </div>
        </section>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {!tables.length && <p>No timetables are available for your account.</p>}
      {table && (
        <>
          <div className="titlebar">
            <div>
              <h2>{table.section_name}</h2>
              {table.status === "PUBLISHED" && (
                <div className="toolbar no-print">
                  <a href={`/api/exports/pdf/?timetable=${table.id}`}>
                    Download published PDF
                  </a>
                  <a href={`/api/exports/xlsx/?timetable=${table.id}`}>
                    Download published Excel
                  </a>
                </div>
              )}
              <span className="badge">
                {table.status} · Version {table.version}
              </span>{" "}
              <span>
                {dirty ? "Unsaved changes" : "Saved"} · revision{" "}
                {table.revision}
              </span>
            </div>
            <label className="no-print">
              Day
              <select
                value={dayFilter}
                onChange={(e) => setDayFilter(e.target.value)}
              >
                <option value="">All days</option>
                {days.map((d) => (
                  <option key={d} value={d}>
                    {DAYS[d]}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {editor && (
            <div className="toolbar no-print">
              {table.status === "DRAFT" && (
                <>
                  <button
                    disabled={busy || !dirty}
                    onClick={() => action("save")}
                  >
                    Save draft
                  </button>
                  <button disabled={busy} onClick={() => action("validate")}>
                    Validate
                  </button>
                  <button disabled={busy || !past.length} onClick={undo}>
                    Undo
                  </button>
                  <button disabled={busy || !future.length} onClick={redo}>
                    Redo
                  </button>
                  <button
                    disabled={busy || !dirty}
                    onClick={() => {
                      if (confirm("Reset unsaved changes?")) {
                        setEntries(table.entries);
                        setPast([]);
                        setFuture([]);
                        setIssues([]);
                      }
                    }}
                  >
                    Reset unsaved
                  </button>
                  <button onClick={() => setPreview((v) => !v)}>
                    {preview ? "Resume editing" : "Preview"}
                  </button>
                  {config?.require_approval && (
                    <button
                      disabled={busy || dirty}
                      onClick={() => action("submit")}
                    >
                      Submit for review
                    </button>
                  )}
                </>
              )}
              {table.status === "SUBMITTED" && admin && (
                <>
                  <button disabled={busy} onClick={() => action("approve")}>
                    Approve
                  </button>
                  <button disabled={busy} onClick={() => action("return")}>
                    Return for corrections
                  </button>
                </>
              )}
              {(table.status === "APPROVED" ||
                (table.status === "DRAFT" && !config?.require_approval)) &&
                selectedSection?.can_publish && (
                  <button
                    disabled={busy || dirty}
                    onClick={() => action("publish")}
                  >
                    Publish
                  </button>
                )}
              {["PUBLISHED", "ARCHIVED"].includes(table.status) && (
                <button disabled={busy} onClick={() => create(table)}>
                  Create revision
                </button>
              )}
              {table.status === "PUBLISHED" && admin && (
                <>
                  <button disabled={busy} onClick={() => action("archive")}>
                    Archive
                  </button>
                  <button disabled={busy} onClick={() => action("withdraw")}>
                    Withdraw
                  </button>
                </>
              )}
            </div>
          )}
          {busy && (
            <p role="status" aria-busy="true">
              Validating and updating schedule…
            </p>
          )}
          <DndContext sensors={sensors} onDragEnd={dragEnd}>
            <div className="editor-layout">
              {editable && (
                <section className="palette no-print">
                  <h3>Teaching assignments</h3>
                  <label>
                    Search subject or faculty
                    <input
                      type="search"
                      value={paletteSearch}
                      onChange={(e) => setPaletteSearch(e.target.value)}
                    />
                  </label>
                  {assignments
                    .filter((a) =>
                      a.name
                        .toLowerCase()
                        .includes(paletteSearch.toLowerCase()),
                    )
                    .map((a) => (
                      <DragItem
                        key={a.id}
                        id={`assignment:${a.id}`}
                        disabled={busy}
                      >
                        <strong>{a.name}</strong>
                        <small>
                          {a.duration} consecutive · {a.weekly_periods} / week ·{" "}
                          {a.room_type}
                        </small>
                      </DragItem>
                    ))}
                  {!assignments.length && (
                    <p>
                      Configure eligible faculty assignments for this semester
                      and year first.
                    </p>
                  )}
                </section>
              )}
              <div className="table-scroll timetable">
                <table>
                  <thead>
                    <tr>
                      <th>Period</th>
                      {days
                        .filter(
                          (d) => dayFilter === "" || Number(dayFilter) === d,
                        )
                        .map((d) => (
                          <th key={d}>{DAYS[d]}</th>
                        ))}
                    </tr>
                  </thead>
                  <tbody>
                    {periods.map((p, pi) => (
                      <tr key={p.id}>
                        <th>
                          {p.name}
                          <small>
                            {p.starts_at.slice(0, 5)} – {p.ends_at.slice(0, 5)}
                          </small>
                        </th>
                        {days
                          .filter(
                            (d) => dayFilter === "" || Number(dayFilter) === d,
                          )
                          .map((d) => (
                            <Slot
                              key={d}
                              day={d}
                              period={p.id}
                              disabled={!editable || busy || p.is_break}
                              onClick={() =>
                                setEditing({ index: -1, day: d, period: p.id })
                              }
                            >
                              {p.is_break ? (
                                <span className="break-label">Break</span>
                              ) : (
                                entries.map((e, i) => {
                                  const start = periods.findIndex(
                                    (q) => q.id === e.period,
                                  );
                                  if (
                                    e.day !== d ||
                                    pi < start ||
                                    pi >= start + e.duration
                                  )
                                    return null;
                                  return (
                                    <div className="class-card" key={i}>
                                      <DragItem
                                        id={`entry:${i}:${pi}`}
                                        disabled={!editable || busy}
                                      >
                                        <strong>{nameFor(e)}</strong>
                                        <span>{facultyFor(e)}</span>
                                        <small>
                                          {e.room_name ||
                                            config?.rooms.find(
                                              (r) => r.id === e.room,
                                            )?.code}{" "}
                                          · {e.duration} period
                                          {e.duration > 1 ? "s" : ""}
                                          {pi > start ? " · continued" : ""}
                                        </small>
                                      </DragItem>
                                      {editable && pi === start && (
                                        <div className="card-actions">
                                          <button
                                            className="secondary"
                                            onClick={() =>
                                              setEditing({
                                                index: i,
                                                day: e.day,
                                                period: e.period,
                                              })
                                            }
                                          >
                                            Edit
                                          </button>
                                          <button
                                            className="secondary"
                                            disabled={busy}
                                            onClick={() => {
                                              if (
                                                confirm("Remove this session?")
                                              )
                                                stage(
                                                  entries.filter(
                                                    (_, n) => n !== i,
                                                  ),
                                                );
                                            }}
                                          >
                                            Remove
                                          </button>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })
                              )}
                            </Slot>
                          ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </DndContext>
          <ConflictList issues={issues} />
          {editor && table.history.length > 0 && (
            <section className="no-print">
              <h3>Review and revision history</h3>
              {table.history.map((h, i) => (
                <p key={i}>
                  {h.previous_state} → {h.new_state} · {h.actor__username} ·{" "}
                  {new Date(h.created_at).toLocaleString(undefined, {
                    timeZone: config?.timezone || "Asia/Kolkata",
                  })}
                  <br />
                  {h.comments}
                </p>
              ))}
            </section>
          )}
        </>
      )}
      {editing && config && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="session-title"
          >
            <h2 id="session-title">
              {editing.index < 0 ? "Add" : "Move or edit"} session
            </h2>
            <form onSubmit={saveModal}>
              <label>
                Subject and eligible faculty
                <select
                  name="assignment"
                  required
                  defaultValue={
                    editing.assignment ||
                    assignments.find(
                      (a) =>
                        a.subject === entries[editing.index]?.subject &&
                        a.faculty === entries[editing.index]?.faculty,
                    )?.id
                  }
                >
                  <option value="">Choose assignment…</option>
                  {assignments.map((a) => (
                    <option value={a.id} key={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Room / laboratory
                <select
                  name="room"
                  required
                  defaultValue={entries[editing.index]?.room || ""}
                >
                  <option value="">Choose room…</option>
                  {config.rooms.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.code} · {r.name} · {r.room_type} · {r.capacity} seats
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Day
                <select name="day" defaultValue={editing.day}>
                  {days.map((d) => (
                    <option key={d} value={d}>
                      {DAYS[d]}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Starting period
                <select name="period" defaultValue={editing.period}>
                  {periods
                    .filter((p) => !p.is_break)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} · {p.starts_at.slice(0, 5)}–
                        {p.ends_at.slice(0, 5)}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Consecutive periods
                <input
                  type="number"
                  name="duration"
                  min="1"
                  max="20"
                  required
                  defaultValue={
                    entries[editing.index]?.duration ||
                    assignments.find((a) => a.id === editing.assignment)
                      ?.duration ||
                    1
                  }
                />
              </label>
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              <ConflictList issues={issues} />
              <div className="actions">
                <button disabled={busy}>Validate change</button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setEditing(undefined);
                    setError("");
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
