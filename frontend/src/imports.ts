export function defaultImportDecision(row: any, mode: string) {
  const automatic =
    row.errors.length === 0 &&
    ((!row.current && row.candidates.length === 0) ||
      (mode === "add_update" && row.current));
  return {
    action: automatic ? "apply" : "skip",
    fields: "excel",
    disks: row.current ? "merge" : "replace",
    credential: "preserve",
    match: row.match || "",
  };
}
