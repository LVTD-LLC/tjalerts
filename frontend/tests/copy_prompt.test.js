const test = require("node:test");
const assert = require("node:assert/strict");

const { copyPrompt } = require("../src/utils/copy_prompt");

test("copyPrompt writes the complete prompt to the clipboard", async () => {
  const writes = [];
  const clipboard = {
    writeText: async (text) => {
      writes.push(text);
    },
  };

  await copyPrompt(clipboard, "Configure the jobs MCP server");

  assert.deepEqual(writes, ["Configure the jobs MCP server"]);
});

test("copyPrompt reports clipboard failures to its caller", async () => {
  const clipboard = {
    writeText: async () => {
      throw new Error("Clipboard permission denied");
    },
  };

  await assert.rejects(
    copyPrompt(clipboard, "Configure the jobs MCP server"),
    /Clipboard permission denied/,
  );
});

test("copyPrompt rejects browsers without clipboard support", async () => {
  await assert.rejects(
    copyPrompt(undefined, "Configure the jobs MCP server"),
    /Clipboard access is unavailable/,
  );
});
