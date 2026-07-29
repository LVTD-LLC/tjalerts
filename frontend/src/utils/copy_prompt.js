async function copyPrompt(clipboard, prompt) {
  if (!clipboard || typeof clipboard.writeText !== "function") {
    throw new Error("Clipboard access is unavailable");
  }

  await clipboard.writeText(prompt);
}

module.exports = { copyPrompt };
