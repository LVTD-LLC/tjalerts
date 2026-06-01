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

const initSentry = async () => {
  const config = readSentryConfig();

  if (!config.dsn) {
    return;
  }

  const Sentry = await import("@sentry/browser");
  const integrations = [];
  addIntegration(integrations, Sentry.browserTracingIntegration);
  addIntegration(integrations, Sentry.feedbackIntegration, {
    colorScheme: "system",
    showBranding: false,
  });
  addIntegration(integrations, Sentry.replayIntegration, {
    blockAllMedia: true,
    maskAllText: true,
  });
  addIntegration(integrations, Sentry.consoleLoggingIntegration, {
    levels: ["warn", "error"],
  });

  Sentry.init({
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

initSentry().catch(() => {});
