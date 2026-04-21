"use strict";

(() => {
  const chatLog = document.getElementById("chat-log");
  const walletMoney = document.getElementById("wallet-money");
  const walletCredits = document.getElementById("wallet-credits");
  const addCooldown = document.getElementById("add-cooldown");
  const resetButton = document.getElementById("reset-session");
  const composerForm = document.getElementById("composer-form");
  const composerInput = document.getElementById("composer-input");
  const sendButton = document.getElementById("send-btn");
  const quickButtons = Array.from(document.querySelectorAll(".quick-btn"));

  if (!chatLog || !walletMoney || !walletCredits || !addCooldown || !resetButton || !composerForm || !composerInput || !sendButton) {
    return;
  }

  const BOT_IDENTITY = {
    name: "Casino",
    avatar: "/static/demo/assets/bot-avatar.svg",
    tag: "APP",
  };

  const USER_IDENTITY = {
    name: "Visitor",
    avatar: "/static/demo/assets/user-avatar.svg",
  };

  const EMBED_COLORS = {
    info: "#5865f2",
  };

  const sessionId =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `demo-${Date.now()}-${Math.random().toString(16).slice(2)}`;

  const numberFormatter = new Intl.NumberFormat("en-US");

  const state = {
    config: {
      prefix: "$",
      defaultBet: 100,
      bonusMultiplier: 5,
      bonusCooldownHours: 12,
    },
    wallet: {
      money: 0,
      credits: 0,
    },
    commandAttempts: [],
    muteUntil: 0,
    acceptedAt: 0,
    lastCommandAt: 0,
    lastNormalizedCommand: "",
    lastUserText: "",
    lastUserTextNode: null,
    duplicateCount: 1,
    pendingCommandRequests: 0,
    pendingActionRequests: 0,
    uiRefreshTimerId: null,
    nextMessageId: 1,
    chatPinnedToBottom: true,
  };

  const formatMoney = (value) => `$${numberFormatter.format(Math.max(0, Math.trunc(value)))}`;
  const formatNumber = (value) => numberFormatter.format(Math.max(0, Math.trunc(value)));

  const formatHeaderTime = (date) => {
    const hour24 = date.getHours();
    const hour12 = hour24 % 12 || 12;
    const minutes = String(date.getMinutes()).padStart(2, "0");
    const suffix = hour24 >= 12 ? "PM" : "AM";
    return `${hour12}:${minutes}${suffix}`;
  };

  const escapeHtml = (raw) => {
    const map = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return raw.replace(/[&<>"']/g, (char) => map[char]);
  };

  const inlineMarkdownToHtml = (raw) => {
    const escaped = escapeHtml(raw || "");
    return escaped
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<span class=\"embed-inline-code\">$1</span>");
  };

  const scrollChatToBottom = () => {
    chatLog.scrollTop = chatLog.scrollHeight;
  };

  const isNearChatBottom = () => {
    return chatLog.scrollTop + chatLog.clientHeight >= chatLog.scrollHeight - 24;
  };

  const maybeScrollChatToBottom = (shouldScroll) => {
    if (shouldScroll) {
      scrollChatToBottom();
      state.chatPinnedToBottom = true;
    }
  };

  const createBaseEntry = (authorType) => {
    const entry = document.createElement("article");
    entry.className = `chat-entry ${authorType}`;
    entry.dataset.messageId = String(state.nextMessageId++);
    return entry;
  };

  const renderAvatar = (identity) => {
    const avatar = document.createElement("img");
    avatar.className = "avatar";
    avatar.src = identity.avatar;
    avatar.alt = `${identity.name} avatar`;
    return avatar;
  };

  const renderEntryHeader = (identity, includeAppTag) => {
    const header = document.createElement("div");
    header.className = "entry-header";

    const author = document.createElement("span");
    author.className = "author-name";
    author.textContent = identity.name;
    header.appendChild(author);

    if (includeAppTag) {
      const tag = document.createElement("span");
      tag.className = "bot-tag";
      tag.textContent = BOT_IDENTITY.tag;
      header.appendChild(tag);
    }

    const time = document.createElement("span");
    time.className = "message-time";
    time.textContent = formatHeaderTime(new Date());
    header.appendChild(time);

    return header;
  };

  const appendSystemMessage = (text) => {
    const shouldScroll = isNearChatBottom();
    const entry = createBaseEntry("system");
    const note = document.createElement("p");
    note.className = "system-note";
    note.textContent = text;
    entry.appendChild(note);
    chatLog.appendChild(entry);
    maybeScrollChatToBottom(shouldScroll);
    return entry;
  };

  const appendUserMessage = (text) => {
    const shouldScroll = isNearChatBottom();
    const entry = createBaseEntry("user");
    entry.appendChild(renderAvatar(USER_IDENTITY));

    const main = document.createElement("div");
    main.className = "entry-main";
    main.appendChild(renderEntryHeader(USER_IDENTITY, false));

    const content = document.createElement("div");
    content.className = "entry-content";

    const line = document.createElement("p");
    line.className = "message-text";
    line.textContent = text;

    content.appendChild(line);
    main.appendChild(content);
    entry.appendChild(main);
    chatLog.appendChild(entry);
    maybeScrollChatToBottom(shouldScroll);
    return line;
  };

  const setEntryButtonsDisabled = (entry, disabled) => {
    const buttons = entry.querySelectorAll("button.discord-btn");
    for (const button of buttons) {
      button.disabled = disabled;
    }
  };

  const renderEmbed = (embed, shouldScrollOnAsyncLoad) => {
    const box = document.createElement("section");
    box.className = "discord-embed";
    box.style.setProperty("--embed-color", embed.color || EMBED_COLORS.info);

    const body = document.createElement("div");
    body.className = "embed-body";

    if (embed.title) {
      const title = document.createElement("h4");
      title.className = "embed-title";
      title.textContent = embed.title;
      body.appendChild(title);
    }

    if (Array.isArray(embed.description_lines) && embed.description_lines.length > 0) {
      const description = document.createElement("div");
      description.className = "embed-description";
      for (const lineText of embed.description_lines) {
        const line = document.createElement("p");
        line.className = "embed-line";
        if (lineText.length === 0) {
          line.innerHTML = "&nbsp;";
        } else {
          line.innerHTML = inlineMarkdownToHtml(lineText);
        }
        description.appendChild(line);
      }
      body.appendChild(description);
    }

    if (Array.isArray(embed.fields) && embed.fields.length > 0) {
      const fields = document.createElement("div");
      fields.className = "embed-fields";
      for (const field of embed.fields) {
        const wrap = document.createElement("section");
        wrap.className = "embed-field";

        const name = document.createElement("h5");
        name.className = "embed-field-name";
        name.textContent = field.name || "";
        wrap.appendChild(name);

        const value = document.createElement("p");
        value.className = "embed-field-value";
        value.innerHTML = inlineMarkdownToHtml(String(field.value || "")).replace(/\n/g, "<br>");
        wrap.appendChild(value);

        fields.appendChild(wrap);
      }
      body.appendChild(fields);
    }

    if (embed.image_url) {
      const imageWrap = document.createElement("div");
      imageWrap.className = "embed-image";
      const image = document.createElement("img");
      if (shouldScrollOnAsyncLoad) {
        image.addEventListener("load", () => {
          if (state.chatPinnedToBottom) {
            scrollChatToBottom();
          }
        });
      }
      image.src = embed.image_url;
      image.alt = embed.title || "Attachment";
      imageWrap.appendChild(image);
      body.appendChild(imageWrap);
    }

    if (embed.footer) {
      const footer = document.createElement("p");
      footer.className = "embed-footer";
      footer.textContent = embed.footer;
      body.appendChild(footer);
    }

    box.appendChild(body);
    return box;
  };

  const submitAction = async (action, sourceEntry) => {
    if (!action || typeof action !== "object") {
      return;
    }

    const now = Date.now();
    registerAttempt(now);
    if (state.commandAttempts.length > 8) {
      state.muteUntil = now + 20000;
      appendSystemMessage("Burst spam detected. Demo chat muted for 20 seconds.");
      updateUiState();
      return;
    }

    const reason = currentBlockReason(now);
    if (reason) {
      appendSystemMessage(reason);
      updateUiState();
      return;
    }

    if (state.pendingActionRequests > 0) {
      return;
    }

    state.acceptedAt = now;
    setEntryButtonsDisabled(sourceEntry, true);

    state.pendingActionRequests += 1;
    updateUiState();
    try {
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), 12000);
      let response;
      try {
        response = await fetch("/api/demo/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({ session_id: sessionId, action }),
        });
      } finally {
        window.clearTimeout(timeoutId);
      }

      const payload = await response.json();
      applyServerResponse(payload);
      const hasActionableComponent = Array.isArray(payload.messages)
        && payload.messages.some((message) =>
          Array.isArray(message.components)
          && message.components.some((component) => component.action && !component.disabled)
        );
      const noProgress =
        payload
        && Array.isArray(payload.messages)
        && payload.messages.length === 0
        && payload.awaiting_action;
      const awaitingWithoutActions =
        payload
        && payload.awaiting_action
        && !hasActionableComponent;
      const shouldKeepSourceRow =
        payload.error
        || noProgress
        || awaitingWithoutActions
        || action.type !== "reaction";

      if (shouldKeepSourceRow) {
        setEntryButtonsDisabled(sourceEntry, false);
      } else if (sourceEntry && sourceEntry.isConnected) {
        sourceEntry.remove();
      }
    } catch (_error) {
      appendSystemMessage("Action request failed.");
      setEntryButtonsDisabled(sourceEntry, false);
    } finally {
      state.pendingActionRequests = Math.max(0, state.pendingActionRequests - 1);
      updateUiState();
    }
  };

  const appendBotMessage = (message) => {
    const shouldScroll = state.chatPinnedToBottom;
    const entry = createBaseEntry("bot");
    entry.appendChild(renderAvatar(BOT_IDENTITY));

    const main = document.createElement("div");
    main.className = "entry-main";
    main.appendChild(renderEntryHeader(BOT_IDENTITY, true));

    const content = document.createElement("div");
    content.className = "entry-content";

    if (message.content) {
      const line = document.createElement("p");
      line.className = "message-text";
      line.textContent = message.content;
      content.appendChild(line);
    }

    if (Array.isArray(message.embeds)) {
      for (const embed of message.embeds) {
        content.appendChild(renderEmbed(embed, shouldScroll));
      }
    }

    if (Array.isArray(message.components) && message.components.length > 0) {
      const row = document.createElement("div");
      row.className = "action-row";
      for (const component of message.components) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `discord-btn ${component.style || "secondary"}`;
        button.textContent = component.label || "Action";
        button.disabled = Boolean(component.disabled) || !component.action;
        button.addEventListener("click", () => {
          if (button.disabled) {
            return;
          }
          submitAction(component.action, entry);
        });
        row.appendChild(button);
      }
      content.appendChild(row);
    }

    main.appendChild(content);
    entry.appendChild(main);
    chatLog.appendChild(entry);
    maybeScrollChatToBottom(shouldScroll);
  };

  const applyServerResponse = (payload) => {
    if (!payload || typeof payload !== "object") {
      return;
    }

    if (payload.error) {
      appendSystemMessage(String(payload.error));
    }

    if (Array.isArray(payload.messages)) {
      for (const message of payload.messages) {
        appendBotMessage(message);
      }
    }

    if (payload.wallet && typeof payload.wallet === "object") {
      const money = Number(payload.wallet.money);
      const credits = Number(payload.wallet.credits);
      if (!Number.isNaN(money)) {
        state.wallet.money = money;
      }
      if (!Number.isNaN(credits)) {
        state.wallet.credits = credits;
      }
    }

    updateWalletView();
  };

  const registerAttempt = (timestampMs) => {
    state.commandAttempts.push(timestampMs);
    const cutoff = timestampMs - 15000;
    while (state.commandAttempts.length && state.commandAttempts[0] < cutoff) {
      state.commandAttempts.shift();
    }
  };

  const currentSlowdownMs = (timestampMs) => Math.max(0, 1000 - (timestampMs - state.acceptedAt));

  const currentBlockReason = (timestampMs) => {
    if (state.pendingCommandRequests > 0) {
      return "Waiting for server response...";
    }
    if (timestampMs < state.muteUntil) {
      const seconds = Math.ceil((state.muteUntil - timestampMs) / 1000);
      return `Muted for ${seconds}s after burst spam.`;
    }
    const slowdown = currentSlowdownMs(timestampMs);
    if (slowdown > 0) {
      return `Rate limited. Wait ${(slowdown / 1000).toFixed(1)}s.`;
    }
    return null;
  };

  const submitCommand = async (rawCommand, options = {}) => {
    const now = Date.now();
    const showUserMessage = options.showUserMessage !== false;
    const enforceSpamChecks = options.enforceSpamChecks !== false;

    if (enforceSpamChecks) {
      registerAttempt(now);
      if (state.commandAttempts.length > 8) {
        state.muteUntil = now + 20000;
        appendSystemMessage("Burst spam detected. Demo chat muted for 20 seconds.");
        updateUiState();
        return;
      }

      const reason = currentBlockReason(now);
      if (reason) {
        appendSystemMessage(reason);
        updateUiState();
        return;
      }

      const normalized = rawCommand.trim().toLowerCase().replace(/\s+/g, " ");
      if (normalized === state.lastNormalizedCommand && now - state.lastCommandAt < 1200) {
        state.duplicateCount += 1;
        if (state.lastUserTextNode) {
          state.lastUserTextNode.textContent = `${state.lastUserText} (x${state.duplicateCount})`;
        }
        appendSystemMessage("Duplicate command collapsed into one response.");
        updateUiState();
        return;
      }

      state.acceptedAt = now;
      state.lastCommandAt = now;
      state.lastNormalizedCommand = normalized;
      state.duplicateCount = 1;
    }

    if (showUserMessage) {
      state.lastUserText = rawCommand;
      state.lastUserTextNode = appendUserMessage(rawCommand);
    }

    state.pendingCommandRequests += 1;
    updateUiState();

    try {
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), 12000);
      let response;
      try {
        response = await fetch("/api/demo/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            session_id: sessionId,
            command: rawCommand,
          }),
        });
      } finally {
        window.clearTimeout(timeoutId);
      }
      const payload = await response.json();
      applyServerResponse(payload);
    } catch (_error) {
      appendSystemMessage("Command request failed.");
    } finally {
      state.pendingCommandRequests = Math.max(0, state.pendingCommandRequests - 1);
      updateUiState();
    }
  };

  const updateWalletView = () => {
    walletMoney.textContent = formatMoney(state.wallet.money);
    walletCredits.textContent = formatNumber(state.wallet.credits);
    addCooldown.textContent = "Server managed";
  };

  const clearUiRefreshTimer = () => {
    if (state.uiRefreshTimerId !== null) {
      window.clearTimeout(state.uiRefreshTimerId);
      state.uiRefreshTimerId = null;
    }
  };

  const scheduleUiRefresh = (delayMs) => {
    clearUiRefreshTimer();
    state.uiRefreshTimerId = window.setTimeout(() => {
      state.uiRefreshTimerId = null;
      updateUiState();
    }, Math.max(30, Math.ceil(delayMs)));
  };

  const updateUiState = () => {
    const now = Date.now();
    const reason = currentBlockReason(now);
    const blocked = Boolean(reason);

    composerInput.disabled = blocked;
    sendButton.disabled = blocked;
    for (const button of quickButtons) {
      button.disabled = blocked;
    }

    clearUiRefreshTimer();
    if (state.pendingCommandRequests === 0) {
      if (now < state.muteUntil) {
        scheduleUiRefresh((state.muteUntil - now) + 40);
      } else {
        const slowdown = currentSlowdownMs(now);
        if (slowdown > 0) {
          scheduleUiRefresh(slowdown + 40);
        }
      }
    }

    updateWalletView();
  };

  const refreshQuickButtons = () => {
    for (const button of quickButtons) {
      const template = button.dataset.template || "help";
      const command = `${state.config.prefix}${template}`;
      button.dataset.command = command;
      button.textContent = command;
    }
  };

  const resetDemoSession = async () => {
    state.pendingCommandRequests += 1;
    updateUiState();

    try {
      const response = await fetch("/api/demo/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      const payload = await response.json();

      chatLog.innerHTML = "";
      applyServerResponse(payload);
      await submitCommand(`${state.config.prefix}help`, {
        showUserMessage: false,
        enforceSpamChecks: false,
      });
    } catch (_error) {
      appendSystemMessage("Failed to reset demo session.");
    } finally {
      state.pendingCommandRequests = Math.max(0, state.pendingCommandRequests - 1);
      updateUiState();
    }
  };

  const loadConfig = async () => {
    try {
      const response = await fetch("/api/demo/config", { method: "GET" });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      if (typeof payload.prefix === "string" && payload.prefix.length > 0) {
        state.config.prefix = payload.prefix;
      }
      if (Number.isInteger(payload.defaultBet) && payload.defaultBet > 0) {
        state.config.defaultBet = payload.defaultBet;
      }
      if (Number.isInteger(payload.bonusMultiplier) && payload.bonusMultiplier > 0) {
        state.config.bonusMultiplier = payload.bonusMultiplier;
      }
      if (Number.isInteger(payload.bonusCooldownHours) && payload.bonusCooldownHours > 0) {
        state.config.bonusCooldownHours = payload.bonusCooldownHours;
      }
    } catch (_error) {
      appendSystemMessage("Config endpoint unavailable. Loaded demo defaults.");
    }
  };

  const installListeners = () => {
    chatLog.addEventListener("scroll", () => {
      state.chatPinnedToBottom = isNearChatBottom();
    });

    composerForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const raw = composerInput.value.trim();
      if (!raw) {
        return;
      }
      composerInput.value = "";
      submitCommand(raw);
    });

    resetButton.addEventListener("click", () => {
      resetDemoSession();
    });

    for (const button of quickButtons) {
      button.addEventListener("click", () => {
        const command = button.dataset.command || "";
        if (!command) {
          return;
        }
        submitCommand(command);
      });
    }
  };

  const boot = async () => {
    await loadConfig();
    refreshQuickButtons();
    installListeners();
    await resetDemoSession();
    state.chatPinnedToBottom = true;
    updateUiState();
  };

  boot();
})();
