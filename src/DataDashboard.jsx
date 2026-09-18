import React, { useEffect, useState } from "react";
import {
  BarChart3,
  ShoppingBag,
  Headphones,
  Package,
  ArrowRight,
} from "lucide-react";
import { api } from "./api";

export function DataDashboard({ analytics, products, tickets, go }) {
  const [days, setDays] = useState(30),
    [data, setData] = useState(analytics),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api("seller", `/analytics?days=${days}`)
      .then((d) => {
        if (active) {
          setData(d);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [days, analytics]);
  if (!data)
    return (
      <div className="page-heading">
        <h1>数据看板</h1>
        <p>{error || "正在加载经营数据…"}</p>
      </div>
    );
  const maximum = Math.max(...data.trend.map((d) => d.amount), 1);
  const points = data.trend
    .map(
      (d, i) =>
        `${45 + (i / Math.max(1, data.trend.length - 1)) * 610},${230 - (d.amount / maximum) * 190}`,
    )
    .join(" ");
  const statuses = Object.entries(data.orderStatuses);
  const colors = [
    "#4382ff",
    "#85aaff",
    "#c4d7ff",
    "#ffc684",
    "#ffa3a3",
    "#97d7ca",
  ];
  let total = 0;
  const gradient = statuses
    .map(([_, n], i) => {
      let start = total;
      total += (n / Math.max(1, data.orderCount)) * 100;
      return `${colors[i % colors.length]} ${start}% ${total}%`;
    })
    .join(",");
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>数据看板</h1>
          <p>经营表现，一目了然。</p>
        </div>
        <span className="badge blue">近 {days} 天</span>
      </div>
      {error && <p className="api-error">{error}</p>}
      <div className="metric-grid">
        {[
          [BarChart3, "销售额", `¥ ${data.sales.toLocaleString("zh-CN")}`],
          [ShoppingBag, "订单数", data.orderCount],
          [
            Headphones,
            "待处理工单",
            tickets.filter((t) => t.status !== "已完成").length,
          ],
          [Package, "商品数量", products.length],
        ].map(([Icon, title, value]) => (
          <article className="metric-card card" key={title}>
            <span className="feature-icon">
              <Icon />
            </span>
            <div>
              <span>{title}</span>
              <strong>{value}</strong>
              <small>
                {title === "销售额" || title === "订单数"
                  ? `近 ${days} 天`
                  : "当前状态"}
              </small>
            </div>
          </article>
        ))}
      </div>
      <div className="dashboard-bottom live-dashboard">
        <section className="chart-card card">
          <div className="section-title">
            <h2>销售趋势</h2>
            <div className="segmented">
              {[7, 30, 90].map((n) => (
                <button
                  key={n}
                  className={days === n ? "active" : ""}
                  onClick={() => setDays(n)}
                >
                  近{n}天
                </button>
              ))}
            </div>
          </div>
          <svg
            className="live-trend"
            viewBox="0 0 700 275"
            role="img"
            aria-label={`近${days}天销售额趋势`}
          >
            <defs>
              <linearGradient id="sales-fill" x1="0" x2="0" y1="0" y2="1">
                <stop stopColor="#83b1ff" stopOpacity=".4" />
                <stop offset="1" stopColor="#83b1ff" stopOpacity="0" />
              </linearGradient>
            </defs>
            {[0, 0.25, 0.5, 0.75, 1].map((f) => (
              <g key={f}>
                <line
                  x1="45"
                  x2="655"
                  y1={230 - f * 190}
                  y2={230 - f * 190}
                  stroke="#e8eef8"
                />
                <text
                  x="35"
                  y={234 - f * 190}
                  textAnchor="end"
                  fill="#8d9dbc"
                  fontSize="10"
                >
                  {Math.round(f * maximum)}
                </text>
              </g>
            ))}
            <polygon
              points={`45,230 ${points} 655,230`}
              fill="url(#sales-fill)"
            />
            <polyline
              points={points}
              fill="none"
              stroke="#3478ff"
              strokeWidth="2.5"
            />
            {data.trend
              .filter(
                (_, i) =>
                  i === 0 || i === Math.floor(days / 2) || i === days - 1,
              )
              .map((d, i) => (
                <text
                  key={d.date}
                  x={45 + i * 305}
                  y="258"
                  textAnchor="middle"
                  fill="#8d9dbc"
                  fontSize="11"
                >
                  {d.date.slice(5)}
                </text>
              ))}
          </svg>
          <p className="dashboard-definition">{data.definition}</p>
        </section>
        <section className="status-card card">
          <div className="section-title">
            <h2>订单状态</h2>
          </div>
          <div className="live-donut-wrap">
            <div
              className="donut"
              style={{
                background: `conic-gradient(${gradient || "#e9f0fc 0% 100%"})`,
              }}
            >
              <div>
                <strong>{data.orderCount}</strong>
                <span>总订单数</span>
              </div>
            </div>
            <ul className="live-status-list">
              {statuses.map(([s, n], i) => (
                <li key={s}>
                  <i style={{ background: colors[i % colors.length] }} />
                  <span>{s}</span>
                  <b>{n}</b>
                </li>
              ))}
            </ul>
          </div>
        </section>
        <section className="ranking-card card">
          <div className="section-title">
            <h2>热销商品排行</h2>
            <button
              className="text-button"
              onClick={() => go("/seller/products")}
            >
              查看全部 <ArrowRight size={14} />
            </button>
          </div>
          {data.topProducts.slice(0, 5).map((p, i) => (
            <div className="live-rank" key={p.id}>
              <span className={`rank-number rank-${i}`}>{i + 1}</span>
              <div>
                <strong>{p.name}</strong>
                <div className="rank-bar">
                  <span
                    style={{
                      width: `${(p.sales / Math.max(1, data.topProducts[0].sales)) * 100}%`,
                    }}
                  />
                </div>
              </div>
              <small>{p.sales} 件</small>
            </div>
          ))}
        </section>
      </div>
    </>
  );
}
