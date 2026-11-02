import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from "recharts";
import { money } from "../lib/format";

// Validated palette (light mode): series-1 blue, series-2 orange; sequential = blue.
const S1 = "#2a78d6", S2 = "#eb6834", GRID = "#e5e7eb", AXIS = "#6b7280";
const tip = { contentStyle: { borderRadius: 8, border: "1px solid #e2e5e9", fontSize: 12 }, formatter: (v) => money(v) };
const k = (v) => `$${Math.round(v / 1000)}k`;
const monthLabel = (m) => new Date(m + "-15").toLocaleString("en-CA", { month: "short" });

export function CashflowChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={190}>
      <BarChart data={data} margin={{ top: 6, right: 6, left: -12, bottom: 0 }} barGap={2}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="month" tickFormatter={monthLabel} stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} />
        <YAxis tickFormatter={k} stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} />
        <Tooltip {...tip} labelFormatter={monthLabel} cursor={{ fill: "#f3f4f6" }} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="in" name="Money in" fill={S1} radius={[4, 4, 0, 0]} maxBarSize={22} />
        <Bar dataKey="out" name="Money out" fill={S2} radius={[4, 4, 0, 0]} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// One measure (spend) across categories: a single sequential hue, sorted bars.
export function SpendingChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(150, data.length * 30 + 20)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 4, bottom: 0 }}>
        <CartesianGrid stroke={GRID} horizontal={false} />
        <XAxis type="number" tickFormatter={(v) => `$${v}`} stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} />
        <YAxis type="category" dataKey="category" width={92} stroke={AXIS} fontSize={11.5} tickLine={false} axisLine={false} />
        <Tooltip {...tip} cursor={{ fill: "#f3f4f6" }} />
        <Bar dataKey="amount" name="Spend" fill={S1} radius={[0, 4, 4, 0]} maxBarSize={16} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function PerformanceChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={190}>
      <LineChart data={data} margin={{ top: 6, right: 10, left: -6, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="month" tickFormatter={monthLabel} stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} />
        <YAxis tickFormatter={k} stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} domain={["dataMin - 2000", "dataMax + 2000"]} />
        <Tooltip {...tip} labelFormatter={monthLabel} />
        <Line type="monotone" dataKey="value" name="Portfolio value" stroke={S1} strokeWidth={2} dot={{ r: 4, fill: S1 }} activeDot={{ r: 6 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
