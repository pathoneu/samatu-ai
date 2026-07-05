/**
 * AnalyticsCharts — small-multiples of the daily operational series:
 * Registracijos (signups), Projektai, Ekstrakcijos. Each is its own area
 * chart with real dates, a faint grid, orange emphasis + area fill.
 *
 * Uses analytics.series (densified so the x-axis is a continuous calendar).
 */
import React from 'react';
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { SectionHead, Panel, EmptyLine, ErrorLine, BlockSkeleton } from './adminPrimitives';
import { fmtInt, fmtAxisDate, densifySeries } from './adminUtils';

const ORANGE = 'hsl(22 93% 54%)';
const NEUTRAL = 'hsl(215 11% 59%)';
const GRID = 'hsl(220 15% 19%)';

function MiniTooltip({ active, payload, label, unitLabel }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border/60 bg-background px-3 py-2 text-xs shadow-xl">
      <div className="font-medium text-foreground mb-1">{label}</div>
      <div className="flex items-center justify-between gap-4 tabular-nums">
        <span className="text-muted-foreground">{unitLabel}</span>
        <span className="font-mono text-primary">{fmtInt(payload[0].value)}</span>
      </div>
    </div>
  );
}

function MiniAreaChart({ data, dataKey, gradId, unitLabel }) {
  const total = data.reduce((s, r) => s + (Number(r[dataKey]) || 0), 0);

  return (
    <Panel className="p-4">
      <div className="flex items-baseline justify-between mb-2">
        <span className="skyrius-header">{unitLabel}</span>
        <span
          className="tabular-nums text-foreground"
          style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 600 }}
        >
          {fmtInt(total)}
        </span>
      </div>
      {total === 0 ? (
        <div style={{ height: 140 }} className="flex items-center">
          <EmptyLine>Nėra duomenų.</EmptyLine>
        </div>
      ) : (
        <div style={{ height: 140 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 6, left: -12, bottom: 0 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={ORANGE} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={ORANGE} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={fmtAxisDate}
                tick={{ fill: NEUTRAL, fontSize: 9 }}
                tickLine={false}
                axisLine={{ stroke: GRID }}
                minTickGap={28}
              />
              <YAxis
                tick={{ fill: NEUTRAL, fontSize: 9 }}
                tickLine={false}
                axisLine={false}
                width={28}
                allowDecimals={false}
              />
              <Tooltip
                content={<MiniTooltip unitLabel={unitLabel} />}
                cursor={{ stroke: GRID }}
              />
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={ORANGE}
                strokeWidth={2}
                fill={`url(#${gradId})`}
                dot={false}
                activeDot={{ r: 3, fill: ORANGE }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}

export default function AnalyticsCharts({ analytics, loading, error, days }) {
  return (
    <section>
      <SectionHead
        eyebrow="Analitika"
        title="Aktyvumas per dieną"
        hint="Registracijos, projektai ir ekstrakcijos pasirinktu laikotarpiu."
      />

      {error && <ErrorLine message={error} />}

      {loading && !analytics && !error && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <BlockSkeleton key={i} height={140} />
          ))}
        </div>
      )}

      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(() => {
            const data = densifySeries(analytics.series, days);
            return (
              <>
                <MiniAreaChart data={data} dataKey="signups"     gradId="gSignups"  unitLabel="Registracijos" />
                <MiniAreaChart data={data} dataKey="projects"    gradId="gProjects" unitLabel="Projektai" />
                <MiniAreaChart data={data} dataKey="extractions" gradId="gExtract"  unitLabel="Ekstrakcijos" />
              </>
            );
          })()}
        </div>
      )}
    </section>
  );
}
