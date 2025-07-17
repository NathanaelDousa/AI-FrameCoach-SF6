async function sendQuestion() {
  const question = document.getElementById('question').value;
  const responseDiv = document.getElementById('response');
  responseDiv.textContent = "Even denken...";

  const response = await fetch('http://localhost:11434/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'gemma3',
      prompt: question,
      stream: false
    })
  });

  const data = await response.json();
  responseDiv.textContent = data.response;
}
