import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  Clock3,
  LoaderCircle,
  MessageSquare,
  Plus,
  Send,
  ShieldAlert,
  ThumbsDown,
  ThumbsUp,
  UserRound,
} from "lucide-react";
import { api, watchRun } from "./api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function Trace({ run }) {
  if (!run) return null;
  const pending = run.proposals?.some((p) => p.status === "pending");
  const highRisk = Boolean(run.proposals?.length);
  return (
    <details className="execution-details">
      <summary>
        <span>
          <Activity size={15} />
          {pending
            ? "等待人工确认"
            : run.status === "completed"
              ? "已完成"
              : run.status === "failed"
                ? "未完成"
                : "正在处理"}
          <span className={`badge ${highRisk ? "red" : "green"}`}>
            {highRisk ? "高风险" : "低风险"}
          </span>
        </span>
        <span>
          展开详情 <ChevronDown size={14} />
        </span>
      </summary>
      <div className="execution-body">
        <p>执行步骤与依据摘要</p>
        {run.events?.map((event) => (
          <div className="execution-step done" key={event.id}>
            {event.status === "running" ? (
              <Clock3 size={15} />
            ) : (
              <CheckCircle2 size={15} />
            )}
            <span>
              {event.stage}
              {event.detail && (
                <small className="trace-detail">{event.detail}</small>
              )}
            </span>
            <small>
              {event.status === "running"
                ? "已启动"
                : event.status === "awaiting_approval"
                  ? "待确认"
                  : event.status === "failed"
                    ? "未完成"
                    : "已记录"}
            </small>
          </div>
        ))}
        {run.meta?.errorCode && (
          <p className="api-error">错误代码：{run.meta.errorCode}</p>
        )}
      </div>
    </details>
  );
}

