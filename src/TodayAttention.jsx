import React, { useEffect, useState, useRef } from "react";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  RefreshCw,
  ShieldAlert,
  X,
} from "lucide-react";
import { api } from "./api";

export function TodayAttention({
  products,
  orders,
  requestApproval,
  go,
  setGlobalSearch,
}) {
  const [report, setReport] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [selected, setSelected] = useState(null),
    [quantities, setQuantities] = useState({});
  const fingerprint = [...products, ...orders]
    .map((r) => `${r.id}:${r.version}`)
    .join("|");
  const dialogRef = useRef(null);
  const load = async (force = false) => {
    setBusy(true);
    setError("");
    try {
      setReport(
        await api("seller", `/inspections?force=${force}`, { method: "POST" }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    let active = true;
    setBusy(true);
    api("seller", "/inspections", { method: "POST" })
      .then((data) => {
        if (active) {
          setReport(data);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [fingerprint]);
  const item = report?.items.find((i) => i.id === selected);
  useEffect(() => {
    if (!item) return;
    const old = document.body.style.overflow;
    const previous = document.activeElement;
    document.body.style.overflow = "hidden";
    dialogRef.current?.focus();
    const key = (e) => {
      if (e.key === "Escape") setSelected(null);
      if (e.key === "Tab") {
        const nodes = dialogRef.current?.querySelectorAll(
          "button:not(:disabled),input,a[href]",
        );
        if (!nodes?.length) return;
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (
          e.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === dialogRef.current)
        ) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", key);
    return () => {
      document.body.style.overflow = old;
      window.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, [Boolean(item)]);
  const viewOrder = (id) => {
    setSelected(null);
    setGlobalSearch(id);
    go("/seller/orders");
  };
  return (
    <section className="today-attention card" aria-label="Onda 今日关注">
      <div className="attention-heading">
        <div>
          <span className="attention-orb">
            <Activity size={21} />
          </span>
          <div>
            <h2>Onda 今日关注</h2>
            <p>自动检查经营数据，把值得处理的事放在前面。</p>
          </div>
        </div>
        <div className="attention-meta">
          <span>
            {busy
              ? "正在检查…"
              : report
                ? `上次检查：${new Date(report.checkedAt).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`
                : "尚未完成检查"}
          </span>
          <button
            aria-label="重新检查经营状况"
            disabled={busy}
            onClick={() => load(true)}
          >
            <RefreshCw size={15} className={busy ? "spin" : ""} />
          </button>
        </div>
      </div>
      {error && <p className="api-error">{error}</p>}
      {!report && busy && (
        <div className="attention-loading">
          正在核对库存、待发货订单与销售变化…
        </div>
      )}
      {report?.items.map((item) => (
        <div className={`attention-row ${item.tone}`} key={item.id}>
          <span className={`attention-priority ${item.tone}`}>
            {item.priority}
          </span>
          <div>
            <h3>{item.title}</h3>
            <p>{item.next}</p>
          </div>
          <button onClick={() => setSelected(item.id)}>
            {item.action}
            <ArrowRight size={16} />
          </button>
        </div>
      ))}
      {report && !report.items.length && (
        <div className="attention-clear">
          <CheckCircle2 size={22} />
          <div>
            <strong>当前没有需要优先处理的异常</strong>
            <p>
              本次已检查 {report.coverage.products} 件商品与{" "}
              {report.coverage.orders} 笔订单。
            </p>
          </div>
        </div>
      )}
      {report && (
        <details className="inspection-details">
          <summary>
            检查依据与执行详情 <ChevronDown size={14} />
          </summary>
          <div>
            {report.steps.map((s) => (
              <p key={s.stage}>
                <CheckCircle2 size={14} />
                {s.stage}
              </p>
            ))}
            <p>
              检查 {report.coverage.products} 件商品、{report.coverage.orders}{" "}
              笔订单。数据变化立即重检；无变化时复用 5 分钟内的结果。
            </p>
            {report.dataNotes.map((t) => (
              <p key={t}>{t}</p>
            ))}
          </div>
        </details>
      )}
      {item && (
        <div
          className="attention-dialog-backdrop"
          onClick={() => setSelected(null)}
        >
          <section
            className="attention-dialog"
            ref={dialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label={item.title}
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <small>{item.priority}</small>
                <h2>{item.title}</h2>
              </div>
              <button
                aria-label="关闭关注详情"
                onClick={() => setSelected(null)}
              >
                <X size={21} />
              </button>
            </header>
            <div className="attention-explanation">
              <strong>为什么值得关注</strong>
              <p>{item.reason}</p>
              <strong>下一步</strong>
              <p>{item.next}</p>
            </div>
            <div className="attention-evidence">
              {item.rows.map((row) => (
                <article key={row.id}>
                  <div className="attention-evidence-heading">
                    <strong>{row.name}</strong>
                    <small>{row.id}</small>
                  </div>
                  {item.id === "stock" ? (
                    <>
                      <div className="attention-facts">
                        <span>
                          当前库存 <b>{row.stock} 件</b>
                        </span>
                        <span>
                          近 7 天售出 <b>{row.sold7} 件</b>
                        </span>
                        <span>
                          预计可支撑{" "}
                          <b>
                            {row.coverageDays === null
                              ? "暂不预测"
                              : `${row.coverageDays} 天`}
                          </b>
                        </span>
                      </div>
                      <small>{row.confidence}</small>
                      <div className="restock-controls">
                        <label>
                          建议补货数量
                          <input
                            aria-label={`补货数量 ${row.id}`}
                            type="number"
                            min="1"
                            max="10000"
                            step="1"
                            value={quantities[row.id] ?? row.suggestedQuantity}
                            onChange={(e) =>
                              setQuantities((q) => ({
                                ...q,
                                [row.id]: e.target.value,
                              }))
                            }
                          />
                        </label>
                        <button
                          className="btn-primary"
                          disabled={row.hasPlan}
                          onClick={() => {
                            const quantity = Number(
                              quantities[row.id] ?? row.suggestedQuantity,
                            );
                            if (
                              !Number.isInteger(quantity) ||
                              quantity < 1 ||
                              quantity > 10000
                            ) {
                              setError("补货数量须为 1 至 10000 的整数");
                              return;
                            }
                            setSelected(null);
                            requestApproval({
                              action: "plan_restock",
                              target: row.id,
                              version: row.version,
                              params: { quantity },
                              description: `为 ${row.name} 记录 ${quantity} 件待补货计划。不会增加现有库存，也不会创建采购或付款。`,
                              onSuccess: () => load(true),
                            });
                          }}
                        >
                          <ShieldAlert size={15} />
                          {row.hasPlan ? "已有待补货计划" : "审核补货方案"}
                        </button>
                      </div>
                    </>
                  ) : item.id === "shipping" ? (
                    <>
                      <p>
                        已等待 {row.hoursWaiting} 小时 · 超时 {row.hoursOverdue}{" "}
                        小时
                      </p>
                      <button
                        className="text-button"
                        onClick={() => viewOrder(row.id)}
                      >
                        在订单管理中处理 <ArrowRight size={14} />
                      </button>
                    </>
                  ) : item.id === "growth" ? (
                    <div className="attention-facts">
                      <span>
                        前 7 天 <b>{row.previous7} 件</b>
                      </span>
                      <span>
                        近 7 天 <b>{row.recent7} 件</b>
                      </span>
                      <span>
                        增长 <b>{row.growthPercent}%</b>
                      </span>
                      <span>
                        当前库存 <b>{row.stock} 件</b>
                      </span>
                    </div>
                  ) : (
                    <p>
                      前期订单毛利 ¥ {row.previousGrossProfit} → 近期 ¥{" "}
                      {row.recentGrossProfit}。{row.note}
                    </p>
                  )}
                </article>
              ))}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
