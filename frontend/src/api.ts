export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export function csrf() {
  return (
    document.cookie
      .split("; ")
      .find((x) => x.startsWith("csrftoken="))
      ?.split("=")[1] || ""
  );
}
export async function api<T = any>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const isForm = data instanceof FormData;
  const r = await fetch("/api/" + path, {
    method,
    credentials: "same-origin",
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      "X-CSRFToken": csrf(),
    },
    body:
      data === undefined
        ? undefined
        : isForm
          ? (data as FormData)
          : JSON.stringify(data),
  });
  if (!r.ok) {
    let message = "خطای ارتباط با سرور";
    try {
      message = JSON.stringify(await r.json());
    } catch {}
    throw new ApiError(r.status, message);
  }
  return r.json();
}
export async function download(path: string, data: unknown) {
  const r = await fetch("/api/" + path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new ApiError(r.status, JSON.stringify(await r.json()));
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = "infrahub.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}
export const statusLabels: Record<string, string> = {
  planned: "برنامه‌ریزی",
  in_progress: "در حال انجام",
  completed: "تکمیل‌شده",
  blocked: "متوقف",
};
export const roles: Record<string, string> = {
  viewer: "بیننده",
  operator: "اپراتور",
  editor: "ویرایشگر",
  manager: "مدیر پروژه",
};
export function time(v: string) {
  return new Intl.DateTimeFormat("fa-IR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Tehran",
  }).format(new Date(v));
}
export const fields: Record<string, string> = {
  server_name: "Server Name",
  environment: "محیط",
  application: "Application",
  vms: "VMs",
  cpu: "CPU (Core)",
  ram: "RAM (GB)",
  os: "OS",
  network: "Network / VLAN",
  ip: "Server IP Addr",
  subnet: "Subnet (CIDR)",
  gateway: "GW IP Addr",
  interfaces: "آدرس‌های شبکه",
  username: "Username",
  status: "وضعیت",
  archived: "بایگانی",
};
