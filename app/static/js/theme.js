/**
 * Projexa — Production UI Engine & Theme Manager
 * Clean • High Performance • Production Standard
 */

(function () {
    "use strict";

    // 1. THEME MANAGER (DARK / LIGHT MODE)
    const THEME_STORAGE_KEY = "projexa_theme";

    function getPreferredTheme() {
        const saved = localStorage.getItem(THEME_STORAGE_KEY) || localStorage.getItem("projectguard_theme");
        if (saved === "dark" || saved === "light") {
            return saved;
        }
        return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light";
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem(THEME_STORAGE_KEY, theme);

        const toggleBtn = document.getElementById("themeToggleBtn");
        if (toggleBtn) {
            const icon = toggleBtn.querySelector("i");
            if (icon) {
                icon.className = theme === "dark" ? "fas fa-sun text-gold" : "fas fa-moon text-secondary";
            }
            toggleBtn.setAttribute("title", "Switch to " + (theme === "dark" ? "Light" : "Dark") + " Mode");
        }
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute("data-theme") || "light";
        const next = current === "dark" ? "light" : "dark";
        applyTheme(next);
    }

    applyTheme(getPreferredTheme());

    // 2. LOADING STATE SEQUENCER
    function initGeminiLoadingSteps(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        let currentStep = 0;
        const stepElements = container.querySelectorAll(".gemini-step-item");

        function advance() {
            if (currentStep < stepElements.length) {
                const el = stepElements[currentStep];
                el.classList.remove("step-pending");
                el.classList.add("step-active");

                const icon = el.querySelector(".step-icon");
                if (icon) {
                    icon.innerHTML = '<i class="fas fa-circle-notch fa-spin text-gold"></i>';
                }

                setTimeout(() => {
                    el.classList.remove("step-active");
                    el.classList.add("step-done");
                    if (icon) {
                        icon.innerHTML = '<i class="fas fa-check-circle text-success"></i>';
                    }
                    currentStep++;
                    if (currentStep < stepElements.length) {
                        advance();
                    }
                }, 1000);
            }
        }

        advance();
    }

    // 3. COPY PROMPT HELPER
    window.copyPrompt = function (button, promptText) {
        if (!promptText) return;

        function showSuccess() {
            const originalHTML = button.innerHTML;
            button.classList.add("btn-success");
            button.classList.remove("btn-outline-primary");
            button.innerHTML = '<i class="fas fa-check me-1"></i> Copied';

            if (window.showToast) {
                window.showToast("Copied", "AI prompt copied to clipboard.", "success");
            }

            setTimeout(() => {
                button.innerHTML = originalHTML;
                button.classList.remove("btn-success");
                button.classList.add("btn-outline-primary");
            }, 2000);
        }

        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(promptText).then(showSuccess).catch(() => fallbackCopy(promptText, showSuccess));
        } else {
            fallbackCopy(promptText, showSuccess);
        }
    };

    function fallbackCopy(text, cb) {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand("copy");
            if (cb) cb();
        } catch (err) {
            console.error("Fallback copy failed", err);
        }
        document.body.removeChild(ta);
    }

    // 4. TOAST NOTIFICATIONS
    window.showToast = function (title, message, type = "info") {
        let toastContainer = document.getElementById("pgToastContainer");
        if (!toastContainer) {
            toastContainer = document.createElement("div");
            toastContainer.id = "pgToastContainer";
            toastContainer.className = "toast-container position-fixed bottom-0 end-0 p-3";
            toastContainer.style.zIndex = "9999";
            document.body.appendChild(toastContainer);
        }

        const toastId = "toast_" + Date.now();
        const icon = type === "success" ? "fa-check-circle text-success" : type === "danger" ? "fa-exclamation-circle text-danger" : "fa-info-circle text-primary";

        const toastEl = document.createElement("div");
        toastEl.className = "toast align-items-center border shadow-sm";
        toastEl.setAttribute("role", "alert");
        toastEl.setAttribute("aria-live", "assertive");
        toastEl.setAttribute("aria-atomic", "true");
        toastEl.id = toastId;

        toastEl.innerHTML = '<div class="d-flex p-2"><div class="toast-body d-flex align-items-center gap-2 py-1 px-2"><i class="fas ' + icon + ' fs-6"></i><div><strong class="d-block small">' + title + '</strong><span class="small text-muted">' + message + '</span></div></div><button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"></button></div>';

        toastContainer.appendChild(toastEl);
        const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
        toast.show();
        toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
    };

    // 5. SIDEBAR CONTROLLER (RESPONSIVE APP SHELL)
    window.toggleAppSidebar = function () {
        const sidebar = document.getElementById("appSidebar");
        const backdrop = document.getElementById("sidebarBackdrop");
        if (sidebar) {
            sidebar.classList.toggle("show");
        }
        if (backdrop) {
            backdrop.classList.toggle("show");
        }
    };

    // 6. COMMAND PALETTE CONTROLLER (⌘K / Ctrl+K)
    window.openCommandPalette = function () {
        const modalEl = document.getElementById("cmdPaletteModal");
        if (!modalEl) return;
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
        setTimeout(() => {
            const input = document.getElementById("cmdPaletteInput");
            if (input) {
                input.value = "";
                input.focus();
                filterCommands("");
            }
        }, 150);
    };

    function filterCommands(query) {
        const q = (query || "").toLowerCase().trim();
        const items = document.querySelectorAll(".cmd-palette-item");
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            if (!q || text.includes(q)) {
                item.style.display = "flex";
            } else {
                item.style.display = "none";
            }
        });
    }

    // Keyboard shortcut listener for Cmd+K / Ctrl+K
    document.addEventListener("keydown", (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            window.openCommandPalette();
        }
    });

    // 7. DOM INITIALIZATION
    document.addEventListener("DOMContentLoaded", () => {
        const themeBtn = document.getElementById("themeToggleBtn");
        if (themeBtn) {
            themeBtn.addEventListener("click", toggleTheme);
        }

        const cmdInput = document.getElementById("cmdPaletteInput");
        if (cmdInput) {
            cmdInput.addEventListener("input", (e) => {
                filterCommands(e.target.value);
            });
        }
    });

    // Public API & Backwards-compatible stubs
    window.ProjexaTheme = {
        applyTheme,
        toggleTheme,
        openCommandPalette: window.openCommandPalette,
        initGeminiLoadingSteps,
        init3DTiltCards: function () {},
        AIAssistantOrb: function () {
            return { setState: function () {} };
        }
    };
    window.ProjectGuardTheme = window.ProjexaTheme;
})();

