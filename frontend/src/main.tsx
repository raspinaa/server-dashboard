/**
 * رابط فارسی/RTL موجودی؛ هر کامپوننت یک گردش کار واقعی API را پوشش می‌دهد.
 * مجوزهای UI فقط کنترل نمایش هستند؛ backend دوباره هر درخواست را مجوزسنجی می‌کند.
 * رمز بازیابی‌شده فقط در حافظه کوتاه‌عمر کامپوننت نگهداری می‌شود، نه storage مرورگر.
 */
import React, { useEffect, useState, useRef, useId, Fragment } from "react";
import { createRoot } from "react-dom/client";
import {
  api,
  download,
  ApiError,
  fields,
  statusLabels,
  roles,
  time,
} from "./api";
import "./style.css";
import "./design.css";
import { defaultImportDecision } from "./imports";
import {
  Icon,
  MetricCard,
  BarChart,
  DonutChart,
  Pager,
  SectionHeading,
  number,
} from "./design";
import { eventLabels, categoryLabels } from "./events";
import {
  Dashboard,
  PasswordDialog,
  ProjectPicker,
  ProjectSelector,
} from "./pages";
type Env = { id: number; name: string; archived: boolean; version: number };
type Project = {
  id: number;
  name: string;
  description: string;
  vcenter_path: string;
  archived: boolean;
  version: number;
  role: string;
  permissions: string[];
  environments: Env[];
};
type Disk = { id?: string; name: string; size: string; order: number };
type NetworkInterface = {
  ip: string;
  subnet: string;
  gateway: string;
  network: string;
};
type Machine = {
  id: string;
  version: number;
  environment: number;
  environment_name: string;
  application: string;
  server_name: string;
  vms: string;
  cpu: number;
  ram: string;
  os: string;
  network: string;
  ip: string;
  subnet: string;
  gateway: string;
  interfaces: NetworkInterface[];
  username: string;
  status: string;
  disks: Disk[];
  has_credential: boolean;
  archived: boolean;
};
type User = {
  id: number;
  username: string;
  first_name: string;
  is_admin: boolean;
  is_active?: boolean;
  permissions: string[];
};
const permLabels: Record<string, string> = {
  export: "خروجی معمولی",
  credential_view: "مشاهده / کپی رمز",
  credential_edit: "تغییر رمز",
  credential_export: "خروجی رمز",
  manage_users: "مدیریت کاربران",
  auth_settings: "تنظیم احراز هویت",
  audit_view: "رویدادهای عمومی",
  perform_updates: "به‌روزرسانی برنامه",
};
const dirtyEditors = new Set<string>();
function navigate() {
  return (
    dirtyEditors.size === 0 || confirm("تغییرات ذخیره‌نشده کنار گذاشته شود؟")
  );
}
const nav = [
  ["dashboard", "نمای کلی زیرساخت", "dashboard"],
  ["inventory", "پروژه‌ها و VM ها", "inventory"],
  ["projects", "تعریف پروژه", "projects"],
  ["imports", "ورود فایل اکسل", "imports"],
  ["exports", "خروجی اکسل از پروژه ها", "exports"],
  ["reports", "گزارش مدیریتی", "▤"],
  ["access", "کاربران و دسترسی", "♧"],
  ["audit", "رویدادهای سیستم", "◷"],
  ["settings", "تنظیمات و به‌روزرسانی", "⚙"],
];
function App() {
  const [user, setUser] = useState<User | null>(null),
    [boot, setBoot] = useState(true),
    [projects, setProjects] = useState<Project[]>([]),
    [pid, setPid] = useState<number>(0),
    [section, setSection] = useState("dashboard"),
    [error, setError] = useState(""),
    [success, setSuccess] = useState(""),
    [busy, setBusy] = useState(false),
    [dark, setDark] = useState(false),
    [epoch, setEpoch] = useState(0),
    [passwordOpen, setPasswordOpen] = useState(false);
  const sessionGeneration = useRef(0);
  const project = projects.find((p) => p.id === pid);
  const refresh = async () => {
    const generation = sessionGeneration.current;
    const [ps, session] = await Promise.all([
      api<Project[]>("projects/"),
      api("session/"),
    ]);
    if (generation !== sessionGeneration.current) return;
    setProjects(ps);
    setUser(session.user);
    setPid((old) => (ps.some((p) => p.id === old) ? old : 0));
    setEpoch((e) => e + 1);
  };
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await fn();
    } catch (e) {
      if (e instanceof ApiError && e.status === 403)
        setError("دسترسی مجاز نیست یا جلسه منقضی شده است. " + e.message);
      else if (e instanceof ApiError && e.status === 409)
        setError(
          "تعارض نسخه: داده تغییر کرده است. نسخه تازه را بارگذاری و تغییرات را دوباره بررسی کنید.",
        );
      else setError(e instanceof Error ? e.message : "خطا");
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    api("session/")
      .then(async (s) => {
        setUser(s.user);
        if (s.user) await refresh();
      })
      .catch((e) => setError(String(e)))
      .finally(() => setBoot(false));
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);
  if (boot)
    return (
      <div className="loading" role="status">
        در حال بارگذاری Infra-HUB…
      </div>
    );
  if (!user)
    return (
      <main className="login">
        <div className="brand">
          <Icon name="inventory" size={32} />
          <span>Infra-HUB</span>
        </div>
        <h1>ورود به فضای مدیریت موجودی</h1>
        <p>داده‌های پروژه؛ از Excel تا همکاری تیمی</p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            run(async () => {
              const s = await api("login/", "POST", Object.fromEntries(f));
              sessionGeneration.current++;
              setUser(s.user);
              setSection("dashboard");
              await refresh();
            });
          }}
        >
          <label>
            نام کاربری
            <input name="username" autoComplete="username" required dir="ltr" />
          </label>
          <label>
            رمز عبور
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              dir="ltr"
            />
          </label>
          <button disabled={busy}>ورود امن</button>
        </form>
        <small>مدیریت یکپارچه پروژه‌ها، ماشین‌ها و منابع زیرساخت</small>
      </main>
    );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <Icon name="inventory" size={32} />
          <span>Infra-HUB</span>
        </div>
        <p className="navlabel">فضای کاری</p>
        <nav>
          {nav
            .filter(
              ([k]) =>
                !["access", "audit", "settings", "imports"].includes(k) ||
                (k === "settings" &&
                  (user.is_admin ||
                    user.permissions.includes("perform_updates"))) ||
                (k === "imports" &&
                  projects.some((p) => p.role === "manager" && !p.archived)) ||
                (k === "access" &&
                  (user.is_admin ||
                    user.permissions.includes("manage_users"))) ||
                (k === "audit" &&
                  (user.is_admin || user.permissions.includes("audit_view"))),
            )
            .map(([k, t, i]) => (
              <button
                key={k}
                className={section === k ? "active" : ""}
                onClick={() => {
                  if (!navigate()) return;
                  setSection(k);
                  setError("");
                  setSuccess("");
                }}
              >
                <Icon name={k} />
                {t}
              </button>
            ))}
        </nav>
        {section === "inventory" && (
          <div className="sidebar-projects" aria-label="پروژه‌های موجودی">
            {projects
              .filter((p) => !p.archived)
              .map((p) => (
                <button
                  key={p.id}
                  className={pid === p.id ? "selected" : ""}
                  onClick={() => {
                    if (navigate()) setPid(p.id);
                  }}
                >
                  <Icon name="projects" size={16} />
                  {p.name}
                </button>
              ))}
          </div>
        )}
        <div className="asidebottom">
          <strong>{user.first_name || user.username}</strong>
          <small>جلسه محلی · دسترسی پروژه‌ای</small>
        </div>
      </aside>
      <div className="workspace">
        <header>
          <div>
            <span className="eyebrow">
              مدیریت و همکاری / {nav.find((n) => n[0] === section)?.[1]}
            </span>
            <h1>{nav.find((n) => n[0] === section)?.[1]}</h1>
          </div>
          <div className="toolbar">
            <details className="profile-menu">
              <summary aria-label="منوی حساب کاربری">
                <span className="avatar">
                  <Icon name="user" />
                </span>
                <span>{user.first_name || user.username}</span>
                <Icon name="chevron" size={16} />
              </summary>
              <div className="profile-options">
                <strong>{user.username}</strong>
                <button
                  className="ghost"
                  onClick={(e) => {
                    (
                      e.currentTarget.closest("details") as HTMLDetailsElement
                    ).open = false;
                    setPasswordOpen(true);
                  }}
                >
                  تغییر رمز
                </button>
                <button
                  className="ghost"
                  aria-label="خروج از حساب"
                  onClick={() => {
                    if (!navigate()) return;
                    run(async () => {
                      sessionGeneration.current++;
                      await api("logout/", "POST");
                      setUser(null);
                      setProjects([]);
                      setPid(0);
                      setSection("dashboard");
                    });
                  }}
                >
                  خروج
                </button>
              </div>
            </details>
            {section === "inventory" && (
              <label className="compact">
                پروژه
                <select
                  aria-label="انتخاب پروژه"
                  value={pid}
                  onChange={(e) => {
                    if (navigate()) setPid(Number(e.target.value));
                  }}
                >
                  <option value={0}>انتخاب پروژه</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                      {p.archived ? " (بایگانی)" : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <button
              className="ghost"
              aria-label="تغییر ظاهر"
              onClick={() => setDark(!dark)}
            >
              {dark ? "☀" : "☾"}
            </button>
          </div>
        </header>
        <main key={user.id}>
          {passwordOpen && (
            <PasswordDialog
              run={run}
              close={() => setPasswordOpen(false)}
              notice={setSuccess}
            />
          )}
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          {success && (
            <div role="status" className="success">
              {success}
            </div>
          )}
          {busy && (
            <div role="status" className="progress">
              در حال انجام…
            </div>
          )}
          {section === "dashboard" ? (
            <Dashboard
              epoch={epoch}
              projects={projects}
              openProject={(id) => {
                setPid(id);
                setSection("inventory");
              }}
            />
          ) : section === "inventory" ? (
            <>
              <ProjectPicker
                projects={projects}
                selected={pid}
                select={setPid}
              />
              {project ? (
                <Inventory
                  key={project.id}
                  project={project}
                  epoch={epoch}
                  user={user}
                  run={run}
                  refresh={refresh}
                  notice={setSuccess}
                />
              ) : (
                <div className="empty">
                  برای نمایش ماشین‌ها، یکی از پروژه‌ها را انتخاب کنید.
                </div>
              )}
            </>
          ) : section === "imports" ? (
            <>
              <ProjectSelector
                label="پروژه مقصد فایل اکسل"
                projects={projects.filter(
                  (p) => p.role === "manager" && !p.archived,
                )}
                value={pid}
                select={(id) => {
                  if (navigate()) setPid(id);
                }}
              />
              {project?.role === "manager" && !project.archived ? (
                <Imports
                  key={project.id}
                  project={project}
                  run={run}
                  refresh={refresh}
                  notice={setSuccess}
                />
              ) : (
                <div className="empty">
                  پروژه مقصد را انتخاب کنید، سپس فایل را بارگذاری کنید.
                </div>
              )}
            </>
          ) : section === "projects" ? (
            <Projects
              projects={projects}
              user={user}
              run={run}
              refresh={refresh}
            />
          ) : section === "access" ? (
            <>
              <ProjectSelector
                label="پروژه برای مدیریت عضویت"
                projects={projects.filter((p) => p.role === "manager")}
                value={pid}
                select={setPid}
              />
              <Access
                project={project?.role === "manager" ? project : undefined}
                actor={user}
                run={run}
                epoch={epoch}
                refresh={refresh}
              />
            </>
          ) : section === "audit" ? (
            <AuditPage run={run} />
          ) : section === "settings" ? (
            <Settings user={user} run={run} notice={setSuccess} />
          ) : section === "reports" ? (
            <ManagementReports
              projects={projects}
              epoch={epoch}
              run={run}
              notice={setSuccess}
            />
          ) : section === "exports" ? (
            <Exports
              project={project}
              projects={projects}
              run={run}
              notice={setSuccess}
            />
          ) : (
            <div className="empty">بخش مورد نظر در دسترس نیست.</div>
          )}
        </main>
        <footer>
          Infra-HUB · منابع تخصیص‌یافته از موجودی ثبت‌شده محاسبه می‌شوند؛ پایش
          زنده انجام نمی‌شود.
        </footer>
      </div>
    </div>
  );
}
type Run = (fn: () => Promise<void>) => Promise<void>;
function Projects({
  projects,
  user,
  run,
  refresh,
}: {
  projects: Project[];
  user: User;
  run: Run;
  refresh: () => Promise<void>;
}) {
  const [selected, setSelected] = useState<Project | null>(null);
  const [open, setOpen] = useState(false);
  return (
    <>
      <section className="panel">
        <SectionHeading
          title={selected ? "ویرایش پروژه" : "تعریف پروژه"}
          description="مشخصات پروژه و محیط‌های آن را در یک محل مدیریت کنید."
        >
          {user.is_admin && (
            <button
              onClick={() => {
                setSelected(null);
                setOpen(!open);
              }}
              aria-expanded={open}
            >
              تعریف پروژه جدید <Icon name="chevron" />
            </button>
          )}
        </SectionHeading>
        {open && (user.is_admin || selected) && (
          <form
            key={selected?.id || "new"}
            className="formgrid"
            onSubmit={(e) => {
              e.preventDefault();
              const d = Object.fromEntries(new FormData(e.currentTarget));
              run(async () => {
                await api(
                  selected ? `projects/${selected.id}/` : "projects/",
                  selected ? "PATCH" : "POST",
                  {
                    ...d,
                    version: selected?.version,
                    archived: d.archived === "on",
                  },
                );
                setSelected(null);
                setOpen(false);
                await refresh();
              });
            }}
          >
            <label>
              نام پروژه
              <input
                name="name"
                defaultValue={selected?.name}
                required
                maxLength={180}
              />
            </label>
            <label>
              مسیر توصیفی vCenter
              <input
                name="vcenter_path"
                dir="ltr"
                defaultValue={selected?.vcenter_path}
              />
            </label>
            <label className="wide">
              شرح
              <textarea
                name="description"
                defaultValue={selected?.description}
              />
            </label>
            {selected && (
              <label className="check">
                <input
                  name="archived"
                  type="checkbox"
                  defaultChecked={selected.archived}
                />
                بایگانی پروژه
              </label>
            )}
            <div className="wide actions">
              <button>ذخیره پروژه</button>
              {selected && (
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    setSelected(null);
                    setOpen(false);
                  }}
                >
                  لغو
                </button>
              )}
            </div>
          </form>
        )}
      </section>
      <div className="cards">
        {projects.map((p) => (
          <section className="panel" key={p.id}>
            <h2>
              {p.name} {p.archived && <small>بایگانی</small>}
            </h2>
            <p>{p.description || "بدون شرح"}</p>
            <p dir="ltr" className="muted">
              {p.vcenter_path || "—"}
            </p>
            <small>
              نقش شما: {roles[p.role]} · نسخه {p.version}
            </small>
            {p.role === "manager" && (
              <>
                <button
                  className="ghost"
                  onClick={() => {
                    setSelected(p);
                    setOpen(true);
                  }}
                  aria-expanded={selected?.id === p.id && open}
                >
                  ویرایش پروژه
                </button>
                {selected?.id === p.id && open && (
                  <>
                    <h3>محیط‌ها</h3>
                    {p.environments.map((env) => (
                      <EnvironmentRow
                        key={env.id + "-" + env.version}
                        env={env}
                        project={p}
                        run={run}
                        refresh={refresh}
                      />
                    ))}
                    <form
                      className="inlineform"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const f = e.currentTarget,
                          name = new FormData(f).get("name");
                        run(async () => {
                          await api(`projects/${p.id}/environments/`, "POST", {
                            name,
                          });
                          f.reset();
                          await refresh();
                        });
                      }}
                    >
                      <input
                        name="name"
                        aria-label="نام محیط جدید"
                        placeholder="محیط جدید، مثلاً Staging"
                        required
                      />
                      <button>افزودن</button>
                    </form>
                  </>
                )}
              </>
            )}
          </section>
        ))}
      </div>
    </>
  );
}
function EnvironmentRow({
  env,
  project,
  run,
  refresh,
}: {
  env: Env;
  project: Project;
  run: Run;
  refresh: () => Promise<void>;
}) {
  return (
    <form
      className="inlineform"
      onSubmit={(e) => {
        e.preventDefault();
        const d = Object.fromEntries(new FormData(e.currentTarget));
        run(async () => {
          await api(`projects/${project.id}/environments/`, "PATCH", {
            id: env.id,
            version: env.version,
            name: d.name,
            archived: d.archived === "on",
          });
          await refresh();
        });
      }}
    >
      <input
        aria-label="نام محیط"
        name="name"
        defaultValue={env.name}
        required
      />
      <label className="check">
        <input name="archived" type="checkbox" defaultChecked={env.archived} />
        بایگانی
      </label>
      <button className="ghost">ذخیره</button>
    </form>
  );
}
function Inventory({
  project,
  epoch,
  user,
  run,
  refresh,
  notice,
}: {
  project: Project;
  epoch: number;
  user: User;
  run: Run;
  refresh: () => Promise<void>;
  notice: (s: string) => void;
}) {
  const [env, setEnv] = useState(""),
    [search, setSearch] = useState(""),
    [page, setPage] = useState(1),
    [pageSize, setPageSize] = useState(30),
    [sort, setSort] = useState("environment"),
    [direction, setDirection] = useState("asc"),
    [rows, setRows] = useState<Machine[]>([]),
    [count, setCount] = useState(0),
    [stats, setStats] = useState<any>(null),
    [expanded, setExpanded] = useState(""),
    [creating, setCreating] = useState(false),
    [loading, setLoading] = useState(true);
  const canEdit =
    ["editor", "manager"].includes(project.role) && !project.archived;
  useEffect(() => {
    let live = true;
    setLoading(true);
    run(async () => {
      const [r, s] = await Promise.all([
        api(
          `projects/${project.id}/machines/?environment=${env}&search=${encodeURIComponent(search)}&page=${page}&page_size=${pageSize}&sort=${sort}&direction=${direction}`,
        ),
        api(`projects/${project.id}/overview/?environment=${env}`),
      ]);
      if (live) {
        setRows(r.results);
        setCount(r.count);
        setStats(s);
        setLoading(false);
      }
    });
    return () => {
      live = false;
      setExpanded("");
    };
  }, [project.id, env, search, page, pageSize, sort, direction, epoch]);
  const max = Math.max(2, ...rows.map((m) => m.disks.length));
  return (
    <>
      <div className="intro">
        <div>
          <span className="eyebrow">PROJECT OVERVIEW</span>
          <h2>{project.name}</h2>
          <p>
            {project.description ||
              "موجودی، منابع تخصیص‌یافته و فعالیت تیم در یک نگاه"}
          </p>
        </div>
        <span className="badge">{roles[project.role]}</span>
      </div>
      {stats && (
        <>
          <div className="metrics">
            {[
              ["machines", "ماشین", ""],
              ["cpu", "CPU", "Core"],
              ["ram", "RAM", "GB"],
              ["disk", "دیسک", "GB"],
            ].map(([k, l, u]) => (
              <div className="metric" key={k}>
                <span>{l} کل پروژه</span>
                <strong>
                  {Number(stats.project[k]).toLocaleString("fa-IR")}{" "}
                  <small>{u}</small>
                </strong>
                <small>
                  محیط انتخابی:{" "}
                  {Number(stats.selected[k]).toLocaleString("fa-IR")} {u}
                </small>
              </div>
            ))}
          </div>
          <section className="panel">
            <div className="sectionhead">
              <h3>توزیع منابع ثبت‌شده در محیط‌ها</h3>
              <small>
                {project.environments.filter((e) => !e.archived).length} محیط ·
                ظرفیت تخصیص‌یافته
              </small>
            </div>
            <div className="graphs">
              {[
                ["cpu", "CPU · Core"],
                ["ram", "RAM · GB"],
                ["disk", "Disk · GB"],
              ].map(([k, l]) => (
                <div key={k}>
                  <h4 dir="ltr">{l}</h4>
                  {stats.environments.map((e: any) => (
                    <button
                      className="barrow"
                      key={e.id}
                      onClick={() => {
                        setEnv(String(e.id));
                        setPage(1);
                      }}
                      aria-label={`${e.name} ${e[k]} ${l}`}
                    >
                      <span>{e.name}</span>
                      <div className="bartrack">
                        <i
                          style={{
                            width:
                              Math.max(
                                0,
                                (100 * Number(e[k])) /
                                  Math.max(
                                    1,
                                    ...stats.environments.map((x: any) =>
                                      Number(x[k]),
                                    ),
                                  ),
                              ) + "%",
                          }}
                        />
                      </div>
                      <b>{Number(e[k]).toLocaleString("fa-IR")}</b>
                    </button>
                  ))}
                </div>
              ))}
            </div>
            <div className="statuscounts">
              {Object.entries(stats.selected.statuses).map(([k, v]) => (
                <span key={k} className={"badge " + k}>
                  {statusLabels[k]}: {String(v)}
                </span>
              ))}
            </div>
          </section>
        </>
      )}
      <section className="panel inventory">
        <div className="sectionhead">
          <div>
            <h2>
              ماشین‌ها <small>{count.toLocaleString("fa-IR")} رکورد</small>
            </h2>
            <div className="tabs">
              <button
                className={!env ? "selected" : ""}
                onClick={() => {
                  setEnv("");
                  setPage(1);
                }}
              >
                همه محیط‌ها
              </button>
              {project.environments
                .filter((e) => !e.archived)
                .map((e) => (
                  <button
                    key={e.id}
                    className={env === String(e.id) ? "selected" : ""}
                    onClick={() => {
                      setEnv(String(e.id));
                      setPage(1);
                    }}
                  >
                    {e.name}
                  </button>
                ))}
            </div>
          </div>
          <div className="actions">
            <input
              aria-label="جستجوی نام سرور"
              placeholder="جستجوی Server Name…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
            {canEdit && (
              <button onClick={() => setCreating(!creating)}>
                افزودن دستی ماشین
              </button>
            )}
          </div>
        </div>
        {creating && (
          <MachineEditor
            project={project}
            run={run}
            done={async () => {
              setCreating(false);
              await refresh();
            }}
          />
        )}
        {loading ? (
          <div role="status" className="empty">
            در حال بارگذاری…
          </div>
        ) : !rows.length ? (
          <div className="empty">ماشینی در این انتخاب ثبت نشده است.</div>
        ) : (
          <div
            className="tablewrap"
            tabIndex={0}
            aria-label="جدول موجودی قابل پیمایش"
          >
            <table>
              <thead>
                <tr>
                  {[
                    "ردیف",
                    "Environment",
                    "Server Name",
                    "Application",
                    "VMs",
                    "CPU (Core)",
                    "RAM (GB)",
                    ...Array.from(
                      { length: max },
                      (_, i) => `Disk ${i + 1} (GB)`,
                    ),
                    "OS",
                    "Network / VLAN",
                    "Server IP Addr",
                    "Subnet (CIDR)",
                    "GW IP Addr",
                    "Username",
                    "رمز",
                    "وضعیت",
                  ].map((h, index) => {
                    const fields = [
                      "",
                      "environment",
                      "server_name",
                      "application",
                      "vms",
                      "cpu",
                      "ram",
                      ...Array.from({ length: max }, (_, i) => `disk_${i}`),
                      "os",
                      "network",
                      "ip",
                      "subnet",
                      "gateway",
                      "username",
                      "",
                      "status",
                    ];
                    const field = fields[index];
                    return (
                      <th
                        key={h}
                        className={h === "Server Name" ? "sticky" : ""}
                        aria-sort={
                          field === sort
                            ? direction === "asc"
                              ? "ascending"
                              : "descending"
                            : undefined
                        }
                      >
                        {field ? (
                          <button
                            className="sort-heading"
                            onClick={() => {
                              setSort(field);
                              setDirection(
                                field === sort && direction === "asc"
                                  ? "desc"
                                  : "asc",
                              );
                              setPage(1);
                            }}
                          >
                            {h}
                            <span>
                              {field === sort
                                ? direction === "asc"
                                  ? "↑"
                                  : "↓"
                                : "↕"}
                            </span>
                          </button>
                        ) : (
                          h
                        )}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {rows.map((m, i) => (
                  <Fragment key={m.id}>
                    {!env &&
                      (i === 0 ||
                        rows[i - 1].environment_name !==
                          m.environment_name) && (
                        <tr className="environment-divider">
                          <td colSpan={17 + max}>{m.environment_name}</td>
                        </tr>
                      )}
                    <tr className={expanded === m.id ? "expanded" : ""}>
                      <td>{(page - 1) * pageSize + i + 1}</td>
                      <td>{m.environment_name}</td>
                      <td className="sticky">
                        <button
                          className="serverlink"
                          aria-label={"مشخصات ماشین " + m.server_name}
                          aria-expanded={expanded === m.id}
                          onClick={() =>
                            setExpanded(expanded === m.id ? "" : m.id)
                          }
                        >
                          {expanded === m.id ? "▾" : "◂"} {m.server_name}
                        </button>
                      </td>
                      <td>{m.application || "—"}</td>
                      <td>{m.vms || "—"}</td>
                      <td>{m.cpu}</td>
                      <td>{m.ram}</td>
                      {Array.from({ length: max }, (_, d) => (
                        <td key={d} title={m.disks[d]?.name}>
                          {m.disks[d]?.size || "0"}
                        </td>
                      ))}
                      {[
                        "os",
                        "network",
                        "ip",
                        "subnet",
                        "gateway",
                        "username",
                      ].map((k) => (
                        <td dir="ltr" key={k}>
                          {["network", "ip", "subnet", "gateway"].includes(k) &&
                          m.interfaces?.length
                            ? m.interfaces.map((address, i) => (
                                <div key={i}>
                                  {address[k as keyof NetworkInterface] || "—"}
                                </div>
                              ))
                            : String(m[k as keyof Machine] || "—")}
                        </td>
                      ))}
                      <td>
                        <InlineCredential
                          machine={m}
                          project={project}
                          run={run}
                          notice={notice}
                        />
                      </td>
                      <td>
                        <span className={"badge " + m.status}>
                          {statusLabels[m.status]}
                        </span>
                      </td>
                    </tr>
                    {expanded === m.id && (
                      <tr>
                        <td colSpan={17 + max} className="detailcell">
                          <MachineDetail
                            key={m.id + "-" + m.version}
                            machine={m}
                            project={project}
                            user={user}
                            run={run}
                            refresh={refresh}
                            notice={notice}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager
          page={page}
          pages={Math.max(1, Math.ceil(count / pageSize))}
          count={count}
          size={pageSize}
          onPage={setPage}
          onSize={(size) => {
            setPageSize(size);
            setPage(1);
          }}
        />
      </section>
    </>
  );
}
function MachineEditor({
  project,
  machine,
  run,
  done,
}: {
  project: Project;
  machine?: Machine;
  run: Run;
  done: () => Promise<void>;
}) {
  const [newEnvironment, setNewEnvironment] = useState(
    !project.environments.some((e) => !e.archived) &&
      project.role === "manager",
  );
  const [interfaces, setInterfaces] = useState<NetworkInterface[]>(
    machine?.interfaces?.length
      ? machine.interfaces.map((x) => ({ ...x }))
      : [
          {
            ip: machine?.ip || "",
            subnet: machine?.subnet || "",
            gateway: machine?.gateway || "",
            network: machine?.network || "",
          },
        ],
  );
  const [disks, setDisks] = useState<Disk[]>(
      machine?.disks.map((d) => ({ ...d })) || [],
    ),
    [dirty, setDirty] = useState(false),
    [stale, setStale] = useState(false);
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [dirty]);
  const editId = useId();
  useEffect(() => {
    if (dirty) dirtyEditors.add(editId);
    else dirtyEditors.delete(editId);
    return () => {
      dirtyEditors.delete(editId);
    };
  }, [dirty, editId]);
  const groups = [
    [
      "هویت و سرویس",
      ["server_name", "environment", "application", "vms", "os"],
    ],
    ["منابع تخصیص‌یافته", ["cpu", "ram"]],
    ["حساب سیستم", ["username"]],
    ["گردش کار", ["status", "archived"]],
  ] as const;
  return (
    <form
      className="editor"
      onChange={() => setDirty(true)}
      onSubmit={(e) => {
        e.preventDefault();
        const data: any = Object.fromEntries(new FormData(e.currentTarget));
        const requestedNewEnvironment = data.environment === "new";
        const newEnvironmentName = String(data.new_environment || "").trim();
        delete data.new_environment;
        data.cpu = Number(data.cpu);
        data.environment = Number(data.environment);
        data.archived = data.archived === "on";
        data.version = machine?.version;
        data.disks = disks.map((d, i) => ({ ...d, order: i }));
        data.interfaces = interfaces;
        run(async () => {
          try {
            if (requestedNewEnvironment) {
              const existing = project.environments.find(
                (env) => !env.archived && env.name === newEnvironmentName,
              );
              const created =
                existing ||
                (await api<Env>(
                  `projects/${project.id}/environments/`,
                  "POST",
                  {
                    name: newEnvironmentName,
                  },
                ));
              data.environment = created.id;
            }
            const r = await api(
              machine
                ? `machines/${machine.id}/`
                : `projects/${project.id}/machines/`,
              machine ? "PATCH" : "POST",
              data,
            );
            setDirty(false);
            if (r.warnings.length) window.alert(r.warnings.join("\n"));
            await done();
          } catch (e) {
            if (e instanceof ApiError && e.status === 409) setStale(true);
            throw e;
          }
        });
      }}
    >
      {groups.map(([title, ks]) => (
        <fieldset key={title}>
          <legend>{title}</legend>
          <div className="formgrid">
            {ks.map((k) => (
              <label key={k} className={k === "archived" ? "check" : ""}>
                {fields[k]}
                {k === "environment" ? (
                  <select
                    name={k}
                    onChange={(e) =>
                      setNewEnvironment(e.target.value === "new")
                    }
                    defaultValue={
                      machine?.environment ||
                      project.environments.find((e) => !e.archived)?.id ||
                      (project.role === "manager" ? "new" : "")
                    }
                    required
                  >
                    <option value="">انتخاب محیط</option>
                    {project.role === "manager" && (
                      <option value="new">محیط جدید</option>
                    )}
                    {project.environments
                      .filter((e) => !e.archived)
                      .map((e) => (
                        <option key={e.id} value={e.id}>
                          {e.name}
                        </option>
                      ))}
                  </select>
                ) : k === "status" ? (
                  <select name={k} defaultValue={machine?.status || "planned"}>
                    {Object.entries(statusLabels).map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                ) : k === "archived" ? (
                  <input
                    name={k}
                    type="checkbox"
                    defaultChecked={machine?.archived}
                  />
                ) : (
                  <input
                    name={k}
                    dir="ltr"
                    type={["cpu", "ram"].includes(k) ? "number" : "text"}
                    min={0}
                    step={k === "ram" ? ".01" : "1"}
                    required={k === "server_name"}
                    defaultValue={String(machine?.[k as keyof Machine] ?? "")}
                    maxLength={k === "vms" ? 240 : 180}
                  />
                )}
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      {newEnvironment && (
        <label>
          نام محیط جدید
          <input
            name="new_environment"
            required
            maxLength={120}
            placeholder="مثلاً Test یا Production"
          />
        </label>
      )}
      <fieldset>
        <legend>آدرس‌های شبکه</legend>
        <p className="muted">
          هر IP جداست؛ مثلاً 192.0.2.10/24. پیشوند داخل IP خودکار تشخیص داده
          می‌شود.
        </p>
        {interfaces.map((address, i) => (
          <div className="formgrid" key={i}>
            {(["network", "ip", "subnet", "gateway"] as const).map((key) => (
              <label key={key}>
                {fields[key]}
                {i ? ` ${i + 1}` : ""}
                <input
                  dir="ltr"
                  value={address[key]}
                  onChange={(e) =>
                    setInterfaces(
                      interfaces.map((item, n) =>
                        n === i
                          ? {
                              ...item,
                              [key]: e.target.value,
                              ...(key === "ip" && e.target.value.includes("/")
                                ? { subnet: "" }
                                : {}),
                            }
                          : item,
                      ),
                    )
                  }
                />
              </label>
            ))}
            <button
              type="button"
              className="danger"
              onClick={() => {
                setInterfaces(interfaces.filter((_, n) => n !== i));
                setDirty(true);
              }}
            >
              حذف IP
            </button>
          </div>
        ))}
        <button
          type="button"
          className="ghost"
          onClick={() => {
            setInterfaces([
              ...interfaces,
              { ip: "", subnet: "", gateway: "", network: "" },
            ]);
            setDirty(true);
          }}
        >
          ＋ IP دیگر
        </button>
      </fieldset>
      <fieldset>
        <legend>دیسک‌ها · هر دیسک مستقل</legend>
        {disks.map((d, i) => (
          <div className="diskrow" key={d.id || "new" + i}>
            <label>
              نام
              <input
                value={d.name}
                required
                onChange={(e) =>
                  setDisks(
                    disks.map((x, n) =>
                      n === i ? { ...x, name: e.target.value } : x,
                    ),
                  )
                }
              />
            </label>
            <label>
              GB
              <input
                type="number"
                value={d.size}
                required
                min="0.01"
                step=".01"
                onChange={(e) =>
                  setDisks(
                    disks.map((x, n) =>
                      n === i ? { ...x, size: e.target.value } : x,
                    ),
                  )
                }
              />
            </label>
            <button
              type="button"
              className="ghost"
              disabled={i === 0}
              aria-label="جابجایی دیسک به بالا"
              onClick={() => {
                const a = [...disks];
                [a[i - 1], a[i]] = [a[i], a[i - 1]];
                setDisks(a);
                setDirty(true);
              }}
            >
              ↑
            </button>
            <button
              type="button"
              className="danger"
              onClick={() => {
                setDisks(disks.filter((_, n) => n !== i));
                setDirty(true);
              }}
            >
              حذف
            </button>
          </div>
        ))}
        <button
          type="button"
          className="ghost"
          onClick={() => {
            setDisks([
              ...disks,
              {
                name: `Disk ${disks.length + 1}`,
                size: "20",
                order: disks.length,
              },
            ]);
            setDirty(true);
          }}
        >
          ＋ دیسک
        </button>
      </fieldset>
      {stale && (
        <div role="alert" className="error">
          نسخه فرم قدیمی است. تغییرات خود را یادداشت و رکورد را دوباره باز کنید.
          <button
            type="button"
            onClick={() => {
              if (confirm("تغییرات ذخیره‌نشده کنار گذاشته شود؟")) done();
            }}
          >
            بارگذاری نسخه تازه
          </button>
        </div>
      )}
      <div className="actions">
        <button disabled={stale}>ذخیره {dirty ? "تغییرات" : ""}</button>
        <button
          className="ghost"
          type="button"
          onClick={() => {
            if (!dirty || confirm("تغییرات ذخیره‌نشده کنار گذاشته شود؟"))
              done();
          }}
        >
          بستن
        </button>
      </div>
    </form>
  );
}
function InlineCredential({
  machine,
  project,
  run,
  notice,
}: {
  machine: Machine;
  project: Project;
  run: Run;
  notice: (s: string) => void;
}) {
  const [secret, setSecret] = useState(""),
    [manual, setManual] = useState(false);
  useEffect(() => {
    if (!secret) return;
    const timer = setTimeout(() => {
      setSecret("");
      setManual(false);
    }, 15000);
    return () => clearTimeout(timer);
  }, [secret]);
  useEffect(() => {
    const clear = () => {
      setSecret("");
      setManual(false);
    };
    document.addEventListener("visibilitychange", clear);
    return () => {
      clear();
      document.removeEventListener("visibilitychange", clear);
    };
  }, [machine.id]);
  if (!machine.has_credential) return <>—</>;
  if (!project.permissions.includes("credential_view")) return <>••••••</>;
  const retrieve = (action: "reveal" | "copy") =>
    run(async () => {
      const r = await api(`machines/${machine.id}/credential/`, "POST", {
        action,
      });
      if (action === "reveal") {
        setSecret(r.password);
        return;
      }
      try {
        await navigator.clipboard.writeText(r.password);
        notice("رمز کپی شد");
      } catch {
        setSecret(r.password);
        setManual(true);
      }
    });
  return (
    <div className="inlinecredential">
      <span>{secret ? "" : "••••••"}</span>
      <button
        className="ghost"
        aria-label={"نمایش رمز " + machine.server_name}
        onClick={() => retrieve("reveal")}
      >
        نمایش
      </button>
      <button
        className="ghost"
        aria-label={"کپی رمز " + machine.server_name}
        onClick={() => retrieve("copy")}
      >
        کپی
      </button>
      {secret && (
        <input
          aria-label={"رمز بازیابی‌شده " + machine.server_name}
          dir="ltr"
          readOnly
          value={secret}
          onFocus={(e) => e.target.select()}
        />
      )}{" "}
      {manual && <small>متن را برای کپی دستی انتخاب کنید.</small>}
    </div>
  );
}
function CredentialControls({
  machine,
  project,
  run,
  refresh,
  notice,
}: {
  machine: Machine;
  project: Project;
  run: Run;
  refresh: () => Promise<void>;
  notice: (s: string) => void;
}) {
  const [secret, setSecret] = useState(""),
    [fallback, setFallback] = useState(false),
    [editing, setEditing] = useState(false);
  useEffect(() => {
    if (!secret) return;
    const id = setTimeout(() => {
      setSecret("");
      setFallback(false);
    }, 15000);
    return () => {
      clearTimeout(id);
    };
  }, [secret]);
  useEffect(() => {
    const clear = () => {
      setSecret("");
      setFallback(false);
    };
    document.addEventListener("visibilitychange", clear);
    return () => {
      clear();
      document.removeEventListener("visibilitychange", clear);
    };
  }, [machine.id]);
  return (
    <div className="credentials">
      <h4>اعتبارنامه ماشین</h4>
      <p className="muted">
        بازیابی با مجوز مستقل · نمایش ۱۵ ثانیه · ثبت رویداد بدون مقدار رمز
      </p>
      {project.permissions.includes("credential_view") && (
        <div className="actions">
          <button
            className="ghost"
            onClick={() =>
              run(async () => {
                const r = await api(
                  `machines/${machine.id}/credential/`,
                  "POST",
                  { action: "reveal" },
                );
                setSecret(r.password);
              })
            }
          >
            نمایش رمز
          </button>
          <button
            className="ghost"
            onClick={() =>
              run(async () => {
                const r = await api(
                  `machines/${machine.id}/credential/`,
                  "POST",
                  { action: "copy" },
                );
                try {
                  await navigator.clipboard.writeText(r.password);
                  notice("رمز کپی شد");
                } catch {
                  setSecret(r.password);
                  setFallback(true);
                }
              })
            }
          >
            کپی
          </button>
          {secret && (
            <input
              aria-label="رمز بازیابی‌شده"
              readOnly
              value={secret}
              dir="ltr"
              onFocus={(e) => e.target.select()}
            />
          )}{" "}
          {fallback && (
            <small>کپی خودکار ممکن نیست؛ متن را انتخاب و دستی کپی کنید.</small>
          )}
        </div>
      )}
      {project.permissions.includes("credential_edit") && (
        <>
          <button className="ghost" onClick={() => setEditing(!editing)}>
            ویرایش رمز / مرجع
          </button>
          {editing && (
            <form
              className="inlineform"
              onSubmit={(e) => {
                e.preventDefault();
                const f = e.currentTarget;
                run(async () => {
                  await api(`machines/${machine.id}/credential/`, "PUT", {
                    ...Object.fromEntries(new FormData(f)),
                    version: machine.version,
                  });
                  f.reset();
                  setEditing(false);
                  setSecret("");
                  await refresh();
                  notice("اعتبارنامه تغییر کرد");
                });
              }}
            >
              <input
                name="password"
                type="password"
                aria-label="رمز ماشین جدید"
                autoComplete="off"
                placeholder="رمز جدید"
              />
              <input
                name="secret_reference"
                aria-label="مرجع مخزن رمز"
                placeholder="یا مرجع مخزن رمز"
              />
              <button>ذخیره اعتبارنامه</button>
            </form>
          )}
        </>
      )}
      {!project.permissions.includes("credential_view") && (
        <small>مجوز مشاهده رمز ندارید.</small>
      )}
    </div>
  );
}
function MachineDetail({
  machine,
  project,
  user,
  run,
  refresh,
  notice,
}: {
  machine: Machine;
  project: Project;
  user: User;
  run: Run;
  refresh: () => Promise<void>;
  notice: (s: string) => void;
}) {
  const [tab, setTab] = useState("activity"),
    [events, setEvents] = useState<any[]>([]);
  const load = async () =>
    setEvents(await api(`machines/${machine.id}/activity/`));
  useEffect(() => {
    run(load);
  }, [machine.id]);
  return (
    <div className="details">
      <div className="sectionhead">
        <strong dir="ltr">
          {machine.server_name} <small>{machine.id}</small>
        </strong>
        <div className="tabs">
          <button
            className={tab === "activity" ? "selected" : ""}
            onClick={() => setTab("activity")}
          >
            فعالیت و نظرها
          </button>
          <button
            className={tab === "specs" ? "selected" : ""}
            onClick={() => setTab("specs")}
          >
            مشخصات و ویرایش
          </button>
        </div>
      </div>
      {tab === "specs" ? (
        <>
          {["editor", "manager"].includes(project.role) && !project.archived ? (
            <MachineEditor
              project={project}
              machine={machine}
              run={run}
              done={refresh}
            />
          ) : (
            <p>مشخصات در جدول نمایش داده شده‌اند؛ مجوز ویرایش ندارید.</p>
          )}
          <CredentialControls
            machine={machine}
            project={project}
            run={run}
            refresh={refresh}
            notice={notice}
          />
        </>
      ) : (
        <>
          {project.role !== "viewer" && (
            <form
              className="commentform"
              onSubmit={(e) => {
                e.preventDefault();
                const f = e.currentTarget;
                run(async () => {
                  await api(
                    `machines/${machine.id}/activity/`,
                    "POST",
                    Object.fromEntries(new FormData(f)),
                  );
                  f.reset();
                  await load();
                });
              }}
            >
              <textarea
                aria-label="متن نظر یا کار انجام‌شده"
                name="comment"
                placeholder="چه کاری انجام شد؟ نظر یا فعالیت را بنویسید…"
                required
              />
              <div className="actions">
                <select name="event" aria-label="نوع فعالیت">
                  <option value="comment">نظر</option>
                  <option value="completed_work">کار انجام‌شده</option>
                </select>
                <button>ثبت فعالیت</button>
              </div>
            </form>
          )}
          <div className="timeline">
            {events.length === 0 ? (
              <p>هنوز فعالیتی ثبت نشده است.</p>
            ) : (
              events.map((a) => (
                <article key={a.id}>
                  <div>
                    <b>{a.author}</b> <span className="badge">{a.event}</span>
                    <small>
                      {time(a.timestamp)} · {a.source}
                    </small>
                  </div>
                  <p>{a.comment}</p>
                  {a.changes.length > 0 && (
                    <table className="changes">
                      <thead>
                        <tr>
                          <th>فیلد</th>
                          <th>قبلی</th>
                          <th>جدید</th>
                        </tr>
                      </thead>
                      <tbody>
                        {a.changes.map((c: any, i: number) => (
                          <tr key={i}>
                            <td>{fields[c.field] || c.field}</td>
                            <td>
                              <code>{JSON.stringify(c.previous)}</code>
                            </td>
                            <td>
                              <code>{JSON.stringify(c.value)}</code>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {["comment", "completed_work"].includes(a.event) &&
                    (a.author_id === user.id || project.role === "manager") && (
                      <button
                        className="ghost"
                        onClick={() => {
                          const comment = prompt(
                            "متن جدید (نسخه قبلی حفظ می‌شود)",
                            a.comment,
                          );
                          if (comment)
                            run(async () => {
                              await api(
                                `machines/${machine.id}/activity/`,
                                "PATCH",
                                { id: a.id, version: a.version, comment },
                              );
                              await load();
                            });
                        }}
                      >
                        ویرایش نظر
                      </button>
                    )}
                  {a.revisions.length > 0 && (
                    <details>
                      <summary>نسخه‌های قبلی نظر</summary>
                      {a.revisions.map((r: any, i: number) => (
                        <p key={i}>
                          {r.previous} · {r.author__username} ·{" "}
                          {time(r.created_at)}
                        </p>
                      ))}
                    </details>
                  )}
                </article>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
function Imports({
  project,
  run,
  refresh,
  notice,
}: {
  project: Project;
  run: Run;
  refresh: () => Promise<void>;
  notice: (s: string) => void;
}) {
  const [batch, setBatch] = useState<any>(null),
    [sheet, setSheet] = useState(""),
    [mapping, setMapping] = useState<Record<string, string>>({}),
    [header, setHeader] = useState(1),
    [mode, setMode] = useState("add_only"),
    [rows, setRows] = useState<any[]>([]),
    [decisions, setDecisions] = useState<Record<string, any>>({}),
    [history, setHistory] = useState<any[]>([]);
  const load = async () =>
    setHistory(await api(`projects/${project.id}/imports/`));
  useEffect(() => {
    if (project.role === "manager") run(load);
  }, [project.id]);
  const selectSheet = (b: any, name: string) => {
    setRows([]);
    setSheet(name);
    const s = b.sheets.find((s: any) => s.name === name);
    setMapping(s.mapping);
    setHeader(s.header_row);
  };
  const patch = (r: any, value: any) =>
    setDecisions((d) => ({ ...d, [r.row]: { ...d[r.row], ...value } }));
  const prepare = async (
    b: any,
    selected: string,
    columns: Record<string, string>,
    titleRow: number,
  ) => {
    const result = await api(`imports/${b.id}/`, "POST", {
      action: "preview",
      worksheet: selected,
      mapping: columns,
      header_row: titleRow,
      mode,
      version: b.version,
    });
    setBatch({ ...b, ...result });
    setRows(result.rows);
    setDecisions(
      Object.fromEntries(
        result.rows.map((row: any) => [
          row.row,
          defaultImportDecision(row, mode),
        ]),
      ),
    );
    await load();
  };
  if (project.role !== "manager")
    return (
      <div className="empty">ورود Excel به مجوز مدیر پروژه نیاز دارد.</div>
    );
  return (
    <>
      <section className="panel">
        <h2>ورود فایل اکسل</h2>
        <p>
          فایل را انتخاب کنید؛ ستون‌ها و بخش‌ها خودکار شناسایی می‌شوند.
          پیش‌نمایش را بررسی و یک‌بار تأیید کنید.
        </p>
        <p className="muted">
          XLSX، حداکثر ۱۰٬۰۰۰ ردیف؛ فرمول و ماکرو پذیرفته نمی‌شود. فایل اصلی
          به‌صورت رمزگذاری‌شده نگهداری می‌شود.
        </p>
        <form
          className="inlineform"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            run(async () => {
              const b = await api(`projects/${project.id}/imports/`, "POST", f);
              setBatch(b);
              selectSheet(b, b.sheets[0].name);
              setRows([]);
              setDecisions({});
              const selected = b.sheets[0];
              await prepare(
                b,
                selected.name,
                selected.mapping,
                selected.header_row,
              );
            });
          }}
        >
          <input
            aria-label="فایل XLSX"
            name="file"
            type="file"
            accept=".xlsx"
            required
          />
          <button disabled={project.archived}>بارگذاری</button>
        </form>
        {batch && (
          <details>
            <summary>تنظیمات فایل و ستون‌ها (اختیاری)</summary>
            <div className="formgrid">
              <label>
                Worksheet
                <select
                  value={sheet}
                  onChange={(e) => selectSheet(batch, e.target.value)}
                >
                  {batch.sheets.map((s: any) => (
                    <option key={s.name}>{s.name}</option>
                  ))}
                </select>
              </label>
              <label>
                ردیف عنوان
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={header}
                  onChange={(e) => {
                    setHeader(Number(e.target.value));
                    setRows([]);
                  }}
                />
              </label>
              <label>
                حالت
                <select
                  value={mode}
                  onChange={(e) => {
                    setMode(e.target.value);
                    setRows([]);
                  }}
                >
                  <option value="add_only">فقط افزودن</option>
                  <option value="add_update">افزودن و به‌روزرسانی</option>
                </select>
              </label>
            </div>
            <details>
              <summary>بررسی / اصلاح نگاشت ستون‌ها</summary>
              <div className="mappinggrid">
                {batch.sheets
                  .find((s: any) => s.name === sheet)
                  ?.headers.map((h: string, i: number) => (
                    <label key={i}>
                      ستون {i + 1}: {h || "(خالی)"}
                      <select
                        value={mapping[String(i + 1)] || "ignore"}
                        onChange={(e) => (
                          setRows([]),
                          setMapping({
                            ...mapping,
                            [String(i + 1)]: e.target.value,
                          })
                        )}
                      >
                        {[
                          "ignore",
                          "row",
                          "environment",
                          "application",
                          "vms",
                          "cpu",
                          "ram",
                          "disk",
                          "os",
                          "network",
                          "server_name",
                          "ip",
                          "subnet",
                          "gateway",
                          "username",
                          "password",
                          "status",
                          "uuid",
                          "disk_metadata",
                        ].map((f) => (
                          <option key={f} value={f}>
                            {fields[f] ||
                              (
                                {
                                  ignore: "نادیده گرفتن",
                                  disk: "دیسک (GB)",
                                  uuid: "UUID مخفی",
                                  disk_metadata: "متادیتای دیسک",
                                } as Record<string, string>
                              )[f] ||
                              f}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
              </div>
            </details>
            <button
              onClick={() => run(() => prepare(batch, sheet, mapping, header))}
            >
              اعتبارسنجی و پیش‌نمایش
            </button>
          </details>
        )}
        {rows.length > 0 && (
          <>
            <h3>پیش‌نمایش و تصمیم‌ها</h3>
            <p>
              {rows.filter((r) => decisions[r.row]?.action === "apply").length}{" "}
              ردیف آماده ورود است. ردیف‌های جدید خودکار انتخاب می‌شوند؛ تطبیق با
              رکورد موجود و خطاها نیازمند بررسی‌اند.
            </p>
            {rows.map((r) => (
              <article className="previewrow" key={r.row}>
                <div className="sectionhead">
                  <strong>
                    ردیف {r.row} · {r.data.server_name} · {r.data.environment}
                  </strong>
                  <span className="badge">
                    {r.current
                      ? "به‌روزرسانی"
                      : r.candidates.length
                        ? "تطبیق لازم"
                        : "افزودن"}
                  </span>
                </div>
                {r.errors.length > 0 && (
                  <div className="error">{r.errors.join(" · ")}</div>
                )}
                {r.warnings.length > 0 && (
                  <div className="warning">{r.warnings.join(" · ")}</div>
                )}
                <details>
                  <summary>داده Excel و نسخه فعلی</summary>
                  <pre dir="ltr">
                    {JSON.stringify(
                      {
                        excel: r.data,
                        current: r.current,
                        candidates: r.candidates,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </details>
                <details>
                  <summary>
                    تغییر تصمیم این ردیف ·{" "}
                    {decisions[r.row]?.action === "apply"
                      ? "آماده ورود"
                      : "رد می‌شود"}
                  </summary>
                  <div className="formgrid">
                    <label>
                      عمل
                      <select
                        value={decisions[r.row]?.action}
                        onChange={(e) => patch(r, { action: e.target.value })}
                      >
                        <option value="skip">رد کردن</option>
                        <option value="apply">اعمال Excel</option>
                      </select>
                    </label>
                    {r.candidates.length > 0 && (
                      <label>
                        تطبیق صریح
                        <select
                          value={decisions[r.row]?.match}
                          onChange={(e) => patch(r, { match: e.target.value })}
                        >
                          <option value="">انتخاب الزامی</option>
                          <option value="new">ماشین جدید مستقل</option>
                          {r.candidates.map((c: any) => (
                            <option key={c.id} value={c.id}>
                              {c.server_name} · {c.ip} · {c.id}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                    <label>
                      تصمیم فیلدها
                      <select
                        value={
                          typeof decisions[r.row]?.fields === "object"
                            ? "custom"
                            : decisions[r.row]?.fields
                        }
                        onChange={(e) =>
                          patch(r, {
                            fields:
                              e.target.value === "custom"
                                ? Object.fromEntries(
                                    Object.keys(r.data)
                                      .filter((k) => k !== "disks")
                                      .map((k) => [k, "web"]),
                                  )
                                : e.target.value,
                          })
                        }
                      >
                        <option value="web">حفظ مقدار وب</option>
                        <option value="excel">اعمال مقدار Excel</option>
                        <option value="custom">تصمیم به تفکیک فیلد</option>
                      </select>
                    </label>
                    <label>
                      دیسک‌ها
                      <select
                        value={decisions[r.row]?.disks}
                        onChange={(e) => patch(r, { disks: e.target.value })}
                      >
                        <option value="preserve">حفظ همه دیسک‌های وب</option>
                        <option value="merge">
                          اعمال ورودی و حفظ دیسک‌های اضافه
                        </option>
                        <option value="replace">
                          جایگزینی کامل؛ حذف دیسک‌های غایب
                        </option>
                      </select>
                    </label>
                    {r.credential_present && (
                      <label>
                        اعتبارنامه
                        <select
                          value={decisions[r.row]?.credential}
                          onChange={(e) =>
                            patch(r, { credential: e.target.value })
                          }
                        >
                          <option value="preserve">حفظ اعتبارنامه فعلی</option>
                          <option
                            value="apply"
                            disabled={
                              !project.permissions.includes("credential_edit")
                            }
                          >
                            اعمال با مجوز مستقل
                          </option>
                        </select>
                      </label>
                    )}
                  </div>
                  {typeof decisions[r.row]?.fields === "object" && (
                    <div className="mappinggrid">
                      {Object.entries(decisions[r.row].fields).map(([k, v]) => (
                        <label key={k}>
                          {fields[k] || k}
                          <select
                            value={String(v)}
                            onChange={(e) =>
                              patch(r, {
                                fields: {
                                  ...decisions[r.row].fields,
                                  [k]: e.target.value,
                                },
                              })
                            }
                          >
                            <option value="web">حفظ وب</option>
                            <option value="excel">اعمال Excel</option>
                          </select>
                        </label>
                      ))}
                    </div>
                  )}
                </details>
              </article>
            ))}
            <button
              disabled={
                batch?.issues?.length > 0 || batch?.status === "applied"
              }
              onClick={() =>
                run(async () => {
                  const result = await api(`imports/${batch.id}/`, "POST", {
                    action: "apply",
                    version: batch.version,
                    decisions,
                  });
                  setBatch({ ...batch, status: "applied" });
                  notice(
                    `ورود کامل شد: ${result.added} افزوده، ${result.updated} تغییر، ${result.skipped} رد شده`,
                  );
                  await refresh();
                  await load();
                })
              }
            >
              تأیید و اعمال تراکنشی
            </button>
          </>
        )}
      </section>
      <section className="panel">
        <SectionHeading
          title="تاریخچه ورود فایل‌ها"
          description="نتیجه پردازش و تعداد تغییرات هر فایل در پروژه انتخاب‌شده"
        />
        {history.map((b) => (
          <article className="historyitem" key={b.id}>
            <b>{b.filename}</b>
            <span>
              <span
                className={
                  "badge " +
                  (b.status === "applied"
                    ? "active"
                    : b.issues.length
                      ? "failed"
                      : "pending")
                }
              >
                {(
                  {
                    uploaded: "بارگذاری‌شده",
                    previewed: "بررسی‌شده",
                    applied: "اعمال‌شده",
                  } as Record<string, string>
                )[b.status] || b.status}
              </span>{" "}
              · {time(b.created_at)}
            </span>
            <div className="history-counts">
              {Object.entries(b.counts || {}).map(([key, value]) => (
                <span key={key}>
                  {(
                    {
                      added: "افزوده",
                      updated: "ویرایش‌شده",
                      skipped: "ردشده",
                    } as Record<string, string>
                  )[key] || key}
                  : {String(value)}
                </span>
              ))}
            </div>
            {b.issues.length > 0 && (
              <details>
                <summary>{b.issues.length} مورد نیازمند بررسی</summary>
                <pre>{JSON.stringify(b.issues, null, 2)}</pre>
              </details>
            )}
            <button
              className="ghost"
              onClick={() =>
                run(async () => {
                  const data = await api(`imports/${b.id}/`);
                  setBatch(data);
                  selectSheet(data, data.sheets[0].name);
                  setRows(data.rows);
                  setDecisions(
                    Object.fromEntries(
                      data.rows.map((r: any) => [
                        r.row,
                        {
                          action: "skip",
                          fields: "web",
                          disks: "preserve",
                          credential: "preserve",
                          match: "",
                        },
                      ]),
                    ),
                  );
                })
              }
            >
              باز کردن
            </button>
          </article>
        ))}
      </section>
    </>
  );
}
function Exports({
  project: initialProject,
  projects,
  run,
  notice,
}: {
  project: Project | null | undefined;
  projects: Project[];
  run: Run;
  notice: (s: string) => void;
}) {
  const [selected, setSelected] = useState(initialProject?.id || 0);
  const project = projects.find((p) => p.id === selected);
  useEffect(() => {
    setSelected(initialProject?.id || 0);
  }, [initialProject?.id]);
  return (
    <section className="panel">
      <h2>خروجی اکسل از پروژه‌ها</h2>
      <p>
        مقادیر ویرایش‌شده در وب، ستون‌های مستقل دیسک و UUID مخفی در خروجی حفظ
        می‌شوند. رمزها به‌صورت پیش‌فرض حذف شده‌اند.
      </p>
      <label>
        پروژه خروجی
        <select
          aria-label="پروژه خروجی"
          value={selected}
          onChange={(e) => setSelected(Number(e.target.value))}
        >
          <option value={0}>انتخاب پروژه برای خروجی</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      {project && (
        <form
          key={project.id}
          className="formgrid"
          onSubmit={(e) => {
            e.preventDefault();
            const d = Object.fromEntries(new FormData(e.currentTarget));
            run(async () => {
              await download(`projects/${project.id}/exports/`, {
                ...d,
                credentials: d.credentials === "on",
                merged: d.merged === "on",
                environment: d.environment || null,
              });
              notice("فایل خروجی دریافت شد");
            });
          }}
        >
          <label>
            نوع
            <select name="kind">
              <option value="inventory">موجودی ماشین‌ها</option>
              <option value="activity">فعالیت و تغییرات</option>
            </select>
          </label>
          <label>
            محیط
            <select name="environment">
              <option value="">کل پروژه</option>
              {project.environments.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
          </label>
          <label className="check">
            <input type="checkbox" name="merged" defaultChecked />
            ادغام سلول‌های محیط و Application
          </label>
          <label className="check">
            <input
              type="checkbox"
              name="credentials"
              disabled={!project.permissions.includes("credential_export")}
            />
            خروجی رمز با مجوز مستقل (فایل حساس)
          </label>
          <button
            disabled={
              !(
                ["editor", "manager"].includes(project.role) ||
                project.permissions.includes("export")
              )
            }
          >
            دریافت XLSX
          </button>
        </form>
      )}
      <p className="warning">
        فایل رمزدار پس از دانلود تحت کنترل دریافت‌کننده است. فایل خروجی روی سرور
        ذخیره نمی‌شود و هر درخواست دوباره مجوزسنجی می‌شود.
      </p>
    </section>
  );
}
function PermissionChecks({
  selected,
  toggle,
  global = false,
}: {
  selected: string[];
  toggle: (p: string) => void;
  global?: boolean;
}) {
  return (
    <div className="permissiongrid">
      {Object.entries(permLabels)
        .filter(
          ([k]) =>
            global ||
            ![
              "manage_users",
              "auth_settings",
              "audit_view",
              "perform_updates",
            ].includes(k),
        )
        .map(([k, l]) => (
          <label className="check" key={k}>
            <input
              type="checkbox"
              checked={selected.includes(k)}
              onChange={() => toggle(k)}
            />
            {l}
          </label>
        ))}
    </div>
  );
}
function Access({
  actor,
  project,
  run,
  epoch,
  refresh,
}: {
  actor: User;
  project?: Project;
  run: Run;
  epoch: number;
  refresh: () => Promise<void>;
}) {
  const [users, setUsers] = useState<User[]>([]),
    [editorOpen, setEditorOpen] = useState(false),
    [members, setMembers] = useState<any[]>([]),
    [edit, setEdit] = useState<User | null>(null),
    [perms, setPerms] = useState<string[]>([]),
    [memberUser, setMemberUser] = useState(""),
    [memberRole, setMemberRole] = useState("viewer"),
    [memberPerms, setMemberPerms] = useState<string[]>([]);
  const load = async () => {
    setUsers(await api("users/"));
    if (project) setMembers(await api(`projects/${project.id}/memberships/`));
  };
  useEffect(() => {
    run(load);
  }, [project?.id, epoch]);
  return (
    <>
      <section className="panel">
        <SectionHeading
          title="کاربران سامانه"
          description="حساب‌ها، وضعیت و مجوزهای مستقل کاربران"
        >
          <button
            onClick={() => {
              setEdit(null);
              setPerms([]);
              setEditorOpen(!editorOpen);
            }}
          >
            تعریف کاربر جدید <Icon name="chevron" />
          </button>
        </SectionHeading>
        {editorOpen && (
          <>
            <h3>{edit ? "ویرایش حساب" : "حساب محلی جدید"}</h3>
            <form
              key={edit?.id || "new"}
              className="formgrid"
              onSubmit={(e) => {
                e.preventDefault();
                const d = Object.fromEntries(new FormData(e.currentTarget));
                run(async () => {
                  await api("users/", edit ? "PATCH" : "POST", {
                    ...d,
                    id: edit?.id,
                    is_active: d.is_active === "on",
                    is_admin: d.is_admin === "on",
                    permissions: perms,
                  });
                  setEdit(null);
                  setEditorOpen(false);
                  setPerms([]);
                  await load();
                  await refresh();
                });
              }}
            >
              <label>
                نام کاربری
                <input
                  name="username"
                  dir="ltr"
                  defaultValue={edit?.username}
                  required
                />
              </label>
              <label>
                نام نمایشی
                <input name="first_name" defaultValue={edit?.first_name} />
              </label>
              {
                <label>
                  {edit ? "رمز جدید (اختیاری)" : "رمز حساب"}
                  <input
                    type="password"
                    name="password"
                    minLength={12}
                    required={!edit}
                    autoComplete="new-password"
                  />
                </label>
              }
              <label className="check">
                <input
                  type="checkbox"
                  name="is_active"
                  defaultChecked={edit ? edit.is_active : true}
                />
                فعال
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  name="is_admin"
                  disabled={!actor.is_admin}
                  defaultChecked={edit?.is_admin}
                />
                مدیر سیستم
              </label>
              <div className="wide">
                <h3>مجوزهای مستقل</h3>
                <PermissionChecks
                  global
                  selected={perms}
                  toggle={(p) =>
                    setPerms(
                      perms.includes(p)
                        ? perms.filter((x) => x !== p)
                        : [...perms, p],
                    )
                  }
                />
              </div>
              <div className="actions">
                <button>ذخیره حساب</button>
                {edit && (
                  <button
                    className="ghost"
                    type="button"
                    onClick={() => {
                      setEdit(null);
                      setEditorOpen(false);
                      setPerms([]);
                    }}
                  >
                    لغو
                  </button>
                )}
              </div>
            </form>
          </>
        )}
        <h3>حساب‌های سامانه</h3>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>نام کاربری</th>
                <th>نام نمایشی</th>
                <th>وضعیت</th>
                <th>مجوزهای مستقل</th>
                <th>مدیریت</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td dir="ltr">{u.username}</td>
                  <td>{u.first_name || "—"}</td>
                  <td>
                    <span
                      className={
                        "badge " + (u.is_active ? "active" : "archived")
                      }
                    >
                      {u.is_admin
                        ? "مدیر سیستم"
                        : u.is_active
                          ? "فعال"
                          : "غیرفعال"}
                    </span>
                  </td>
                  <td>
                    {u.permissions.map((p) => permLabels[p] || p).join("، ") ||
                      "مجوز پروژه"}
                  </td>
                  <td>
                    <button
                      className="ghost"
                      disabled={u.is_admin && !actor.is_admin}
                      onClick={() => {
                        setEdit(u);
                        setPerms(u.permissions);
                        setEditorOpen(true);
                      }}
                    >
                      ویرایش
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {project && (
        <section className="panel">
          <h2>عضویت در {project.name}</h2>
          <form
            className="formgrid"
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                await api(`projects/${project.id}/memberships/`, "POST", {
                  user: Number(memberUser),
                  role: memberRole,
                  permissions: memberPerms,
                });
                await load();
                await refresh();
              });
            }}
          >
            <label>
              کاربر
              <select
                required
                value={memberUser}
                onChange={(e) => {
                  setMemberUser(e.target.value);
                  const m = members.find(
                    (x) => x.user_id === Number(e.target.value),
                  );
                  setMemberRole(m?.role || "viewer");
                  setMemberPerms(m?.permissions || []);
                }}
              >
                <option value="">انتخاب</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.username}
                  </option>
                ))}
              </select>
            </label>
            <label>
              نقش
              <select
                value={memberRole}
                onChange={(e) => setMemberRole(e.target.value)}
              >
                {Object.entries(roles).map(([k, l]) => (
                  <option key={k} value={k}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
            <div className="wide">
              <PermissionChecks
                selected={memberPerms}
                toggle={(p) =>
                  setMemberPerms(
                    memberPerms.includes(p)
                      ? memberPerms.filter((x) => x !== p)
                      : [...memberPerms, p],
                  )
                }
              />
            </div>
            <button>ذخیره عضویت</button>
          </form>
          {members.map((m) => (
            <div className="historyitem" key={m.id}>
              <span>
                {m.user__username} · {roles[m.role]} ·{" "}
                {m.permissions.map((p: string) => permLabels[p]).join("، ")}
              </span>
              <button
                className="danger"
                onClick={() =>
                  run(async () => {
                    await api(`projects/${project.id}/memberships/`, "POST", {
                      user: m.user_id,
                      role: m.role,
                      permissions: [],
                      remove: true,
                    });
                    await load();
                    await refresh();
                  })
                }
              >
                حذف عضویت
              </button>
            </div>
          ))}
        </section>
      )}
    </>
  );
}
function AuditPage({ run }: { run: Run }) {
  const auditLabels: Record<string, string> = {
    ...fields,
    disks: "دیسک‌ها",
    fields: "فیلدهای تغییرکرده",
    project: "شناسه پروژه",
    server_name: "نام ماشین",
    source: "منبع",
    activity: "شناسه فعالیت",
    scope: "دامنه",
    page: "صفحه",
    version: "نسخه",
    permissions: "مجوزها",
    is_active: "حساب فعال",
    is_admin: "مدیر سیستم",
    password_changed: "رمز تغییر کرده",
    user_id: "شناسه کاربر",
    name: "نام",
    previous: "مقدار قبلی",
    reason: "علت",
    counts: "نتیجه ورود",
    worksheet: "برگه",
    rows: "ردیف‌ها",
    issues: "موارد بررسی",
    type: "نوع فعالیت",
  };
  const displayValue = (value: any): string =>
    value === null || value === undefined
      ? "—"
      : typeof value === "boolean"
        ? value
          ? "بله"
          : "خیر"
        : typeof value === "object"
          ? JSON.stringify(value)
          : String(value);
  const [data, setData] = useState<any>(null),
    [category, setCategory] = useState(""),
    [username, setUsername] = useState(""),
    [search, setSearch] = useState(""),
    [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [page, setPage] = useState(1),
    [size, setSize] = useState(30),
    [detail, setDetail] = useState<any>(null);
  useEffect(() => {
    let live = true;
    const query = new URLSearchParams({
      category,
      user: username,
      search,
      from,
      to,
      page: String(page),
      page_size: String(size),
    });
    run(async () => {
      const value = await api("audit/?" + query);
      if (live) setData(value);
    });
    return () => {
      live = false;
    };
  }, [category, username, search, from, to, page, size]);
  return (
    <section className="panel">
      <SectionHeading
        title="رویدادهای سامانه"
        description="ردیابی کاربر، زمان و تغییرات؛ رویدادها قابل ویرایش نیستند."
      />
      <div className="filterbar">
        <label>
          دسته
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
          >
            <option value="">همه رویدادها</option>
            {Object.entries(categoryLabels).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          کاربر
          <input
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          عمل یا هدف
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          از تاریخ
          <input
            type="date"
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          تا تاریخ
          <input
            type="date"
            value={to}
            onChange={(e) => {
              setTo(e.target.value);
              setPage(1);
            }}
          />
        </label>
      </div>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>زمان</th>
              <th>کاربر</th>
              <th>عمل</th>
              <th>هدف</th>
              <th>جزئیات</th>
            </tr>
          </thead>
          <tbody>
            {data?.results.map((event: any) => (
              <Fragment key={event.id}>
                <tr>
                  <td>{time(event.created_at)}</td>
                  <td>
                    {event.user__username ||
                      event.metadata.username ||
                      "سامانه"}
                  </td>
                  <td>
                    <span className="badge">
                      {eventLabels[event.event] || event.event}
                    </span>
                  </td>
                  <td dir="ltr">{event.target || "—"}</td>
                  <td>
                    <button
                      className="ghost"
                      onClick={() =>
                        run(async () =>
                          setDetail(
                            detail?.id === event.id
                              ? null
                              : {
                                  id: event.id,
                                  ...(await api(`audit/${event.id}/`)),
                                },
                          ),
                        )
                      }
                    >
                      نمایش جزئیات
                    </button>
                  </td>
                </tr>
                {detail?.id === event.id && (
                  <tr>
                    <td colSpan={5}>
                      <div className="audit-detail">
                        <dl className="audit-meta">
                          {Object.entries(detail.metadata)
                            .filter(
                              ([key]) =>
                                key !== "fields" || !detail.changes.length,
                            )
                            .map(([key, value]) => (
                              <div key={key}>
                                <dt>{auditLabels[key] || key}</dt>
                                <dd>{displayValue(value)}</dd>
                              </div>
                            ))}
                        </dl>
                        {detail.changes.length > 0 && (
                          <table>
                            <thead>
                              <tr>
                                <th>فیلد</th>
                                <th>قبل</th>
                                <th>بعد</th>
                              </tr>
                            </thead>
                            <tbody>
                              {detail.changes.map((change: any, i: number) => (
                                <tr key={i}>
                                  <td>
                                    {auditLabels[change.field] || change.field}
                                  </td>
                                  <td>{displayValue(change.previous)}</td>
                                  <td>{displayValue(change.value)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {data && !data.count && (
        <div className="empty">رویدادی با این فیلتر پیدا نشد.</div>
      )}
      {data && (
        <Pager
          page={page}
          pages={data.pages}
          count={data.count}
          size={size}
          onPage={setPage}
          onSize={(value) => {
            setSize(value);
            setPage(1);
          }}
        />
      )}
    </section>
  );
}
function Settings({
  user,
  run,
  notice,
}: {
  user: User;
  run: Run;
  notice: (s: string) => void;
}) {
  const [updates, setUpdates] = useState<any>(null),
    [uploading, setUploading] = useState(false);
  const canUpdate =
      user.is_admin || user.permissions.includes("perform_updates"),
    uploadBusy =
      uploading ||
      updates?.uploads?.some((item: any) =>
        ["pending", "processing"].includes(item.status),
      );
  const load = async () => {
    if (canUpdate) setUpdates(await api("updates/"));
  };
  useEffect(() => {
    run(load);
    const timer = setInterval(() => {
      if (canUpdate)
        api("updates/")
          .then(setUpdates)
          .catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, []);
  return (
    <>
      {updates && (
        <section className="panel">
          <div className="sectionhead">
            <h2>مرکز به‌روزرسانی</h2>
            <span className="badge" dir="ltr">
              v{updates.installed}
            </span>
          </div>
          <p>
            فقط بسته آفلاین کپی‌شده و امضاشده؛ اجرا توسط سرویس مستقل محدود، خارج
            از درخواست وب.
          </p>
          <form
            className="upload-zone"
            onSubmit={(event) => {
              event.preventDefault();
              const form = event.currentTarget;
              const body = new FormData(form);
              setUploading(true);
              run(async () => {
                try {
                  const received = await api("updates/upload/", "POST", body);
                  notice(
                    `بسته نسخه ${received.version} دریافت شد؛ در حال بررسی روی سرور`,
                  );
                  form.reset();
                  await load();
                } finally {
                  setUploading(false);
                }
              });
            }}
          >
            <SectionHeading
              title="بارگذاری نسخه جدید"
              description="بسته ZIP رسمی و امضاشده را انتخاب کنید. پس از تأیید نسخه، نصب را از همین صفحه شروع کنید."
            />
            <label>
              فایل انتشار
              <input
                type="file"
                name="file"
                accept=".zip"
                required
                disabled={uploadBusy || !updates.execution_enabled}
              />
            </label>
            <button disabled={uploadBusy || !updates.execution_enabled}>
              {uploading ? "در حال بارگذاری…" : "بارگذاری و بررسی بسته"}
            </button>
          </form>
          {updates.uploads?.length > 0 && (
            <>
              <h3>تاریخچه بسته‌های بارگذاری‌شده</h3>
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>
                      <th>نسخه</th>
                      <th>کاربر</th>
                      <th>زمان</th>
                      <th>وضعیت</th>
                      <th>نتیجه</th>
                    </tr>
                  </thead>
                  <tbody>
                    {updates.uploads.map((item: any) => (
                      <tr key={item.id}>
                        <td dir="ltr">{item.version}</td>
                        <td>{item.user__username}</td>
                        <td>{time(item.updated_at)}</td>
                        <td>
                          <span
                            className={
                              "badge " +
                              (item.status === "ready"
                                ? "active"
                                : item.status === "failed"
                                  ? "failed"
                                  : "pending")
                            }
                          >
                            {(
                              {
                                pending: "در صف بررسی",
                                processing: "در حال تأیید",
                                ready: "آماده نصب",
                                failed: "ناموفق",
                              } as Record<string, string>
                            )[item.status] || item.status}
                          </span>
                        </td>
                        <td>{item.error || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          <button
            onClick={() =>
              run(async () => {
                await api("updates/", "POST", { action: "check" });
                await load();
                notice("بررسی انتشار تکمیل شد");
              })
            }
          >
            بررسی بسته آفلاین
          </button>
          {updates.available && (
            <article className="previewrow">
              <h3 dir="ltr">{updates.available.version}</h3>
              <p>{updates.available.notes}</p>
              <pre>
                {JSON.stringify(updates.available.compatibility, null, 2)}
              </pre>
              <small>آخرین بررسی: {time(updates.available.checked_at)}</small>
              <div className="actions">
                <button
                  disabled={!updates.execution_enabled}
                  onClick={() =>
                    run(async () => {
                      await api("updates/", "POST", {
                        action: "install",
                        version: updates.available.version,
                      });
                      await load();
                    })
                  }
                >
                  نصب انتشار انتخاب‌شده
                </button>
              </div>
            </article>
          )}
          {!updates.execution_enabled && (
            <div className="warning">
              اجرای به‌روزرسانی فعال نیست. اتصال سرویس مستقل، مخزن و کلید عمومی
              امضا باید در فاز استقرار انجام شود.
            </div>
          )}
          <h3>اجراهای ثبت‌شده</h3>
          {updates.runs.map((r: any) => (
            <article className="historyitem" key={r.id}>
              <b>
                <span dir="ltr">
                  {r.from_version} → {r.to_version}
                </span>{" "}
                ·{" "}
                <span
                  className={
                    "badge " +
                    (r.status === "completed"
                      ? "active"
                      : r.status === "failed"
                        ? "failed"
                        : "pending")
                  }
                >
                  {(
                    {
                      queued: "در صف نصب",
                      running: "در حال نصب",
                      completed: "تکمیل‌شده",
                      failed: "ناموفق",
                    } as Record<string, string>
                  )[r.status] || r.status}
                </span>
              </b>
              <span>
                {r.user__username} · {time(r.updated_at)}
              </span>
              <p>پشتیبان: {r.backup_path || "هنوز ایجاد نشده"}</p>
              <ol>
                {r.progress.map((s: string, i: number) => (
                  <li key={i}>
                    {(
                      {
                        integrity_verified: "تأیید امضا و یکپارچگی",
                        preflight_passed: "بررسی پیش‌نیازها",
                        full_snapshot_complete: "تهیه پشتیبان کامل",
                        backup_complete: "پشتیبان پایگاه داده آماده شد",
                        staged: "آماده‌سازی نسخه",
                        images_ready: "آماده‌سازی سرویس‌ها",
                        migrations_complete: "به‌روزرسانی ساختار پایگاه داده",
                        services_restarted: "اجرای سرویس‌های جدید",
                        healthy: "تأیید سلامت سامانه",
                      } as Record<string, string>
                    )[s] || s}
                  </li>
                ))}
              </ol>
              {r.error && <p className="error">{r.error}</p>}
              {r.status === "failed" && (
                <button
                  disabled={!updates.execution_enabled}
                  onClick={() =>
                    run(async () => {
                      await api("updates/", "POST", {
                        action: "retry",
                        version: r.to_version,
                      });
                      await load();
                    })
                  }
                >
                  تلاش دوباره
                </button>
              )}
            </article>
          ))}
          {!updates.runs.length && (
            <div className="empty compact-empty">
              هنوز نصبی از این صفحه ثبت نشده است.
            </div>
          )}
          <h3>کنترل‌های نصب</h3>
          <p>
            پیش از نصب پشتیبان کامل تهیه می‌شود. امضای معتبر، نسخه جدیدتر،
            سازگاری و سلامت سرویس‌ها بررسی می‌شوند. در صورت شکست، پشتیبان و
            گزارش مراحل حفظ می‌شوند؛ بازیابی پایگاه داده با تصمیم مدیر انجام
            می‌شود.
          </p>
        </section>
      )}
    </>
  );
}
createRoot(document.getElementById("root")!).render(<App />);

function ManagementReports({
  projects,
  epoch,
  run,
  notice,
}: {
  projects: Project[];
  epoch: number;
  run: Run;
  notice: (s: string) => void;
}) {
  const [pid, setPid] = useState(0);
  const [env, setEnv] = useState("");
  const [detailPage, setDetailPage] = useState(1);
  const [detailSize, setDetailSize] = useState(30);
  const [reportTab, setReportTab] = useState("overview");
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const project = projects.find((p) => p.id === pid) || null;
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setReport(null);
    const query = new URLSearchParams();
    if (pid) query.set("project", String(pid));
    if (env) query.set("environment", env);
    query.set("page", String(detailPage));
    query.set("page_size", String(detailSize));
    api("reports/?" + query)
      .then((data) => {
        if (active) setReport(data);
      })
      .catch((e) => {
        if (active) setError(String(e.message));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [pid, env, epoch, revision, detailPage, detailSize]);
  const number = (value: any) => Number(value || 0).toLocaleString("fa-IR");
  const label = (row: any) =>
    row.environment__name ||
    row.application__name ||
    row.project__name ||
    row.os ||
    "ثبت‌نشده";
  const chart = (rows: any[], key: string, title: string, unit: string) => (
    <BarChart
      title={title}
      unit={unit}
      values={rows.map((row) => ({
        label: label(row),
        value: Number(row[key]),
      }))}
    />
  );
  const table = (title: string, rows: any[], getName: (row: any) => string) => (
    <section className="panel">
      <h3>{title}</h3>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>عنوان</th>
              <th>ماشین</th>
              <th>CPU (Core)</th>
              <th>RAM (GB)</th>
              <th>Disk (GB)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td>{getName(row)}</td>
                <td>{number(row.machines)}</td>
                <td>{number(row.cpu)}</td>
                <td>{number(row.ram)}</td>
                <td>{number(row.disk)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p>رکوردی وجود ندارد.</p>}
      </div>
    </section>
  );
  return (
    <section>
      <div className="sectionhead">
        <h2>داشبورد گزارش مدیریتی</h2>
        <button className="ghost" onClick={() => setRevision((r) => r + 1)}>
          تازه‌سازی گزارش
        </button>
      </div>
      <p>
        فقط پروژه‌های مجاز شما؛ منابع تخصیص‌یافته از موجودی ثبت‌شده، بدون پایش
        زنده. موارد ناقص شاخص کیفیت اطلاعات هستند، نه سلامت زیرساخت.
      </p>
      <div className="formgrid">
        <label>
          پروژه گزارش
          <select
            aria-label="پروژه گزارش"
            value={pid}
            onChange={(e) => {
              setPid(Number(e.target.value));
              setEnv("");
              setDetailPage(1);
            }}
          >
            <option value={0}>همه پروژه‌های مجاز</option>
            {projects
              .filter((p) => !p.archived)
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
          </select>
        </label>
        <label>
          محیط گزارش
          <select
            aria-label="محیط گزارش"
            value={env}
            disabled={!project}
            onChange={(e) => {
              setEnv(e.target.value);
              setDetailPage(1);
            }}
          >
            <option value="">همه محیط‌ها</option>
            {project?.environments
              .filter((e) => !e.archived)
              .map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
          </select>
        </label>
      </div>
      {loading && <p role="status">در حال محاسبه گزارش…</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {report && (
        <>
          <p>
            زمان تهیه: {time(report.generated_at)} ·{" "}
            {project ? project.name : "کل پروژه‌های مجاز"}
          </p>
          <div
            className="tabs report-tabs"
            role="tablist"
            aria-label="دسته گزارش"
          >
            {[
              ["overview", "نمودارها و منابع"],
              ["groups", "تفکیک منابع"],
              ["machines", "فهرست ماشین‌ها"],
              ["quality", "کیفیت و فعالیت"],
            ].map(([key, title]) => (
              <button
                key={key}
                role="tab"
                aria-selected={reportTab === key}
                className={reportTab === key ? "selected" : ""}
                onClick={() => setReportTab(key)}
              >
                {title}
              </button>
            ))}
          </div>
          <div className="metrics">
            {[
              [report.project_count, "پروژه"],
              [report.environment_count, "محیط"],
              [report.totals.machines, "ماشین"],
              [report.disk_count, "دیسک"],
              [report.totals.cpu, "CPU (Core)"],
              [report.totals.ram, "RAM (GB)"],
              [report.totals.disk, "Disk (GB)"],
            ].map(([value, name]) => (
              <MetricCard
                key={String(name)}
                label={String(name)}
                value={value}
                tone={
                  ["blue", "teal", "violet", "amber"][String(name).length % 4]
                }
              />
            ))}
          </div>
          {reportTab === "overview" && (
            <>
              <div className="graphs">
                {chart(
                  project ? report.environments : report.projects,
                  "cpu",
                  project ? "CPU به تفکیک محیط" : "CPU به تفکیک پروژه",
                  "Core",
                )}
                {chart(
                  project ? report.environments : report.projects,
                  "ram",
                  project ? "RAM به تفکیک محیط" : "RAM به تفکیک پروژه",
                  "GB",
                )}
                {chart(
                  project ? report.environments : report.projects,
                  "disk",
                  project ? "دیسک به تفکیک محیط" : "دیسک به تفکیک پروژه",
                  "GB",
                )}
              </div>
              <div className="graphs">
                {chart(
                  report.operating_systems,
                  "machines",
                  "توزیع سیستم‌عامل",
                  "ماشین",
                )}
                {chart(
                  [...report.services]
                    .sort((a: any, b: any) => b.machines - a.machines)
                    .slice(0, 20),
                  "machines",
                  "۲۰ سرویس با بیشترین ماشین",
                  "ماشین",
                )}
              </div>
              <DonutChart
                title="توزیع وضعیت گردش کار"
                values={report.statuses.map((item: any) => ({
                  label: statusLabels[item.status],
                  value: item.machines,
                }))}
              />
            </>
          )}
          {reportTab === "groups" && (
            <>
              {table(
                "جزئیات پروژه‌ها",
                report.projects,
                (r) => r.project__name,
              )}
              {table(
                "جزئیات محیط‌ها",
                report.environments,
                (r) => `${r.project__name} / ${r.environment__name}`,
              )}
              {table(
                "سرویس‌ها و Applicationها",
                report.services,
                (r) =>
                  `${r.project__name} / ${r.application__name || "ثبت‌نشده"}`,
              )}
              {table(
                "سیستم‌عامل‌ها",
                report.operating_systems,
                (r) => r.os || "ثبت‌نشده",
              )}
              {table(
                "شبکه‌ها",
                report.networks,
                (r) =>
                  `${r.project__name} / ${r.environment__name} / ${r.network || "ثبت‌نشده"}`,
              )}
            </>
          )}
          {reportTab === "machines" && (
            <section className="panel">
              <h3>جزئیات ماشین‌ها</h3>
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>
                      <th>پروژه</th>
                      <th className="sticky">Server Name</th>
                      <th>Environment</th>
                      <th>Application</th>
                      <th>VMs</th>
                      <th>CPU (Core)</th>
                      <th>RAM (GB)</th>
                      {Array.from(
                        {
                          length: Math.max(
                            0,
                            ...report.machines.map((m: any) => m.disks.length),
                          ),
                        },
                        (_, i) => (
                          <th key={i}>Disk {i + 1} (GB)</th>
                        ),
                      )}
                      <th>OS</th>
                      <th>Network / VLAN</th>
                      <th>Server IP Addr</th>
                      <th>Subnet (CIDR)</th>
                      <th>GW IP Addr</th>
                      <th>Username</th>
                      <th>وضعیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.machines.map((m: any) => (
                      <tr key={m.id}>
                        <td>{m.project_name}</td>
                        <td className="sticky">{m.server_name}</td>
                        <td>{m.environment_name}</td>
                        <td>{m.application}</td>
                        <td>{m.vms}</td>
                        <td>{number(m.cpu)}</td>
                        <td>{number(m.ram)}</td>
                        {Array.from(
                          {
                            length: Math.max(
                              0,
                              ...report.machines.map(
                                (row: any) => row.disks.length,
                              ),
                            ),
                          },
                          (_, i) => (
                            <td key={i} title={m.disks[i]?.name}>
                              {m.disks[i] ? number(m.disks[i].size) : "—"}
                            </td>
                          ),
                        )}
                        <td>{m.os}</td>
                        <td>{m.network}</td>
                        <td>{m.ip}</td>
                        <td>{m.subnet}</td>
                        <td>{m.gateway}</td>
                        <td>{m.username}</td>
                        <td>{statusLabels[m.status]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pager
                page={report.page}
                pages={report.pages}
                count={report.totals.machines}
                size={detailSize}
                onPage={setDetailPage}
                onSize={(value) => {
                  setDetailSize(value);
                  setDetailPage(1);
                }}
              />
            </section>
          )}
          {reportTab === "quality" && (
            <>
              <section className="panel">
                <h3>کیفیت تکمیل موجودی</h3>
                <div className="quality-grid">
                  {Object.entries({
                    missing_ip: "IP ثبت‌نشده",
                    missing_subnet: "Subnet ثبت‌نشده",
                    missing_os: "OS ثبت‌نشده",
                    missing_application: "Application ثبت‌نشده",
                    without_disks: "ماشین بدون دیسک",
                    zero_resources: "CPU یا RAM صفر",
                    duplicate_ip_contexts: "گروه IP تکراری در پروژه/محیط/شبکه",
                  }).map(([key, title]) => (
                    <MetricCard
                      key={key}
                      label={title}
                      value={report.quality[key]}
                      tone={report.quality[key] ? "amber" : "teal"}
                    />
                  ))}
                </div>
              </section>
              <section className="panel">
                <h3>فعالیت ۳۰ روز اخیر</h3>
                {report.activity_30_days.map((row: any, i: number) => (
                  <p key={i}>
                    {row.event} · {row.source}: {number(row.count)}
                  </p>
                ))}
                {!report.activity_30_days.length && (
                  <p>فعالیتی ثبت نشده است.</p>
                )}
              </section>
            </>
          )}
        </>
      )}
      <Exports
        project={project}
        projects={projects}
        run={run}
        notice={notice}
      />
    </section>
  );
}
