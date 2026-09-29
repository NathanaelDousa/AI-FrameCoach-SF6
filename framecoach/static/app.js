const chatWindow = document.getElementById("chat-window");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendButton = document.getElementById("send");
const characterSelect = document.getElementById("character");

function escapeHTML(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function inline(text) {
  return text
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*?)\*/g, "$1<em>$2</em>");
}

// Small markdown renderer. The input is escaped first, so model output can never inject HTML.
function renderMarkdown(markdown) {
  const lines = escapeHTML(markdown).split("\n");
  const html = [];
  let list = null;

  const closeList = () => {
    if (list) html.push(`</${list}>`);
    list = null;
  };

  for (const line of lines) {
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    const bullet = line.match(/^\s*[-*+]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);

    if (heading) {
      closeList();
      html.push(`<h4>${inline(heading[2])}</h4>`);
    } else if (bullet || numbered) {
      const type = bullet ? "ul" : "ol";
      if (list !== type) {
        closeList();
        html.push(`<${type}>`);
        list = type;
      }
      html.push(`<li>${inline((bullet || numbered)[1])}</li>`);
    } else if (line.trim() === "") {
      closeList();
    } else {
      closeList();
      html.push(`<p>${inline(line)}</p>`);
    }
  }
  closeList();
  return html.join("");
}

