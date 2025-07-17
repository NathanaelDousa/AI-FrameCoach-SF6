const chatWindow = document.getElementById("chat-window");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");

function markdownToHTML(markdown) {
  return markdown
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // **bold**
    .replace(/^\* (.*$)/gm, '<li>$1</li>')             // * list item
    .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');        // wrap in <ul>
}

function addMessage(text, sender, isMarkdown = false) {
  const msgDiv = document.createElement("div");
  msgDiv.classList.add("message", sender);

  // Gebruik innerHTML als het een bot-bericht is met markdown
  if (isMarkdown) {
    msgDiv.innerHTML = markdownToHTML(text);
  } else {
    msgDiv.textContent = text;
  }

  chatWindow.appendChild(msgDiv);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const userInput = chatInput.value.trim();
  if (!userInput) return;

  addMessage(userInput, "user");
  chatInput.value = "";
  console.log(chatInput);
  const thinkingMsg = document.createElement("div");
  thinkingMsg.classList.add("message", "bot", "thinking");
  thinkingMsg.textContent = "Even denken...";
  chatWindow.appendChild(thinkingMsg);
  chatWindow.scrollTop = chatWindow.scrollHeight;

  try {
    // 👉 Stuur de vraag naar je Flask API i.p.v. direct naar Ollama
    const response = await fetch('http://localhost:5000/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: userInput
      })
    });

    const data = await response.json();
    thinkingMsg.remove();

    // ✨ Render het AI-antwoord met markdown ondersteuning
    addMessage(data.answer, "bot", true);
  } catch (error) {
    thinkingMsg.textContent = "Er is iets misgegaan bij het ophalen van het antwoord.";
    console.error(error);
  }
});