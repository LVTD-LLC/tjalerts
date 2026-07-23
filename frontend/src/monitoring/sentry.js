const readSentryConfig = () => {
  const configElement = document.getElementById("tjalerts-sentry-config");

  if (!configElement || !configElement.textContent) {
    return {};
  }

  try {
    return JSON.parse(configElement.textContent);
  } catch (_error) {
    return {};
  }
};

const addIntegration = (integrations, integrationFactory, options) => {
  if (typeof integrationFactory === "function") {
    integrations.push(integrationFactory(options));
  }
};

const initSentry = async (config) => {
  if (!config.dsn) {
    return;
  }

  const {
    browserTracingIntegration,
    consoleLoggingIntegration,
    init,
  } = await import("@sentry/browser");

  const integrations = [];
  addIntegration(integrations, browserTracingIntegration);

  if (config.enableLogs) {
    addIntegration(integrations, consoleLoggingIntegration, {
      levels: ["warn", "error"],
    });
  }

  init({
    dsn: config.dsn,
    environment: config.environment || undefined,
    release: config.release || undefined,
    integrations,
    sendDefaultPii: false,
    tracesSampleRate: config.tracesSampleRate,
    tracePropagationTargets: [config.siteUrl, /^\//].filter(Boolean),
    replaysSessionSampleRate: config.replaysSessionSampleRate,
    replaysOnErrorSampleRate: config.replaysOnErrorSampleRate,
    enableLogs: Boolean(config.enableLogs),
  });
};

const scheduleSentryInit = () => {
  const config = readSentryConfig();

  if (!config.dsn) {
    return;
  }

  const start = () => {
    initSentry(config).catch(() => {});
  };

  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(start, { timeout: 3000 });
    return;
  }

  window.setTimeout(start, 1500);
};

if (document.readyState === "complete") {
  scheduleSentryInit();
} else {
  window.addEventListener("load", scheduleSentryInit, { once: true });
}
