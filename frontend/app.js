/** API origin: empty when UI is served by uvicorn on :8000; else point at backend. */
function resolveApiBase() {
  const { protocol, hostname, port } = window.location;
  if (port === "8000") return "";
  if (protocol === "file:") return "http://localhost:8000";
  const host = hostname === "0.0.0.0" ? "localhost" : hostname;
  return `http://${host}:8000`;
}
const API = resolveApiBase();

function fetchErrorMessage(err) {
  if (err instanceof TypeError || /failed to fetch|networkerror/i.test(String(err.message))) {
    return (
      "Cannot reach the API. Start the server (uvicorn on port 8000) and open " +
      "http://localhost:8000 — do not use Live Server or open index.html directly."
    );
  }
  return err.message || "Request failed";
}

const state = {
  accessToken: localStorage.getItem("access_token"),
  refreshToken: localStorage.getItem("refresh_token"),
  user: null,
  chats: [],
  activeChatId: null,
  registerMode: false,
};

const $ = (sel) => document.querySelector(sel);

function show(el) {
  el.classList.remove("hidden");
}
function hide(el) {
  el.classList.add("hidden");
}

function setTokens(access, refresh) {
  state.accessToken = access;
  state.refreshToken = refresh;
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

function clearTokens() {
  state.accessToken = null;
  state.refreshToken = null;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

function showAuthError(msg) {
  const el = $("#auth-error");
  el.textContent = msg;
  show(el);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.accessToken) headers.Authorization = `Bearer ${state.accessToken}`;

  let res;
  try {
    res = await fetch(`${API}${path}`, { ...options, headers });
  } catch (err) {
    throw new Error(fetchErrorMessage(err));
  }

  if (res.status === 401 && state.refreshToken && !path.includes("/auth/refresh")) {
    let refreshed;
    try {
      refreshed = await fetch(`${API}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });
    } catch (err) {
      throw new Error(fetchErrorMessage(err));
    }
    if (refreshed.ok) {
      const tokens = await refreshed.json();
      setTokens(tokens.access_token, tokens.refresh_token);
      headers.Authorization = `Bearer ${state.accessToken}`;
      try {
        res = await fetch(`${API}${path}`, { ...options, headers });
      } catch (err) {
        throw new Error(fetchErrorMessage(err));
      }
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg).join(", ")
      : detail || "Request failed";
    throw new Error(message);
  }

  if (res.status === 204) return null;
  return res.json();
}

function parseOAuthFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const access = params.get("access_token");
  const refresh = params.get("refresh_token");
  if (access && refresh) {
    setTokens(access, refresh);
    window.history.replaceState({}, "", "/");
  }
}

async function bootstrap() {
  parseOAuthFromUrl();

  if (!state.accessToken) {
    show($("#auth-screen"));
    hide($("#main-screen"));
    return;
  }

  try {
    state.user = await api("/api/auth/me");
    await enterApp();
  } catch {
    clearTokens();
    show($("#auth-screen"));
    hide($("#main-screen"));
  }
}

async function enterApp() {
  hide($("#auth-screen"));
  show($("#main-screen"));
  $("#user-label").textContent = state.user.login;
  await loadChats();
  startMessagePolling();
}

async function loadChats() {
  state.chats = await api("/api/chats");
  renderChatList();
  if (state.chats.length && !state.activeChatId) {
    selectChat(state.chats[0].id);
  }
}

function renderChatList() {
  const list = $("#chat-list");
  list.innerHTML = "";
  for (const chat of state.chats) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.textContent = chat.title;
    btn.classList.toggle("active", chat.id === state.activeChatId);
    btn.onclick = () => selectChat(chat.id);
    li.appendChild(btn);
    list.appendChild(li);
  }
}

async function selectChat(chatId) {
  state.activeChatId = chatId;
  const chat = state.chats.find((c) => c.id === chatId);
  $("#chat-title").textContent = chat?.title || "Chat";
  show($("#composer"));
  renderChatList();
  await loadMessages();
}

async function loadMessages() {
  if (!state.activeChatId) return;
  const messages = await api(`/api/chats/${state.activeChatId}/messages`);
  const container = $("#messages");
  container.innerHTML = "";
  for (const m of messages) {
    container.appendChild(renderMessage(m.role, m.content));
  }
  container.scrollTop = container.scrollHeight;
}

function renderMessage(role, content) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = content;
  return div;
}

let pollTimer = null;
function startMessagePolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(() => {
    if (state.activeChatId && !$("#send-btn").disabled) {
      loadMessages().catch(() => {});
    }
  }, 15000);
}

$("#toggle-auth-mode").onclick = () => {
  state.registerMode = !state.registerMode;
  hide($("#auth-error"));
  if (state.registerMode) {
    hide($("#login-form"));
    show($("#register-form"));
    $("#toggle-auth-mode").textContent = "Already have an account? Sign in";
  } else {
    show($("#login-form"));
    hide($("#register-form"));
    $("#toggle-auth-mode").textContent = "Need an account? Register";
  }
};

$("#login-form").onsubmit = async (e) => {
  e.preventDefault();
  hide($("#auth-error"));
  const fd = new FormData(e.target);
  try {
    const tokens = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ login: fd.get("login"), password: fd.get("password") }),
    });
    setTokens(tokens.access_token, tokens.refresh_token);
    await bootstrap();
  } catch (err) {
    showAuthError(typeof err.message === "string" ? err.message : "Login failed");
  }
};

$("#register-form").onsubmit = async (e) => {
  e.preventDefault();
  hide($("#auth-error"));
  const fd = new FormData(e.target);
  const body = {
    login: fd.get("login"),
    password: fd.get("password"),
  };
  const email = fd.get("email");
  if (email) body.email = email;
  try {
    const tokens = await api("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    });
    setTokens(tokens.access_token, tokens.refresh_token);
    await bootstrap();
  } catch (err) {
    showAuthError(typeof err.message === "string" ? err.message : "Registration failed");
  }
};

$("#logout-btn").onclick = async () => {
  if (state.refreshToken) {
    await api("/api/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: state.refreshToken }),
    }).catch(() => {});
  }
  clearTokens();
  state.user = null;
  state.chats = [];
  state.activeChatId = null;
  if (pollTimer) clearInterval(pollTimer);
  show($("#auth-screen"));
  hide($("#main-screen"));
};

$("#new-chat-btn").onclick = async () => {
  const chat = await api("/api/chats", {
    method: "POST",
    body: JSON.stringify({ title: "New chat" }),
  });
  state.chats.unshift(chat);
  await selectChat(chat.id);
};

$("#composer").onsubmit = async (e) => {
  e.preventDefault();
  const input = $("#prompt-input");
  const content = input.value.trim();
  if (!content || !state.activeChatId) return;

  const useStream = $("#stream-toggle").checked;
  const container = $("#messages");
  container.appendChild(renderMessage("user", content));
  input.value = "";
  $("#send-btn").disabled = true;

  if (useStream) {
    const assistantEl = renderMessage("assistant", "");
    assistantEl.classList.add("streaming");
    container.appendChild(assistantEl);
    container.scrollTop = container.scrollHeight;

    try {
      let res;
      try {
        res = await fetch(`${API}/api/chats/${state.activeChatId}/messages/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${state.accessToken}`,
          },
          body: JSON.stringify({ content }),
        });
      } catch (err) {
        throw new Error(fetchErrorMessage(err));
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        const detail = err.detail;
        throw new Error(Array.isArray(detail) ? detail.map((d) => d.msg).join(", ") : detail || "Stream failed");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          if (!part.startsWith("data: ")) continue;
          const data = JSON.parse(part.slice(6));
          if (data.type === "token") {
            assistantEl.textContent += data.content;
            container.scrollTop = container.scrollHeight;
          } else if (data.type === "done") {
            assistantEl.textContent = data.message.content;
          } else if (data.type === "error") {
            throw new Error(data.content);
          }
        }
      }
      assistantEl.classList.remove("streaming");
    } catch (err) {
      assistantEl.textContent = `Error: ${err.message}`;
      assistantEl.classList.remove("streaming");
    }
  } else {
    try {
      const msg = await api(`/api/chats/${state.activeChatId}/messages`, {
        method: "POST",
        body: JSON.stringify({ content }),
      });
      container.appendChild(renderMessage("assistant", msg.content));
    } catch (err) {
      container.appendChild(renderMessage("assistant", `Error: ${err.message}`));
    }
  }

  $("#send-btn").disabled = false;
  container.scrollTop = container.scrollHeight;
  await loadChats();
};

bootstrap();
