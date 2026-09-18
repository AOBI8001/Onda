const tokens = {};
const authRequests = {};

async function token(role) {
  if (tokens[role]) return tokens[role];
  if (!authRequests[role])
    authRequests[role] = fetch(`/api/auth/dev/${role}`, { method: "POST" })
      .then(async (r) => {
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || "无法建立身份会话");
        tokens[role] = data.token;
        return data.token;
      })
      .finally(() => {
        delete authRequests[role];
      });
  return authRequests[role];
}

export async function api(
  role,
  path,
  { method = "GET", body, signal } = {},
  retry = true,
) {
  const key = await token(role);
  const response = await fetch(`/api${path}`, {
    method,
    signal,
    headers: {
      Authorization: `Bearer ${key}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (response.status === 401 && retry) {
    delete tokens[role];
    return api(role, path, { method, body, signal }, false);
  }
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "请求参数不正确，请检查后重试",
    );
  return result;
}

export async function watchRun(role, id, onUpdate, signal) {
  const key = await token(role);
  let cursor = 0;
  for (let attempt = 0; attempt < 3; attempt++) {
    const response = await fetch(`/api/runs/${id}/events?after=${cursor}`, {
      headers: { Authorization: `Bearer ${key}` },
      signal,
    });
    if (!response.ok) throw new Error("执行状态连接失败");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop();
      for (const frame of frames) {
        const data = frame.split("\n").find((l) => l.startsWith("data: "));
        if (!data) continue;
        const event = JSON.parse(data.slice(6));
        if (event.id) cursor = event.id;
        if (frame.includes("event: settled")) {
          await reader.cancel();
          const final = await api(role, `/runs/${id}`);
          onUpdate(final);
          return final;
        }
        onUpdate(await api(role, `/runs/${id}`));
      }
    }
    const current = await api(role, `/runs/${id}`);
    onUpdate(current);
    if (!["queued", "running"].includes(current.status)) return current;
  }
  throw new Error("实时连接已断开，刷新页面可恢复任务状态");
}
