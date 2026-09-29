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
