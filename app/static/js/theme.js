/**
 * ProjectGuard — Modern Futuristic Theme & Interactive 3D UI Engine
 * Features:
 * 1. Dark / Light Mode with localStorage persistence & system preference
 * 2. Ambient Neural Network & Particle Canvas Background
 * 3. 3D Tilt Card physics with dynamic glare & smooth spring return
 * 4. Interactive 3D AI Assistant Orb (Idle, Thinking, Completed states)
 * 5. Multi-Step Gemini Loading Sequence
 * 6. Micro-interactions & Smooth Transitions
 */

(function () {
    "use strict";

    // 1. THEME MANAGER (DARK / LIGHT MODE)
    const THEME_STORAGE_KEY = "projectguard_theme";

    function getPreferredTheme() {
        const saved = localStorage.getItem(THEME_STORAGE_KEY);
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
                icon.className = theme === "dark" ? "fas fa-sun text-warning" : "fas fa-moon text-light";
            }
            toggleBtn.setAttribute("title", "Switch to " + (theme === "dark" ? "Light" : "Dark") + " Mode");
        }

        if (window.NeuralCanvas) {
            window.NeuralCanvas.setTheme(theme);
        }
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute("data-theme") || "light";
        const next = current === "dark" ? "light" : "dark";
        applyTheme(next);
    }

    applyTheme(getPreferredTheme());

    // 2. AMBIENT NEURAL NETWORK & PARTICLE CANVAS BACKGROUND
    class NeuralBackground {
        constructor() {
            this.canvas = document.getElementById("neural-bg-canvas");
            if (!this.canvas) return;

            this.ctx = this.canvas.getContext("2d");
            this.particles = [];
            this.particleCount = 45;
            this.maxDistance = 140;
            this.width = 0;
            this.height = 0;
            this.animationFrameId = null;
            this.theme = document.documentElement.getAttribute("data-theme") || "light";
            this.mouse = { x: null, y: null, radius: 120 };
            this.prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

            this.init();
        }

        init() {
            this.resize();
            window.addEventListener("resize", () => this.resize());

            window.addEventListener("mousemove", (e) => {
                this.mouse.x = e.clientX;
                this.mouse.y = e.clientY;
            });
            window.addEventListener("mouseleave", () => {
                this.mouse.x = null;
                this.mouse.y = null;
            });

            this.createParticles();
            if (!this.prefersReducedMotion) {
                this.animate();
            } else {
                this.renderStatic();
            }

            document.addEventListener("visibilitychange", () => {
                if (document.hidden) {
                    if (this.animationFrameId) cancelAnimationFrame(this.animationFrameId);
                } else if (!this.prefersReducedMotion) {
                    this.animate();
                }
            });
        }

        setTheme(theme) {
            this.theme = theme;
        }

        resize() {
            this.width = this.canvas.width = window.innerWidth;
            this.height = this.canvas.height = window.innerHeight;
            this.particleCount = this.width < 768 ? 20 : 45;
        }

        createParticles() {
            this.particles = [];
            for (let i = 0; i < this.particleCount; i++) {
                this.particles.push({
                    x: Math.random() * this.width,
                    y: Math.random() * this.height,
                    vx: (Math.random() - 0.5) * 0.45,
                    vy: (Math.random() - 0.5) * 0.45,
                    radius: Math.random() * 2 + 1.2,
                    alpha: Math.random() * 0.5 + 0.2
                });
            }
        }

        renderStatic() {
            this.ctx.clearRect(0, 0, this.width, this.height);
        }

        animate() {
            this.ctx.clearRect(0, 0, this.width, this.height);

            const isDark = this.theme === "dark";
            const nodePrefix = isDark ? "rgba(56, 189, 248, " : "rgba(59, 130, 246, ";
            const linePrefix = isDark ? "rgba(99, 102, 241, " : "rgba(147, 197, 253, ";

            for (let i = 0; i < this.particles.length; i++) {
                const p = this.particles[i];

                p.x += p.vx;
                p.y += p.vy;

                if (p.x < 0 || p.x > this.width) p.vx *= -1;
                if (p.y < 0 || p.y > this.height) p.vy *= -1;

                if (this.mouse.x !== null) {
                    const dx = p.x - this.mouse.x;
                    const dy = p.y - this.mouse.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < this.mouse.radius) {
                        const force = (this.mouse.radius - dist) / this.mouse.radius;
                        p.x += (dx / dist) * force * 1.5;
                        p.y += (dy / dist) * force * 1.5;
                    }
                }

                this.ctx.beginPath();
                this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                this.ctx.fillStyle = nodePrefix + (isDark ? p.alpha : p.alpha * 0.6) + ")";
                this.ctx.fill();

                for (let j = i + 1; j < this.particles.length; j++) {
                    const p2 = this.particles[j];
                    const dx = p.x - p2.x;
                    const dy = p.y - p2.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < this.maxDistance) {
                        const alpha = (1 - dist / this.maxDistance) * (isDark ? 0.22 : 0.12);
                        this.ctx.beginPath();
                        this.ctx.moveTo(p.x, p.y);
                        this.ctx.lineTo(p2.x, p2.y);
                        this.ctx.strokeStyle = linePrefix + alpha + ")";
                        this.ctx.lineWidth = 0.8;
                        this.ctx.stroke();
                    }
                }
            }

            this.animationFrameId = requestAnimationFrame(() => this.animate());
        }
    }

    // 3. SUBTLE 3D TILT CARDS PHYSICS
    function init3DTiltCards() {
        const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (prefersReducedMotion || window.innerWidth < 992) {
            return;
        }

        const cards = document.querySelectorAll(".card-3d, .card-stat, .card-modern-tilt");

        cards.forEach((card) => {
            if (card.dataset.tiltInitialized) return;
            card.dataset.tiltInitialized = "true";

            let bounds;
            let mouseX = 0;
            let mouseY = 0;
            let isHovering = false;

            function updateTransform() {
                if (!isHovering) {
                    card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)";
                    card.style.boxShadow = "";
                    return;
                }

                const centerX = bounds.width / 2;
                const centerY = bounds.height / 2;
                const percentX = (mouseX - centerX) / centerX;
                const percentY = (mouseY - centerY) / centerY;

                const maxDeg = 2.5;
                const rotX = -percentY * maxDeg;
                const rotY = percentX * maxDeg;

                card.style.transform = "perspective(1000px) rotateX(" + rotX.toFixed(2) + "deg) rotateY(" + rotY.toFixed(2) + "deg) translateZ(3px)";
                
                const shadowX = -percentX * 4;
                const shadowY = -percentY * 6 + 6;
                card.style.boxShadow = shadowX.toFixed(1) + "px " + shadowY.toFixed(1) + "px 14px rgba(0, 0, 0, 0.08)";
            }

            card.addEventListener("mouseenter", () => {
                isHovering = true;
                bounds = card.getBoundingClientRect();
                card.style.transition = "transform 0.1s ease-out, box-shadow 0.2s ease-out";
            });

            card.addEventListener("mousemove", (e) => {
                if (!bounds) bounds = card.getBoundingClientRect();
                mouseX = e.clientX - bounds.left;
                mouseY = e.clientY - bounds.top;
                requestAnimationFrame(updateTransform);
            });

            card.addEventListener("mouseleave", () => {
                isHovering = false;
                card.style.transition = "transform 0.4s cubic-bezier(0.25, 1, 0.5, 1), box-shadow 0.4s ease-out";
                updateTransform();
            });
        });
    }

    // 4. INTERACTIVE 3D AI ASSISTANT ORB
    class AIAssistantOrb {
        constructor(containerId, options = {}) {
            this.container = document.getElementById(containerId);
            if (!this.container) return;

            this.size = options.size || 160;
            this.state = options.state || "idle";
            this.canvas = document.createElement("canvas");
            this.canvas.width = this.size;
            this.canvas.height = this.size;
            this.canvas.className = "ai-orb-canvas";
            this.container.innerHTML = "";
            this.container.appendChild(this.canvas);
            this.ctx = this.canvas.getContext("2d");

            this.angle = 0;
            this.pulse = 0;
            this.particles = [];
            this.initParticles();
            this.animate();

            this.container.addEventListener("mouseenter", () => {
                if (this.state === "idle") this.setState("thinking");
            });
            this.container.addEventListener("mouseleave", () => {
                if (this.state === "thinking" && !this.lockedState) this.setState("idle");
            });
        }

        initParticles() {
            this.particles = [];
            const count = 36;
            for (let i = 0; i < count; i++) {
                this.particles.push({
                    theta: Math.random() * Math.PI * 2,
                    phi: Math.acos(Math.random() * 2 - 1),
                    radius: (this.size * 0.35) + (Math.random() * 8 - 4),
                    speed: 0.015 + Math.random() * 0.015,
                    size: Math.random() * 2 + 1.5,
                    hue: Math.random() * 60 + 190
                });
            }
        }

        setState(newState, locked = false) {
            this.state = newState;
            this.lockedState = locked;
        }

        animate() {
            this.ctx.clearRect(0, 0, this.size, this.size);
            const cx = this.size / 2;
            const cy = this.size / 2;
            const isDark = document.documentElement.getAttribute("data-theme") === "dark";

            let speedMult = 1;
            let corePulseRate = 0.03;
            let coreColor1 = "rgba(59, 130, 246, 0.45)";
            let coreColor2 = "rgba(99, 102, 241, 0.2)";

            if (this.state === "thinking") {
                speedMult = 2.8;
                corePulseRate = 0.08;
                coreColor1 = "rgba(6, 182, 212, 0.65)";
                coreColor2 = "rgba(168, 85, 247, 0.35)";
            } else if (this.state === "completed") {
                speedMult = 1.2;
                coreColor1 = "rgba(16, 185, 129, 0.65)";
                coreColor2 = "rgba(5, 150, 105, 0.25)";
            }

            this.angle += 0.015 * speedMult;
            this.pulse += corePulseRate;
            const pulseScale = 1 + Math.sin(this.pulse) * 0.08;

            const grad = this.ctx.createRadialGradient(
                cx, cy, 5,
                cx, cy, (this.size * 0.32) * pulseScale
            );
            grad.addColorStop(0, coreColor1);
            grad.addColorStop(0.65, coreColor2);
            grad.addColorStop(1, "rgba(0, 0, 0, 0)");

            this.ctx.beginPath();
            this.ctx.arc(cx, cy, (this.size * 0.34) * pulseScale, 0, Math.PI * 2);
            this.ctx.fillStyle = grad;
            this.ctx.fill();

            const innerGrad = this.ctx.createRadialGradient(
                cx - 3, cy - 3, 1,
                cx, cy, 14 * pulseScale
            );
            innerGrad.addColorStop(0, "#ffffff");
            innerGrad.addColorStop(0.4, this.state === "completed" ? "#34d399" : "#38bdf8");
            innerGrad.addColorStop(1, "rgba(56, 189, 248, 0)");

            this.ctx.beginPath();
            this.ctx.arc(cx, cy, 14 * pulseScale, 0, Math.PI * 2);
            this.ctx.fillStyle = innerGrad;
            this.ctx.fill();

            this.ctx.save();
            this.ctx.translate(cx, cy);

            const ringCount = 2;
            for (let r = 0; r < ringCount; r++) {
                this.ctx.beginPath();
                const rot = this.angle * (r === 0 ? 1 : -1.2);
                this.ctx.ellipse(0, 0, (this.size * 0.38), (this.size * 0.16), rot + (r * 0.8), 0, Math.PI * 2);
                this.ctx.strokeStyle = this.state === "completed"
                    ? "rgba(52, 211, 153, 0.45)"
                    : isDark ? "rgba(56, 189, 248, 0.45)" : "rgba(59, 130, 246, 0.35)";
                this.ctx.lineWidth = 1.2;
                this.ctx.stroke();
            }

            this.particles.forEach((p) => {
                p.theta += p.speed * speedMult;
                const x = p.radius * Math.sin(p.phi) * Math.cos(p.theta);
                const y = p.radius * Math.sin(p.phi) * Math.sin(p.theta);
                const z = p.radius * Math.cos(p.phi);

                const cosA = Math.cos(this.angle);
                const sinA = Math.sin(this.angle);
                const rx = x * cosA - z * sinA;
                const rz = z * cosA + x * sinA;

                const depthScale = (rz + this.size * 0.5) / (this.size);
                const alpha = Math.max(0.15, Math.min(0.9, depthScale));

                this.ctx.beginPath();
                this.ctx.arc(rx, y, p.size * depthScale, 0, Math.PI * 2);
                this.ctx.fillStyle = "hsla(" + p.hue + ", 85%, 65%, " + alpha + ")";
                this.ctx.fill();
            });

            this.ctx.restore();

            requestAnimationFrame(() => this.animate());
        }
    }

    // 5. GEMINI MULTI-STEP ANIMATED LOADING
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
                    icon.innerHTML = '<i class="fas fa-spinner fa-spin text-primary"></i>';
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
                }, 1300);
            }
        }

        advance();
    }

    // 6. GLOBAL HELPERS
    window.copyPrompt = function (button, promptText) {
        if (!promptText) return;

        function showSuccess() {
            const originalHTML = button.innerHTML;
            button.classList.add("btn-copied");
            button.innerHTML = '<i class="fas fa-check me-1"></i> Copied!';
            showToast("Success", "AI prompt copied to clipboard! Ready to paste into ChatGPT or Claude.", "success");

            setTimeout(() => {
                button.innerHTML = originalHTML;
                button.classList.remove("btn-copied");
            }, 2200);
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
        toastEl.className = "toast align-items-center border-0 shadow-lg modern-toast";
        toastEl.setAttribute("role", "alert");
        toastEl.setAttribute("aria-live", "assertive");
        toastEl.setAttribute("aria-atomic", "true");
        toastEl.id = toastId;

        toastEl.innerHTML = '<div class="d-flex"><div class="toast-body d-flex align-items-center gap-2 py-3 px-3"><i class="fas ' + icon + ' fs-5"></i><div><strong class="d-block small">' + title + '</strong><span class="small text-muted">' + message + '</span></div></div><button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"></button></div>';

        toastContainer.appendChild(toastEl);
        const toast = new bootstrap.Toast(toastEl, { delay: 3500 });
        toast.show();
        toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
    };

    // 7. INITIALIZATION ON DOM READY
    document.addEventListener("DOMContentLoaded", () => {
        window.NeuralCanvas = new NeuralBackground();
        init3DTiltCards();

        const themeBtn = document.getElementById("themeToggleBtn");
        if (themeBtn) {
            themeBtn.addEventListener("click", toggleTheme);
        }

        document.querySelectorAll("[data-ai-orb]").forEach((el) => {
            const size = parseInt(el.dataset.orbSize, 10) || 160;
            const state = el.dataset.orbState || "idle";
            const orb = new AIAssistantOrb(el.id, { size, state });
            el._aiOrb = orb;
        });

        document.querySelectorAll(".task-checkbox").forEach((cb) => {
            cb.addEventListener("change", function () {
                const row = this.closest(".task-item-row") || this.closest(".card");
                if (row) {
                    if (this.checked) {
                        row.classList.add("task-completed-anim");
                    } else {
                        row.classList.remove("task-completed-anim");
                    }
                }
            });
        });
    });

    window.ProjectGuardTheme = {
        applyTheme,
        toggleTheme,
        AIAssistantOrb,
        initGeminiLoadingSteps,
        init3DTiltCards
    };
})();
