import React, { useEffect, useRef, useState } from "react";
import { api, statusLabels, time } from "./api";
import {
  Icon,
  MetricCard,
  BarChart,
  DonutChart,
  SectionHeading,
  number,
} from "./design";
type ProjectSummary = {
  id: number;
  name: string;
  description?: string;
  archived: boolean;
  role: string;
  environments: { id: number; name: string; archived: boolean }[];
};
type Run = (fn: () => Promise<void>) => Promise<void>;
export function ProjectSelector({
  label,
  projects,
  value,
  select,
}: {
  label: string;
  projects: ProjectSummary[];
  value: number;
  select: (id: number) => void;
}) {
  return (
    <section className="panel project-selector">
      <Icon name="projects" size={28} />
      <label>
        {label}
        <select
          aria-label={label}
          value={projects.some((p) => p.id === value) ? value : 0}
          onChange={(e) => select(Number(e.target.value))}
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
    </section>
  );
}
export function ProjectPicker({
  projects,
  selected,
  select,
}: {
  projects: ProjectSummary[];
  selected: number;
  select: (id: number) => void;
}) {
  return (
    <section className="panel">
      <SectionHeading
        title="پروژه‌ها"
        description="یک پروژه را انتخاب کنید تا منابع و ماشین‌های آن نمایش داده شود."
      />
      <div className="project-switcher">
        {projects
          .filter((p) => !p.archived)
          .map((project) => (
            <button
              key={project.id}
              className={selected === project.id ? "selected" : ""}
              onClick={() => select(project.id)}
            >
              <Icon name="projects" />
              <span>
                {project.name}
                <small>
                  {number(
                    project.environments.filter((e) => !e.archived).length,
                  )}{" "}
                  محیط
                </small>
              </span>
            </button>
          ))}
      </div>
      {!projects.length && (
        <div className="empty">هنوز پروژه‌ای در دسترس شما نیست.</div>
      )}
    </section>
  );
}
export function Dashboard({
  epoch,
  projects,
  openProject,
}: {
  epoch: number;
  projects: ProjectSummary[];
  openProject: (id: number) => void;
}) {
  const [report, setReport] = useState<any>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    api("reports/?summary=1")
      .then((value) => {
        if (live) setReport(value);
      })
      .catch((error) => {
        if (live) setError(error.message);
      });
    return () => {
      live = false;
    };
  }, [epoch]);
  if (error)
    return (
      <div className="error" role="alert">
        {error}
      </div>
    );
  if (!report)
    return (
      <div className="empty" role="status">
        در حال تهیه نمای کلی زیرساخت…
      </div>
    );
  const values = (key: string) =>
    report.projects
      .slice(0, 12)
      .map((p: any) => ({ label: p.project__name, value: Number(p[key]) }));
  return (
    <>
      <SectionHeading
        title="نمای کلی زیرساخت"
        description={`جمع منابع تمام پروژه‌های مجاز شما · ${time(report.generated_at)}`}
      />
      <div className="metrics">
        <MetricCard
          label="پروژه‌های فعال"
          value={report.project_count}
          icon="projects"
        />
        <MetricCard
          label="کل ماشین‌ها"
          value={report.totals.machines}
          icon="inventory"
          tone="teal"
        />
        <MetricCard
          label="محیط‌ها"
          value={report.environment_count}
          icon="dashboard"
          tone="violet"
        />
        <MetricCard
          label="دیسک‌های ثبت‌شده"
          value={report.disk_count}
          icon="disk"
          tone="amber"
        />
        <MetricCard
          label="هسته‌های پردازشی"
          value={report.totals.cpu}
          unit="Core"
          icon="cpu"
        />
        <MetricCard
          label="حافظه تخصیص‌یافته"
          value={report.totals.ram}
          unit="GB"
          icon="inventory"
          tone="teal"
        />
        <MetricCard
          label="فضای دیسک"
          value={report.totals.disk}
          unit="GB"
          icon="disk"
          tone="violet"
        />
        <MetricCard
          label="سرویس‌ها"
          value={report.services.filter((s: any) => s.application_id).length}
          icon="reports"
          tone="amber"
        />
      </div>
      <div className="dashboard-layout">
        <BarChart
          title="CPU به تفکیک پروژه"
          unit="Core"
          values={values("cpu")}
        />
        <BarChart title="RAM به تفکیک پروژه" unit="GB" values={values("ram")} />
        <BarChart
          title="دیسک به تفکیک پروژه"
          unit="GB"
          values={values("disk")}
        />
        <DonutChart
          title="وضعیت ماشین‌ها"
          values={report.statuses.map((s: any) => ({
            label: statusLabels[s.status],
            value: s.machines,
          }))}
        />
      </div>
      <section className="panel" style={{ marginTop: 22 }}>
        <SectionHeading
          title="پروژه‌های زیرساخت"
          description="منابع هر پروژه و دسترسی مستقیم به ماشین‌ها"
        />
        <div className="project-card-grid">
          {projects
            .filter((p) => !p.archived)
            .map((project) => {
              const counts =
                report.projects.find((p: any) => p.project_id === project.id) ||
                {};
              return (
                <article className="project-card" key={project.id}>
                  <h3>{project.name}</h3>
                  <p className="muted">
                    {project.description || "موجودی و منابع پروژه"}
                  </p>
                  <div className="project-counts">
                    <span>{number(counts.machines)} ماشین</span>
                    <span>{number(counts.cpu)} Core</span>
                    <span>{number(counts.ram)} GB RAM</span>
                  </div>
                  <button
                    className="ghost"
                    onClick={() => openProject(project.id)}
                  >
                    نمایش پروژه و VM ها
                  </button>
                </article>
              );
            })}
        </div>
      </section>
      <div className="dashboard-layout">
        <BarChart
          title="توزیع سیستم‌عامل‌ها"
          unit="ماشین"
          values={report.operating_systems
            .slice(0, 12)
            .map((item: any) => ({
              label: item.os || "ثبت‌نشده",
              value: item.machines,
            }))}
        />
        <BarChart
          title="محیط‌های زیرساخت"
          unit="ماشین"
          values={report.environments
            .slice(0, 12)
            .map((item: any) => ({
              label: `${item.project__name} / ${item.environment__name}`,
              value: item.machines,
            }))}
        />
      </div>
    </>
  );
}
export function PasswordDialog({
  run,
  close,
  notice,
}: {
  run: Run;
  close: () => void;
  notice: (message: string) => void;
}) {
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    dialog.current?.querySelector<HTMLInputElement>("input")?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "Tab") {
        const elements = Array.from(
          dialog.current?.querySelectorAll<HTMLElement>("input,button") || [],
        );
        if (e.shiftKey && document.activeElement === elements[0]) {
          e.preventDefault();
          elements.at(-1)?.focus();
        } else if (!e.shiftKey && document.activeElement === elements.at(-1)) {
          e.preventDefault();
          elements[0]?.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      before?.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop">
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-label="تغییر رمز حساب"
        ref={dialog}
      >
        <SectionHeading
          title="تغییر رمز حساب"
          description="رمز جدید فقط برای حساب واردشده اعمال می‌شود."
        />
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const values = Object.fromEntries(new FormData(e.currentTarget));
            if (values.new_password !== values.confirm_password) {
              setError("تکرار رمز جدید یکسان نیست");
              return;
            }
            run(async () => {
              try {
                await api("password/", "POST", {
                  old_password: values.old_password,
                  new_password: values.new_password,
                });
                notice("رمز حساب تغییر کرد");
                close();
              } catch (error) {
                setError((error as Error).message);
                throw error;
              }
            });
          }}
        >
          <label>
            رمز فعلی
            <input
              type="password"
              name="old_password"
              autoComplete="current-password"
              required
            />
          </label>
          <label>
            رمز جدید
            <input
              type="password"
              name="new_password"
              autoComplete="new-password"
              required
              minLength={12}
            />
          </label>
          <label>
            تکرار رمز جدید
            <input
              type="password"
              name="confirm_password"
              autoComplete="new-password"
              required
              minLength={12}
            />
          </label>
          <div className="actions">
            <button>ذخیره رمز جدید</button>
            <button type="button" className="ghost" onClick={close}>
              بستن
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
