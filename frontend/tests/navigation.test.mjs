import assert from "node:assert/strict";
import test from "node:test";
import { moduleGroups } from "../src/navigation.ts";
const ids = (admin, role) =>
  moduleGroups(admin, role).flatMap((group) => group.items.map(([id]) => id));
test("admin navigation contains every configured management module without duplicates", () => {
  const modules = ids(true, "ADMIN");
  assert.equal(modules.length, new Set(modules).size);
  for (const id of [
    "users",
    "departments",
    "programs",
    "years",
    "semesters",
    "sections",
    "subjects",
    "faculty",
    "students",
    "rooms",
    "periods",
    "settings",
    "audit",
    "conflicts",
    "assignments",
    "availability",
    "leave",
    "department-rules",
    "department-access",
    "room-availability",
  ])
    assert.ok(modules.includes(id), id);
});
test("HOD navigation excludes institution administration and student management", () => {
  const modules = ids(false, "HOD");
  for (const id of [
    "subjects",
    "faculty",
    "assignments",
    "conflicts",
    "timetables",
  ])
    assert.ok(modules.includes(id), id);
  for (const id of [
    "users",
    "students",
    "settings",
    "audit",
    "department-access",
    "departments",
  ])
    assert.ok(!modules.includes(id), id);
});
test("faculty navigation contains personal workspace and requests only", () => {
  assert.deepEqual(ids(false, "FACULTY"), [
    "dashboard",
    "timetables",
    "notifications",
    "reports",
    "requests",
  ]);
});
test("student navigation has no management or request links", () => {
  assert.deepEqual(ids(false, "STUDENT"), [
    "dashboard",
    "timetables",
    "notifications",
    "reports",
  ]);
});
test("all module identifiers and labels are present and valid for hash navigation", () => {
  for (const group of moduleGroups(true, "ADMIN")) {
    assert.ok(group.title.length);
    for (const [id, label] of group.items) {
      assert.match(id, /^[a-z-]+$/);
      assert.ok(label.trim());
    }
  }
});
