const test = require("node:test");
const assert = require("node:assert/strict");

const { CopyPromptController } = require("../src/controllers/copy_prompt_controller");

function buildController(clipboard) {
  const scheduledResets = [];
  const clearedTimers = [];

  Object.defineProperty(global, "navigator", {
    configurable: true,
    value: { clipboard },
  });
  global.window = {
    clearTimeout(timer) {
      clearedTimers.push(timer);
    },
    setTimeout(callback) {
      scheduledResets.push(callback);
      return scheduledResets.length;
    },
  };

  const controller = new CopyPromptController({
    scope: {
      element: { isConnected: true },
    },
  });
  controller.buttonTarget = { disabled: false };
  controller.labelTarget = { textContent: "Copy Prompt for AI" };
  controller.promptTarget = { value: "  Configure the jobs MCP server  " };
  controller.statusTarget = { textContent: "" };
  controller.initialize();
  controller.connect();

  return {
    clearedTimers,
    controller,
    runScheduledReset: (index = scheduledResets.length - 1) => scheduledResets[index](),
  };
}

test.afterEach(() => {
  delete global.navigator;
  delete global.window;
});

test("controller reports a successful copy and resets its label", async () => {
  const writes = [];
  const fixture = buildController({
    writeText: async (text) => writes.push(text),
  });

  await fixture.controller.copy();

  assert.deepEqual(writes, ["Configure the jobs MCP server"]);
  assert.equal(fixture.controller.buttonTarget.disabled, false);
  assert.equal(fixture.controller.labelTarget.textContent, "Copied!");
  assert.equal(
    fixture.controller.statusTarget.textContent,
    "AI setup prompt copied to your clipboard.",
  );

  fixture.runScheduledReset();

  assert.equal(fixture.controller.labelTarget.textContent, "Copy Prompt for AI");
  assert.equal(fixture.controller.statusTarget.textContent, "");
});

test("controller exposes clipboard failures and remains retryable", async () => {
  const fixture = buildController({
    writeText: async () => {
      throw new Error("Clipboard permission denied");
    },
  });

  await fixture.controller.copy();

  assert.equal(fixture.controller.buttonTarget.disabled, false);
  assert.equal(fixture.controller.labelTarget.textContent, "Copy failed");
  assert.equal(
    fixture.controller.statusTarget.textContent,
    "Clipboard access failed. Check your browser permission and try again.",
  );
});

test("controller clears its pending reset when disconnected", async () => {
  const fixture = buildController({
    writeText: async () => {},
  });

  await fixture.controller.copy();
  fixture.controller.disconnect();

  assert.deepEqual(fixture.clearedTimers, [1]);
});

test("controller ignores clipboard completion after disconnect", async () => {
  let finishCopy;
  const fixture = buildController({
    writeText: () => new global.Promise((resolve) => {
      finishCopy = resolve;
    }),
  });

  const copy = fixture.controller.copy();
  fixture.controller.context.scope.element.isConnected = false;
  fixture.controller.disconnect();
  finishCopy();
  await copy;

  assert.equal(fixture.controller.labelTarget.textContent, "Copy Prompt for AI");
  assert.equal(fixture.controller.statusTarget.textContent, "");
  assert.throws(fixture.runScheduledReset);
});

test("a newer copy attempt cannot be reset by an older timer", async () => {
  const fixture = buildController({
    writeText: async () => {},
  });

  await fixture.controller.copy();
  await fixture.controller.copy();
  fixture.runScheduledReset(0);

  assert.deepEqual(fixture.clearedTimers, [1]);
  assert.equal(fixture.controller.labelTarget.textContent, "Copied!");

  fixture.runScheduledReset(1);

  assert.equal(fixture.controller.labelTarget.textContent, "Copy Prompt for AI");
});