function scrollToBottom() {
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function addMessage(sender, text = "") {
  const div = document.createElement("div");
  div.classList.add("message", sender);
  div.textContent = text;
  chatWindow.appendChild(div);
  scrollToBottom();
  return div;
}

function addSources(message, sources) {
  if (!sources.length) return;
  const details = document.createElement("details");
  details.className = "sources";
  const summary = document.createElement("summary");
  summary.textContent = `Sources (${sources.length})`;
  details.appendChild(summary);
  for (const source of sources) {
    const item = document.createElement("details");
    const label = document.createElement("summary");
    label.textContent = source.label;
    const body = document.createElement("pre");
    body.textContent = source.text;
    item.append(label, body);
    details.appendChild(item);
  }
  message.after(details);
}

async function ask(question) {
  chatWindow.querySelector(".welcome")?.remove();
  addMessage("user", question);
  const bot = addMessage("bot", "Thinking...");
  bot.classList.add("thinking");
  sendButton.disabled = true;

  let answer = "";
  let sources = [];
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, character: characterSelect.value, stream: true }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      if (response.status === 400 && settings && !settings.configured) openSettings(true);
      throw new Error(data.error || `Request failed (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.type === "meta") {
          sources = event.sources;
        } else if (event.type === "token") {
          answer += event.text;
          bot.classList.remove("thinking");
          bot.innerHTML = renderMarkdown(answer);
          scrollToBottom();
        } else if (event.type === "error") {
          throw new Error(event.error);
        }
      }
    }
    if (!answer) throw new Error("The model returned an empty answer.");
    addSources(bot, sources);
  } catch (error) {
    bot.classList.remove("thinking");
    bot.classList.add("error");
    bot.textContent = error.message;
    console.error(error);
  } finally {
    sendButton.disabled = false;
    chatInput.focus();
    scrollToBottom();
  }
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question || sendButton.disabled) return;
  chatInput.value = "";
  ask(question);
});

chatWindow.addEventListener("click", (e) => {
  if (e.target.classList.contains("example")) ask(e.target.textContent);
});

// --- Model settings ---------------------------------------------------------

const dialog = document.getElementById("settings-dialog");
const settingsForm = document.getElementById("settings-form");
const providerSelect = document.getElementById("provider");
const modelSelect = document.getElementById("model");
const apiKeyInput = document.getElementById("api-key");
const settingsError = document.getElementById("settings-error");
const saveButton = document.getElementById("settings-save");
const API_PROVIDERS = ["anthropic", "openai", "deepseek"];
const SHORT_NAMES = { ollama: "Local", anthropic: "Claude", openai: "OpenAI", deepseek: "DeepSeek" };

let settings = null;
let modelRequest = 0;

const providerInfo = (id) => settings.providers.find((p) => p.id === id);

async function postJSON(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function updateModelLabel() {
  const label = document.getElementById("model-label");
  if (!settings.configured) {
    label.textContent = "Choose a model";
    return;
  }
  label.textContent = `${SHORT_NAMES[settings.provider]} · ${providerInfo(settings.provider).model}`;
}

function setModelOptions(models, selected) {
  const unique = [...new Set([selected, ...models].filter(Boolean))];
  modelSelect.replaceChildren(
    ...unique.map((name) => {
      const option = document.createElement("option");
      option.value = option.textContent = name;
      return option;
    })
  );
  if (!unique.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Enter your API key to see models";
    modelSelect.appendChild(option);
  }
  modelSelect.value = selected || unique[0] || "";
}

async function loadModels() {
  const provider = providerSelect.value;
  const info = providerInfo(provider);
  if (info.needs_key && !info.has_key && !apiKeyInput.value.trim()) return;
  const request = ++modelRequest;
  settingsError.textContent = "";
  const button = document.getElementById("load-models");
  button.disabled = true;
  button.textContent = "Loading...";
  try {
    const data = await postJSON("/api/models", { provider, api_key: apiKeyInput.value.trim() });
    if (request !== modelRequest) return; // the user switched provider meanwhile
    let current = modelSelect.value || info.model;
    // Ollama reports "gemma3" as "gemma3:latest".
    if (!data.models.includes(current) && data.models.includes(`${current}:latest`)) current += ":latest";
    // Suggested models first so the recommended ones are at the top.
    const ordered = [...info.suggested_models.filter((m) => data.models.includes(m)), ...data.models];
    setModelOptions(ordered, data.models.includes(current) || provider === "ollama" ? current : ordered[0]);
  } catch (error) {
    if (request === modelRequest) settingsError.textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "Refresh list";
  }
}

function selectProvider() {
  const info = providerInfo(providerSelect.value);
  document.getElementById("key-row").hidden = !info.needs_key;
  document.getElementById("ollama-help").hidden = info.id !== "ollama";
  document.getElementById("key-link").href = info.key_url || "#";
  document.getElementById("key-status").textContent = info.has_key
    ? `A key is saved (${info.key_hint}). Paste a new one to replace it.`
    : "Paste your API key.";
  apiKeyInput.value = "";
  apiKeyInput.placeholder = info.has_key ? `Saved key ${info.key_hint}` : "Paste your key here";
  settingsError.textContent = "";
  setModelOptions(info.suggested_models, info.model);
  loadModels();
}

function selectMode(mode) {
  document.getElementById("provider-fields").hidden = false;
  document.getElementById("provider-row").hidden = mode === "local";
  const ids = mode === "local" ? ["ollama"] : API_PROVIDERS;
  providerSelect.replaceChildren(
    ...ids.map((id) => {
      const option = document.createElement("option");
      option.value = id;
      option.textContent = providerInfo(id).label;
      return option;
    })
  );
  providerSelect.value = ids.includes(settings.provider) ? settings.provider : ids[0];
  selectProvider();
}

function openSettings(firstRun = false) {
  document.getElementById("settings-title").textContent = firstRun ? "Choose your AI" : "Model settings";
  document.getElementById("settings-intro").hidden = !firstRun;
  document.getElementById("settings-cancel").hidden = firstRun;
  document.getElementById("provider-fields").hidden = true;
  settingsError.textContent = "";
  for (const radio of settingsForm.elements.mode) radio.checked = false;
  if (settings.configured) {
    const mode = settings.provider === "ollama" ? "local" : "api";
    settingsForm.elements.mode.value = mode;
    selectMode(mode);
  }
  if (!dialog.open) dialog.showModal();
}

async function loadSettings() {
  try {
    const response = await fetch("/api/settings");
    settings = await response.json();
  } catch (error) {
    console.error(error);
    return;
  }
  updateModelLabel();
  if (!settings.configured) openSettings(true);
}

settingsForm.addEventListener("change", (e) => {
  if (e.target.name === "mode") selectMode(e.target.value);
});
providerSelect.addEventListener("change", selectProvider);
apiKeyInput.addEventListener("change", loadModels);
document.getElementById("load-models").addEventListener("click", loadModels);
document.getElementById("model-button").addEventListener("click", () => openSettings(!settings.configured));
document.getElementById("settings-cancel").addEventListener("click", () => dialog.close());

// Escape closes the dialog, except on first launch when a choice is required.
dialog.addEventListener("cancel", (e) => {
  if (!settings.configured) e.preventDefault();
});

settingsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (document.getElementById("provider-fields").hidden) {
    settingsError.textContent = "Choose a local model or a cloud API first.";
    return;
  }
  saveButton.disabled = true;
  try {
    settings = await postJSON("/api/settings", {
      provider: providerSelect.value,
      model: modelSelect.value,
      api_key: apiKeyInput.value.trim(),
    });
    apiKeyInput.value = "";
    updateModelLabel();
    dialog.close();
  } catch (error) {
    settingsError.textContent = error.message;
  } finally {
    saveButton.disabled = false;
  }
});

loadSettings();