export function LiveAgent({ seller, requestApproval, refresh, setToast }) {
  const role = seller ? "seller" : "buyer";
  const [threads, setThreads] = useState([]),
    [active, setActive] = useState(null),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false),
    [live, setLive] = useState(null),
    [draft, setDraft] = useState(null),
    [error, setError] = useState("");
  const controller = useRef(null),
    scroll = useRef(null);
  const thread = threads.find((t) => t.id === active);
  const load = async () => {
    const data = await api(role, "/threads");
    setThreads(data);
    return data;
  };
  const watch = async (id) => {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setBusy(true);
    try {
      await watchRun(role, id, setLive, abort.signal);
      await load();
      await refresh();
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message);
    } finally {
      if (!abort.signal.aborted) {
        setBusy(false);
        setDraft(null);
      }
    }
  };
  useEffect(() => {
    let valid = true;
    load()
      .then((data) => {
        if (!valid) return;
        const first = data[0];
        if (!first) return;
        setActive(first.id);
        const latest = first.runs.at(-1);
        setLive(latest || null);
        if (latest && ["queued", "running"].includes(latest.status))
          watch(latest.id);
      })
      .catch((e) => setError(e.message));
    return () => {
      valid = false;
      controller.current?.abort();
    };
  }, [role]);
  useEffect(() => {
    scroll.current?.scrollTo({
      top: scroll.current.scrollHeight,
      behavior: "smooth",
    });
  }, [live?.events?.length, draft, active]);
  const send = async (text = input) => {
    if (!text.trim() || busy) return;
    setError("");
    setBusy(true);
    setDraft(text.trim());
    setInput("");
    try {
      const result = await api(role, "/runs", {
        method: "POST",
        body: { text: text.trim(), thread_id: active },
      });
      setActive(result.thread_id);
      setLive({ id: result.id, status: "queued", events: [], proposals: [] });
      await watch(result.id);
    } catch (e) {
      setError(e.message);
      setBusy(false);
      setDraft(null);
    }
  };
  const showApproval = (proposal) =>
    requestApproval({
      proposal,
      onSuccess: async () => {
        await load();
        const run = await api(
          role,
          `/runs/${live?.id || thread.runs.at(-1).id}`,
        );
        setLive(run);
        if (["queued", "running"].includes(run.status)) await watch(run.id);
      },
    });
  const messages = thread?.messages || [];
  const runs = Object.fromEntries((thread?.runs || []).map((r) => [r.id, r]));
  if (live) runs[live.id] = live;
  const pending = live?.proposals?.filter((p) => p.status === "pending") || [];
  return (
    <div className="chat-layout">
      <aside className="chat-sidebar card">
        <div className="chat-sidebar-heading">
          <h2>对话记录</h2>
          <button
            className="round-button"
            aria-label="新建对话"
            disabled={busy}
            onClick={() => {
              setActive(null);
              setLive(null);
              setDraft(null);
              setError("");
            }}
          >
            <Plus size={23} />
          </button>
        </div>
        <div className="history-list">
          {threads.map((t) => (
            <button
              key={t.id}
              disabled={busy}
              className={active === t.id ? "active" : ""}
              onClick={() => {
                setActive(t.id);
                setLive(t.runs.at(-1) || null);
                setError("");
                const r = t.runs.at(-1);
                if (r && ["queued", "running"].includes(r.status)) watch(r.id);
              }}
            >
              <MessageSquare size={25} />
              <span>
                <strong>{t.title}</strong>
                <small>{new Date(t.created).toLocaleDateString("zh-CN")}</small>
              </span>
            </button>
          ))}
        </div>
        <div className="sidebar-caption">ONDA — A BRIGHTER EVERYDAY</div>
      </aside>
      <section className="chat-panel card">
        <div className="chat-messages" ref={scroll}>
          {!messages.length && !draft && (
            <div className="chat-welcome">
              <span className="orb" />
              <h2>{seller ? "让经营更从容" : "Hi, 我是 Onda"}</h2>
              <p>
                {seller
                  ? "销售、库存、订单和工单，从这里开始。"
                  : "发现好物，追踪订单，照顾你的每一份期待。"}
              </p>
              <div>
                {(seller
                  ? [
                      "分析最近一个月的销售情况",
                      "哪些商品库存不足？",
                      "查看待处理工单",
                    ]
                  : [
                    "推荐300元以内适合送礼的数码配件",
                      "查询我的订单物流",
                      "帮我取消待发货的耳机订单",
                    ]
                ).map((text) => (
                  <button key={text} onClick={() => send(text)}>
                    {text}
                    <ArrowRight size={15} />
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div className={`message-row ${m.role}`} key={m.id}>
              {m.role === "assistant" && <span className="orb small" />}
              <div className="message-content">
                <div className="message-bubble">
                  {m.role === "assistant" ? (
                    <div className="agent-markdown">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          a: ({ children, ...props }) => (
                            <a
                              {...props}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {children}
                            </a>
                          ),
                        }}
                      >
                        {m.text}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="live-message-text">{m.text}</p>
                  )}
                  {m.role === "assistant" && (
                    <>
                      <Trace run={runs[m.run_id]} />
                      <div className="feedback-actions">
                        <button
                          aria-label="回答有帮助"
                          onClick={() =>
                            api(role, `/runs/${m.run_id}/feedback`, {
                              method: "POST",
                              body: { rating: "helpful" },
                            })
                              .then(() => setToast("反馈已记录"))
                              .catch((e) => setToast(e.message))
                          }
                        >
                          <ThumbsUp size={14} />
                        </button>
                        <button
                          aria-label="回答需改进"
                          onClick={() =>
                            api(role, `/runs/${m.run_id}/feedback`, {
                              method: "POST",
                              body: { rating: "unhelpful" },
                            })
                              .then(() => setToast("反馈已记录"))
                              .catch((e) => setToast(e.message))
                          }
                        >
                          <ThumbsDown size={14} />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
              {m.role === "user" && (
                <span className="avatar default-avatar">
                  <UserRound size={23} />
                </span>
              )}
            </div>
          ))}
          {draft &&
            !messages.some((m) => m.text === draft && m.role === "user") && (
              <div className="message-row user">
                <div className="message-content">
                  <div className="message-bubble">
                    <p>{draft}</p>
                  </div>
                </div>
                <span className="avatar default-avatar">
                  <UserRound size={23} />
                </span>
              </div>
            )}
          {busy && (
            <div className="message-row assistant">
              <span className="orb small" />
              <div className="running-card">
                <span>
                  <LoaderCircle className="spin" size={16} /> Onda 正在处理…
                </span>
                <Trace run={live} />
              </div>
            </div>
          )}
          {pending.map((p) => (
            <div className="live-approval card" key={p.id}>
              <div>
                <ShieldAlert size={20} />
                <strong>{p.title}</strong>
                <span className="badge red">高风险 · 待确认</span>
              </div>
              <p>操作对象：{p.target}</p>
              <button
                className="btn-primary"
                disabled={busy}
                onClick={() => showApproval(p)}
              >
                查看并确认操作 <ArrowRight size={16} />
              </button>
              <button
                className="text-button"
                disabled={busy}
                onClick={async () => {
                  try {
                    await api(role, `/proposals/${p.id}/decision`, {
                      method: "POST",
                      body: { approved: false },
                    });
                    await watch(live.id);
                  } catch (e) {
                    setError(e.message);
                  }
                }}
              >
                拒绝操作
              </button>
            </div>
          ))}
          {error && (
            <div className="api-error" role="alert">
              {error}
            </div>
          )}
        </div>
        <div className="chat-input-area">
          <form
            className="chat-input"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <input
              aria-label="给 Onda 发送消息"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={busy || pending.length > 0}
              placeholder={
                pending.length
                  ? "请先确认或拒绝待处理操作"
                  : busy
                    ? "Onda 正在处理，请稍候…"
                    : "和 Onda 聊一聊你想了解的问题…"
              }
            />
            <button
              className="send-button"
              aria-label="发送消息"
              disabled={busy || pending.length > 0 || !input.trim()}
            >
              {busy ? (
                <LoaderCircle className="spin" size={21} />
              ) : (
                <Send size={23} />
              )}
            </button>
          </form>
        </div>
      </section>
    </div>
  );
}
