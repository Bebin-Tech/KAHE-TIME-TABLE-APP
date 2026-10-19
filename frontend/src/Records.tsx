import React, { useEffect, useState } from "react";
import { api } from "./api";
import { useModalFocus } from "./useModalFocus";
type Field = {
  name: string;
  label: string;
  required: boolean;
  kind: string;
  choices: [string | number, string][] | null;
  initial: unknown;
  disabled?: boolean;
};
type Row = Record<string, unknown> & { id: number };
type Schema = {
  fields: Field[];
  rows: Row[];
  writable: boolean;
  can_create?: boolean;
  can_delete?: boolean;
};
export function Records({ resource }: { resource: string }) {
  const [schema, setSchema] = useState<Schema>();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState<Row | null>();
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  useModalFocus(editing !== undefined, () => setEditing(undefined));
  const base =
    resource === "users" ? "/api/accounts/" : `/api/academic/${resource}/`;
  const load = () =>
    api(base)
      .then(setSchema)
      .catch((e) => setError(e.message));
  useEffect(() => {
    setSchema(undefined);
    setEditing(undefined);
    setError("");
    setMessage("");
    load();
  }, [resource]);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!schema) return;
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const payload: Record<string, unknown> = {};
    try {
      for (const field of schema.fields) {
        const raw = form.get(field.name);
        payload[field.name] =
          field.kind === "checkbox"
            ? raw === "on"
            : field.kind === "json"
              ? JSON.parse(String(raw || "[]"))
              : raw;
      }
      await api(
        `${base}${editing?.id ? editing.id + "/" : ""}`,
        editing?.id ? "PUT" : "POST",
        payload,
      );
      setEditing(undefined);
      setMessage("Saved successfully.");
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(row: Row) {
    if (!confirm("Delete this record? Referenced records cannot be deleted."))
      return;
    setBusy(true);
    try {
      await api(`${base}${row.id}/`, "DELETE");
      setMessage("Record deleted.");
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const display = (field: Field, value: unknown) =>
    field.choices?.find((c) => String(c[0]) === String(value))?.[1] ??
    (typeof value === "object" ? JSON.stringify(value) : String(value ?? ""));
  return (
    <>
      <div className="titlebar">
        <div>
          <small>ACADEMIC CONFIGURATION</small>
          <h1>{resource.replaceAll("-", " ")}</h1>
        </div>
        {schema?.writable && schema.can_create !== false && (
          <button
            onClick={() => {
              setEditing(null);
              setError("");
            }}
          >
            Add record
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {!schema ? (
        <p aria-busy="true">Loading records…</p>
      ) : (
        <section>
          <label>
            Search records{" "}
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              type="search"
            />
          </label>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {schema.fields.map((f) => (
                    <th key={f.name}>{f.label}</th>
                  ))}
                  {schema.writable && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {schema.rows
                  .filter((r) =>
                    JSON.stringify(r)
                      .toLowerCase()
                      .includes(search.toLowerCase()),
                  )
                  .map((row) => (
                    <tr key={row.id}>
                      {schema.fields.map((f) => (
                        <td key={f.name}>
                          {display(f, row[f.name] ?? row[f.name + "_id"])}
                        </td>
                      ))}
                      {schema.writable && (
                        <td>
                          <button
                            className="secondary"
                            onClick={() => {
                              setEditing(row);
                              setError("");
                            }}
                          >
                            Edit
                          </button>{" "}
                          {schema.can_delete !== false &&
                            resource !== "users" && (
                              <button
                                className="secondary"
                                disabled={busy}
                                onClick={() => remove(row)}
                              >
                                Delete
                              </button>
                            )}
                        </td>
                      )}
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          {!schema.rows.length && (
            <p>No records yet. Add records using the form above.</p>
          )}
        </section>
      )}
      {editing !== undefined && schema && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="form-title"
          >
            <h2 id="form-title">
              {editing ? "Edit" : "Add"} {resource}
            </h2>
            <form onSubmit={save}>
              {schema.fields.map((f) => {
                const value =
                  editing?.[f.name] ??
                  editing?.[f.name + "_id"] ??
                  f.initial ??
                  "";
                return (
                  <label key={f.name}>
                    {f.label}
                    {f.choices ? (
                      <select
                        name={f.name}
                        required={f.required}
                        disabled={f.disabled}
                        defaultValue={String(value)}
                      >
                        <option value="">Select…</option>
                        {f.choices.map((c) => (
                          <option key={String(c[0])} value={c[0]}>
                            {c[1]}
                          </option>
                        ))}
                      </select>
                    ) : f.kind === "checkbox" ? (
                      <input
                        name={f.name}
                        type="checkbox"
                        disabled={f.disabled}
                        defaultChecked={Boolean(value)}
                      />
                    ) : (
                      <input
                        name={f.name}
                        type={f.kind === "json" ? "text" : f.kind}
                        disabled={f.disabled}
                        required={f.required}
                        defaultValue={
                          f.kind === "json"
                            ? JSON.stringify(value || [])
                            : String(value)
                        }
                      />
                    )}
                  </label>
                );
              })}
              <p className="error" role="alert">
                {error}
              </p>
              <div className="actions">
                <button disabled={busy}>
                  {busy ? "Saving…" : "Save record"}
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setEditing(undefined)}
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
