import React from "react";

export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    dashboard: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="11" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="18" width="7" height="3" rx="1" />
      </>
    ),
    inventory: (
      <>
        <rect x="3" y="3" width="18" height="7" rx="2" />
        <rect x="3" y="14" width="18" height="7" rx="2" />
        <path d="M7 6.5h.01M7 17.5h.01M11 6.5h6M11 17.5h6" />
      </>
    ),
    projects: (
      <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" />
    ),
    imports: (
      <>
        <path d="M12 3v12m-4-4 4 4 4-4M4 15v5h16v-5" />
      </>
    ),
    exports: (
      <>
        <path d="M12 15V3m-4 4 4-4 4 4M4 15v5h16v-5" />
      </>
    ),
    reports: (
      <>
        <path d="M4 20h16M7 16v-5m5 5V4m5 12V8" />
      </>
    ),
    access: (
      <>
        <circle cx="9" cy="7" r="3" />
        <path d="M3 21v-3a6 6 0 0 1 12 0v3m2-17a3 3 0 0 1 0 6m2 5a5 5 0 0 1 2 4v2" />
      </>
    ),
    audit: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    settings: (
      <>
        <path d="m12 2 2 3 4-1 1 4 3 2-2 3 1 4-4 1-2 3-3-2-4 1-1-4-3-2 2-3-1-4 4-1Z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    user: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 22v-2a8 8 0 0 1 16 0v2" />
      </>
    ),
    cpu: (
      <>
        <rect x="6" y="6" width="12" height="12" rx="2" />
        <path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4" />
      </>
    ),
    disk: (
      <>
        <rect x="3" y="6" width="18" height="13" rx="3" />
        <path d="M3 14h18M16 17h.01M19 17h.01" />
      </>
    ),
    chevron: <path d="m7 10 5 5 5-5" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.dashboard}
    </svg>
  );
}

export const number = (value: unknown) =>
  Number(value || 0).toLocaleString("fa-IR");
export function MetricCard({
  label,
  value,
  unit = "",
  icon = "dashboard",
  tone = "blue",
}: {
  label: string;
  value: unknown;
  unit?: string;
  icon?: string;
  tone?: string;
}) {
  return (
    <article className={"metric metric-" + tone}>
      <div className="metric-heading">
        <span>{label}</span>
        <span className="metric-icon">
          <Icon name={icon} />
        </span>
      </div>
      <strong>
        {number(value)} <small>{unit}</small>
      </strong>
      <span className="metric-caption">موجودی ثبت‌شده</span>
    </article>
  );
}
export function SectionHeading({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="sectionhead">
      <div>
        <h2>{title}</h2>
        {description && <p className="muted">{description}</p>}
      </div>
      <div className="actions">{children}</div>
    </div>
  );
}
export type ChartValue = { label: string; value: number };
export function BarChart({
  title,
  values,
  unit = "",
  compact = false,
}: {
  title: string;
  values: ChartValue[];
  unit?: string;
  compact?: boolean;
}) {
  const max = Math.max(1, ...values.map((v) => v.value));
  return (
    <section className={"panel chart-card " + (compact ? "compact-chart" : "")}>
      <div className="chart-heading">
        <h3>{title}</h3>
        <small>{unit}</small>
      </div>
      {values.length ? (
        <div className="chart-bars">
          {values.map((v, i) => (
            <div className="barrow" key={i}>
              <span title={v.label}>{v.label}</span>
              <div className="bartrack">
                <i
                  style={{
                    width: `${Math.max(0, (100 * v.value) / max)}%`,
                    background: `var(--chart-${(i % 5) + 1})`,
                  }}
                />
              </div>
              <strong>{number(v.value)}</strong>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty compact-empty">هنوز داده‌ای ثبت نشده است</div>
      )}
    </section>
  );
}
export function DonutChart({
  title,
  values,
}: {
  title: string;
  values: ChartValue[];
}) {
  const total = values.reduce((sum, item) => sum + item.value, 0);
  let offset = 0;
  return (
    <section className="panel chart-card">
      <h3>{title}</h3>
      <div className="donut-layout">
        <svg
          viewBox="0 0 160 160"
          className="donut"
          role="img"
          aria-label={`${title}: ${number(total)}`}
        >
          <circle
            cx="80"
            cy="80"
            r="54"
            fill="none"
            stroke="var(--line)"
            strokeWidth="18"
          />
          {values.map((item, i) => {
            const length = total ? (item.value / total) * 339.292 : 0;
            const position = offset;
            offset += length;
            return (
              <circle
                key={i}
                cx="80"
                cy="80"
                r="54"
                fill="none"
                stroke={`var(--chart-${(i % 5) + 1})`}
                strokeWidth="18"
                strokeDasharray={`${length} ${339.292 - length}`}
                strokeDashoffset={-position}
                transform="rotate(-90 80 80)"
              />
            );
          })}
          <text x="80" y="77" textAnchor="middle" className="donut-total">
            {number(total)}
          </text>
          <text x="80" y="98" textAnchor="middle" className="donut-label">
            ماشین
          </text>
        </svg>
        <div className="chart-legend">
          {values.map((item, i) => (
            <div key={i}>
              <i style={{ background: `var(--chart-${(i % 5) + 1})` }} />
              <span>{item.label}</span>
              <strong>{number(item.value)}</strong>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
export function Pager({
  page,
  pages,
  count,
  size,
  onPage,
  onSize,
}: {
  page: number;
  pages: number;
  count: number;
  size: number;
  onPage: (value: number) => void;
  onSize?: (value: number) => void;
}) {
  return (
    <div className="pagination">
      <div className="pagination-summary">
        {number(count)} رکورد{" "}
        {onSize && (
          <label className="compact">
            نمایش در هر صفحه
            <select
              aria-label="تعداد در هر صفحه"
              value={size}
              onChange={(e) => onSize(Number(e.target.value))}
            >
              {[30, 50, 100].map((n) => (
                <option key={n} value={n}>
                  {number(n)}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <div className="actions">
        <button
          className="ghost"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          قبلی
        </button>
        <span>
          صفحه {number(page)} از {number(Math.max(1, pages))}
        </span>
        <button
          className="ghost"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          بعدی
        </button>
      </div>
    </div>
  );
}
