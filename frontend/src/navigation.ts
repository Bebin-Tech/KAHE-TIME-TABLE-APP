export type ModuleGroup = { title: string; items: [string, string][] };
export function moduleGroups(admin: boolean, role: string): ModuleGroup[] {
  const groups: ModuleGroup[] = [
    {
      title: "Workspace",
      items: [
        ["dashboard", "Dashboard"],
        ["timetables", "Timetables"],
        ["notifications", "Notifications"],
        ["reports", "Reports & workload"],
        ...(role !== "STUDENT" || admin
          ? [["requests", "Requests & leave"] as [string, string]]
          : []),
      ],
    },
  ];
  if (admin || role === "HOD") {
    groups.push({
      title: "Scheduling",
      items: [
        ["conflicts", "Conflict reports"],
        ["assignments", "Teaching assignments"],
        ["availability", "Faculty availability"],
        ["leave", "Approved leave"],
        ["department-rules", "Scheduling rules"],
      ],
    });
    groups.push({
      title: "Academic management",
      items: admin
        ? [
            ["departments", "Departments"],
            ["programs", "Programs"],
            ["years", "Academic years"],
            ["semesters", "Semesters"],
            ["sections", "Sections"],
            ["subjects", "Subjects"],
          ]
        : [["subjects", "Subjects"]],
    });
    groups.push({
      title: "People & facilities",
      items: [
        ["faculty", "Faculty"],
        ...(admin ? [["students", "Students"] as [string, string]] : []),
        ["rooms", "Classrooms & labs"],
        ["periods", "Periods & breaks"],
        ...(admin
          ? [["room-availability", "Room availability"] as [string, string]]
          : []),
      ],
    });
  }
  if (admin)
    groups.push({
      title: "Administration",
      items: [
        ["users", "User accounts"],
        ["department-access", "Department permissions"],
        ["audit", "Audit history"],
        ["settings", "Institution settings"],
      ],
    });
  return groups;
}
