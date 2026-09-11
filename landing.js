(() => {
  "use strict";

  const runtimeConfig = window.MERCHANTOS_CONFIG || {};
  let authenticated = false;
  let pendingDestination = runtimeConfig.home || "/";
  for (const link of document.querySelectorAll("[data-app]")) {
    const destination = runtimeConfig[link.dataset.app];
    if (destination) {
      link.href = destination;
      link.target = "_self";
    }
  }

  const authDialog = document.querySelector("#auth-dialog");
  const authStatus = document.querySelector(".auth-status");
  const authTabs = Array.from(document.querySelectorAll("[data-auth-tab]"));
  const authForms = Array.from(document.querySelectorAll("[data-auth-form]"));
  const googleAuthButton = document.querySelector("[data-google-auth]");

  if (!runtimeConfig.googleAuthEnabled) {
    googleAuthButton.disabled = true;
    googleAuthButton.setAttribute("aria-disabled", "true");
    googleAuthButton.title = "Add a Google OAuth web client to enable this option.";
    googleAuthButton.querySelector("span").textContent = "Google sign-in · setup required";
    googleAuthButton.querySelector("i").textContent = "◇";
    const setupNote = document.querySelector("[data-google-auth-note]");
    if (setupNote) {
      setupNote.textContent = runtimeConfig.googleAuthSetupMessage || "Google OAuth credentials are missing.";
      setupNote.hidden = false;
    }
  }

  const passwordMinimum = Number(runtimeConfig.authMinPasswordLength);
  const passwordMaximum = Number(runtimeConfig.authMaxPasswordLength);
  const nameMaximum = Number(runtimeConfig.authMaxNameLength);
  for (const input of document.querySelectorAll('input[name="password"]')) {
    if (Number.isInteger(passwordMinimum) && passwordMinimum > 0) input.minLength = passwordMinimum;
    if (Number.isInteger(passwordMaximum) && passwordMaximum >= passwordMinimum) input.maxLength = passwordMaximum;
  }
  const nameInput = document.querySelector('input[name="displayName"]');
  if (nameInput && Number.isInteger(nameMaximum) && nameMaximum > 0) nameInput.maxLength = nameMaximum;
  const passwordGuidance = document.querySelector("#password-guidance");
  if (passwordGuidance && Number.isInteger(passwordMinimum)) {
    passwordGuidance.textContent = `Use at least ${passwordMinimum} characters with letters and numbers.`;
  }

  const allowedDestinations = new Set(
    [runtimeConfig.home, runtimeConfig.agent1, runtimeConfig.agent2, runtimeConfig.agent3].filter(Boolean)
  );

  const safeDestination = (candidate) => {
    try {
      const normalized = new URL(candidate, window.location.href).origin + new URL(candidate, window.location.href).pathname.replace(/\/$/, "");
      return Array.from(allowedDestinations).find((url) => url.replace(/\/$/, "") === normalized) || runtimeConfig.home;
    } catch (_) {
      return runtimeConfig.home;
    }
  };

  const selectAuthTab = (name) => {
    for (const tab of authTabs) {
      tab.setAttribute("aria-selected", String(tab.dataset.authTab === name));
    }
    for (const form of authForms) {
      form.hidden = form.dataset.authForm !== name;
    }
    authStatus.textContent = "";
    authStatus.classList.remove("success");
  };

  const openAuth = (destination, tab = "signin") => {
    pendingDestination = safeDestination(destination);
    selectAuthTab(tab);
    if (!authDialog.open) authDialog.showModal();
    window.setTimeout(() => authDialog.querySelector("form:not([hidden]) input")?.focus(), 0);
  };

  googleAuthButton.addEventListener("click", () => {
    if (!runtimeConfig.googleAuthEnabled) {
      return;
    }
    const destination = encodeURIComponent(safeDestination(pendingDestination));
    window.location.assign(`/api/auth/google/start?next=${destination}`);
  });

  const authRequest = async (path, payload = {}) => {
    const response = await fetch(path, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json().catch(() => ({ ok: false, error: "Unexpected server response." }));
    if (!response.ok) throw new Error(result.error || "Unable to complete this request.");
    return result;
  };

  for (const tab of authTabs) {
    tab.addEventListener("click", () => selectAuthTab(tab.dataset.authTab));
  }
  document.querySelector(".auth-close").addEventListener("click", () => authDialog.close());
  authDialog.addEventListener("click", (event) => {
    if (event.target === authDialog) authDialog.close();
  });

  for (const form of authForms) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submit = form.querySelector("button[type=submit]");
      const values = Object.fromEntries(new FormData(form));
      submit.disabled = true;
      authStatus.textContent = "Securing your session…";
      authStatus.classList.remove("success");
      try {
        await authRequest(`/api/auth/${form.dataset.authForm === "signin" ? "login" : "register"}`, values);
        authenticated = true;
        authStatus.textContent = "Success. Opening your workspace…";
        authStatus.classList.add("success");
        window.location.assign(pendingDestination);
      } catch (error) {
        authStatus.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
  }

  for (const link of document.querySelectorAll("[data-app]")) {
    link.addEventListener("click", (event) => {
      if (!authenticated) {
        event.preventDefault();
        openAuth(link.href);
      }
    });
  }

  const query = new URLSearchParams(window.location.search);
  const oauthErrors = {
    not_configured: "Google sign-in is not configured for this deployment yet.",
    state: "The Google sign-in request could not be verified. Please try again.",
    expired: "The Google sign-in request expired. Please try again.",
    cancelled: "Google sign-in was cancelled.",
    verification: "Google could not verify this account. Please try again.",
  };
  if (query.get("logout") === "1") {
    authRequest("/api/auth/logout").finally(() => window.location.replace("/"));
  } else {
    fetch("/api/auth/me", { credentials: "same-origin", cache: "no-store" })
      .then((response) => response.json())
      .then((result) => {
        authenticated = Boolean(result.authenticated);
        const headerText = document.querySelector(".header-contact span");
        if (headerText) headerText.textContent = authenticated ? "Open workspace" : "Sign in";
      })
      .catch(() => { authenticated = false; });
    if (query.get("auth")) {
      openAuth(query.get("next"), query.get("auth") === "register" ? "register" : "signin");
      if (query.get("oauth_error")) {
        authStatus.textContent = oauthErrors[query.get("oauth_error")] || "Google sign-in could not be completed.";
      }
    }
  }

  for (const source of document.querySelectorAll("[data-video-source]")) {
    const sourceUrl = runtimeConfig.videos && runtimeConfig.videos[source.dataset.videoSource];
    if (sourceUrl) {
      source.src = sourceUrl;
      source.parentElement.load();
    }
  }

  const videos = Array.from(document.querySelectorAll(".js-autoplay-video"));

  const playVideos = () => {
    for (const video of videos) {
      video.muted = true;
      video.defaultMuted = true;
      const attempt = video.play();
      if (attempt && typeof attempt.catch === "function") {
        attempt.catch(() => {});
      }
    }
  };

  playVideos();
  const retryInterval = Number(runtimeConfig.videoRetryIntervalMs);
  if (Number.isFinite(retryInterval) && retryInterval > 0) {
    window.setInterval(playVideos, retryInterval);
  }

  const playAfterGesture = () => {
    playVideos();
    document.removeEventListener("click", playAfterGesture);
    document.removeEventListener("touchstart", playAfterGesture);
  };

  document.addEventListener("click", playAfterGesture, { passive: true });
  document.addEventListener("touchstart", playAfterGesture, { passive: true });

  const menuButton = document.querySelector(".menu-toggle");
  const mobileMenu = document.querySelector(".mobile-menu");
  const mobileBreakpoint = 700;

  const setMenuOpen = (open) => {
    menuButton.setAttribute("aria-expanded", String(open));
    menuButton.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    mobileMenu.hidden = !open;
    document.body.classList.toggle("menu-open", open);
  };

  menuButton.addEventListener("click", () => {
    setMenuOpen(menuButton.getAttribute("aria-expanded") !== "true");
  });

  mobileMenu.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      setMenuOpen(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menuButton.getAttribute("aria-expanded") === "true") {
      setMenuOpen(false);
      menuButton.focus();
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > mobileBreakpoint) {
      setMenuOpen(false);
    }
  });
})();
