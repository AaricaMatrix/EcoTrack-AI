/* ═══════════════════════════════════════════════════════
   ECOTRACK AI — Complete Frontend
   Single source of truth — no duplicate function overrides
═══════════════════════════════════════════════════════ */

      const API_BASE = "https://aaricacoding-ecotrack-ai.hf.space";
      const DEMO_MODE = false;

      const appState = {
        currentStep: 0,
        result: null,
        tips: null,
        forecast: null,
        token: null,
        userName: null,
        donutChart: null,
        forecastChart: null,
      };

      /* ── MOBILE NAV ─────────────────────────────────────────────────── */
      function toggleMobileNav() {
        const menu = document.getElementById("nav-menu");
        const btn = document.getElementById("hamburger-btn");
        const overlay = document.getElementById("nav-overlay");
        if (menu.classList.contains("mobile-open")) {
          closeMobileNav();
        } else {
          menu.classList.add("mobile-open");
          btn.classList.add("open");
          btn.setAttribute("aria-expanded", "true");
          overlay.classList.remove("hidden");
          document.body.style.overflow = "hidden";
        }
      }
      function closeMobileNav() {
        const menu = document.getElementById("nav-menu");
        const btn = document.getElementById("hamburger-btn");
        const overlay = document.getElementById("nav-overlay");
        menu.classList.remove("mobile-open");
        btn.classList.remove("open");
        btn.setAttribute("aria-expanded", "false");
        overlay.classList.add("hidden");
        document.body.style.overflow = "";
      }
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeMobileNav();
      });

      /* ── PAGE NAVIGATION — single master function, no overrides ─────── */
      function navTo(pageName) {
        closeMobileNav();
        // Hide all pages
        document
          .querySelectorAll("section[id^='page-']")
          .forEach((s) => s.classList.add("hidden"));
        // Deactivate all tabs
        document.querySelectorAll(".nav-tab").forEach((t) => {
          t.classList.remove("active");
          t.setAttribute("aria-selected", "false");
        });
        // Show requested page
        const page = document.getElementById(`page-${pageName}`);
        if (page) page.classList.remove("hidden");
        const tab = document.getElementById(`tab-${pageName}`);
        if (tab) {
          tab.classList.add("active");
          tab.setAttribute("aria-selected", "true");
        }
        window.scrollTo({ top: 0, behavior: "smooth" });
        // Page-specific actions
        if (pageName === "insights" && appState.result) loadAIInsights();
        if (pageName === "offset") loadOffsetContent();
        if (pageName === "community") loadCommunityContent();
        if (pageName === "badges") renderBadgesPage();
      }

      /* ── STEP NAVIGATION ─────────────────────────────────────────────── */
      function goStep(n) {
        document
          .getElementById(`calc-step-${appState.currentStep}`)
          .classList.add("hidden");
        document.getElementById(`calc-step-${n}`).classList.remove("hidden");
        for (let i = 0; i < 4; i++) {
          const s = document.getElementById(`step-${i}`);
          s.classList.remove("active", "done");
          if (i < n) s.classList.add("done");
          else if (i === n) s.classList.add("active");
        }
        for (let i = 0; i < 3; i++)
          document.getElementById(`line-${i}`).classList.toggle("done", i < n);
        appState.currentStep = n;
      }

      /* ── LOCAL CARBON CALCULATION ────────────────────────────────────── */
      const EF = {
        car: {
          petrol: 0.192,
          diesel: 0.171,
          hybrid: 0.11,
          electric: 0.053,
          none: 0,
        },
        transit: 0.089,
        flight_short: 255,
        flight_long: 1050,
        elec: 0.716,
        gas: 2.03,
        diet: {
          vegan: 1500,
          vegetarian: 1700,
          pescatarian: 2000,
          omnivore: 2500,
        },
        meat: 3.5,
        waste: { low: 1.0, medium: 1.15, high: 1.3 },
        clothing: 10,
        electronics: 300,
        order: 0.5,
      };

      function calcLocal(f) {
        const carEm = parseFloat(f.carKm) * 52 * (EF.car[f.fuelType] || 0.192);
        const transitEm = parseFloat(f.transitKm) * 52 * EF.transit;
        const flightEm =
          parseFloat(f.flights) * 0.5 * EF.flight_short +
          parseFloat(f.flights) * 0.5 * EF.flight_long;
        const transport = Math.round(carEm + transitEm + flightEm);
        const elecEm =
          parseFloat(f.electricity) *
          12 *
          EF.elec *
          (1 - parseFloat(f.solar) / 100);
        const gasEm = parseFloat(f.gas) * 12 * EF.gas;
        const home = Math.round(
          (elecEm + gasEm) / Math.max(parseInt(f.people), 1),
        );
        const dietBase = EF.diet[f.dietType] || 2500;
        const meatAdj = Math.max(0, parseFloat(f.meatMeals) - 7) * 52 * EF.meat;
        const diet = Math.round(
          (dietBase + meatAdj) * (EF.waste[f.wasteLevel] || 1.15),
        );
        const shopping = Math.round(
          parseInt(f.clothes) * EF.clothing +
            parseInt(f.electronics) * EF.electronics +
            parseFloat(f.onlineOrders) * 12 * EF.order,
        );
        const total = transport + home + diet + shopping;
        const rating =
          total < 1500
            ? "excellent"
            : total < 2500
              ? "good"
              : total < 4000
                ? "average"
                : total < 7000
                  ? "high"
                  : "critical";
        const percentile =
          total < 1000
            ? 5
            : total < 2000
              ? 20
              : total < 3000
                ? 40
                : total < 4500
                  ? 60
                  : total < 7000
                    ? 80
                    : 90;
        return {
          footprint: { transport, home_energy: home, diet, shopping, total },
          rating,
          percentile,
          global_avg_kg: 4000,
          india_avg_kg: 1800,
        };
      }

      function forecastLocal(total) {
        const months = [],
          predicted = [],
          now = new Date();
        const mn = [
          "Jan",
          "Feb",
          "Mar",
          "Apr",
          "May",
          "Jun",
          "Jul",
          "Aug",
          "Sep",
          "Oct",
          "Nov",
          "Dec",
        ];
        for (let i = 1; i <= 6; i++) {
          const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
          months.push(`${mn[d.getMonth()]} ${d.getFullYear()}`);
          predicted.push(
            Math.round(
              total * Math.pow(0.98, i) * (1 + (Math.random() * 0.04 - 0.02)),
            ),
          );
        }
        return {
          months,
          predicted_kg: predicted,
          trend: "improving",
          reduction_potential_kg: Math.round(total * 0.25),
        };
      }

      function genTips(fp) {
        const tips = [];
        const { transport, home_energy, diet, shopping } = fp;
        if (transport > 1500)
          tips.push({
            icon: "🚗",
            title: "Switch to an EV",
            desc: "EVs cut transport emissions by 70%. India FAME-II subsidies help.",
            impact: Math.round(transport * 0.65),
            difficulty: "hard",
          });
        if (transport > 400)
          tips.push({
            icon: "🏠",
            title: "Work from home 2 days/week",
            desc: "Reducing commute by 40% directly cuts car emissions.",
            impact: Math.round(transport * 0.2),
            difficulty: "medium",
          });
        if (transport > 250)
          tips.push({
            icon: "🚂",
            title: "Replace one flight with train",
            desc: "Delhi-Mumbai by Rajdhani saves ~200kg CO₂ vs flying.",
            impact: 230,
            difficulty: "easy",
          });
        if (home_energy > 600)
          tips.push({
            icon: "☀️",
            title: "Install rooftop solar",
            desc: "A 2kW system covers 60-80% of household electricity.",
            impact: Math.round(home_energy * 0.6),
            difficulty: "hard",
          });
        if (home_energy > 300)
          tips.push({
            icon: "⭐",
            title: "Upgrade to 5-star BEE appliances",
            desc: "Cuts home energy use by 30-40%. Saves money too.",
            impact: Math.round(home_energy * 0.3),
            difficulty: "medium",
          });
        if (diet > 1800)
          tips.push({
            icon: "🥗",
            title: "Try Meatless Mondays",
            desc: "Skipping meat one day a week saves 150-200kg CO₂e annually.",
            impact: 180,
            difficulty: "easy",
          });
        if (diet > 2200)
          tips.push({
            icon: "♻️",
            title: "Reduce food waste",
            desc: "Plan meals, store properly, compost scraps.",
            impact: Math.round(diet * 0.12),
            difficulty: "easy",
          });
        if (shopping > 400)
          tips.push({
            icon: "👕",
            title: "Buy second-hand clothing",
            desc: "10 second-hand items saves ~100kg CO₂ and textile waste.",
            impact: Math.round(shopping * 0.2),
            difficulty: "easy",
          });
        return tips.sort((a, b) => b.impact - a.impact).slice(0, 5);
      }

      /* ── MAIN CALCULATE ──────────────────────────────────────────────── */
      async function doCalculate() {
        const fd = {
          carKm: document.getElementById("car-km").value,
          fuelType: document.getElementById("fuel-type").value,
          flights: document.getElementById("flights").value,
          transitKm: document.getElementById("transit-km").value,
          electricity: document.getElementById("electricity").value,
          gas: document.getElementById("gas").value,
          people: document.getElementById("people").value,
          solar: document.getElementById("solar").value,
          dietType: document.getElementById("diet-type").value,
          meatMeals: document.getElementById("meat-meals").value,
          wasteLevel: document.getElementById("food-waste").value,
          clothes: document.getElementById("clothes").value,
          electronics: document.getElementById("electronics").value,
          onlineOrders: document.getElementById("online-orders").value,
        };
        const btn = document.getElementById("calc-btn");
        btn.textContent = "Calculating... 🔄";
        btn.disabled = true;
        await new Promise((r) => setTimeout(r, 600));
        let result;
        if (DEMO_MODE) {
          result = calcLocal(fd);
        } else {
          try {
            const res = await fetch(
              `${API_BASE}/api/carbon/calculate/anonymous`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  transport: {
                    car_km_per_week: parseFloat(fd.carKm),
                    car_fuel_type: fd.fuelType,
                    flights_per_year: parseInt(fd.flights),
                    public_transport_km_per_week: parseFloat(fd.transitKm),
                  },
                  home_energy: {
                    electricity_kwh_per_month: parseFloat(fd.electricity),
                    gas_units_per_month: parseFloat(fd.gas),
                    num_people_in_home: parseInt(fd.people),
                    renewable_energy_percent: parseFloat(fd.solar),
                  },
                  diet: {
                    diet_type: fd.dietType,
                    meat_meals_per_week: parseFloat(fd.meatMeals),
                    food_waste_level: fd.wasteLevel,
                  },
                  shopping: {
                    new_clothes_per_year: parseInt(fd.clothes),
                    electronics_per_year: parseInt(fd.electronics),
                    online_shopping_orders_per_month: parseFloat(
                      fd.onlineOrders,
                    ),
                  },
                  country: "IN",
                }),
              },
            );
            if (!res.ok) throw new Error("API " + res.status);
            result = await res.json();
          } catch (e) {
            console.warn("API failed, local fallback:", e);
            result = calcLocal(fd);
          }
        }
        const forecast = forecastLocal(result.footprint.total);
        const tips = genTips(result.footprint);
        appState.result = result;
        appState.forecast = forecast;
        appState.tips = tips;
        btn.textContent = "Calculate My Footprint 🌍";
        btn.disabled = false;
        // Award badges based on form data and result
        checkBadgesFromForm(fd);
        checkBadgesFromResult(result);
        gameState.co2Saved = Math.max(
          0,
          Math.round(4000 - result.footprint.total),
        );
        saveGameState();
        renderDashboard(result, forecast);
        renderTips(tips, forecast.reduction_potential_kg);
        navTo("dashboard");
      }

      /* ── DASHBOARD RENDER ────────────────────────────────────────────── */
      function renderDashboard(result, forecast) {
        document.getElementById("no-data-msg").classList.add("hidden");
        document.getElementById("dashboard-content").classList.remove("hidden");
        const { footprint, rating, percentile, global_avg_kg, india_avg_kg } =
          result;
        animateNumber("total-kg", 0, footprint.total, 800);
        const badge = document.getElementById("result-badge");
        badge.textContent = rating.charAt(0).toUpperCase() + rating.slice(1);
        badge.className = `result-badge badge-${rating}`;
        document.getElementById("percentile-text").textContent =
          `Your footprint is lower than ${Math.round(100 - percentile)}% of the global population`;
        document.getElementById("stat-transport").textContent =
          footprint.transport.toLocaleString();
        document.getElementById("stat-home").textContent =
          footprint.home_energy.toLocaleString();
        document.getElementById("stat-diet").textContent =
          footprint.diet.toLocaleString();
        document.getElementById("stat-shopping").textContent =
          footprint.shopping.toLocaleString();
        renderDonutChart(footprint);
        renderForecastChart(forecast);
        renderCompareBars(footprint.total, global_avg_kg, india_avg_kg);
        renderBreakdownBars(footprint);
      }

      function renderDonutChart(fp) {
        if (appState.donutChart) appState.donutChart.destroy();
        const ctx = document.getElementById("donut-chart").getContext("2d");
        appState.donutChart = new Chart(ctx, {
          type: "doughnut",
          data: {
            labels: ["Transport", "Home Energy", "Diet", "Shopping"],
            datasets: [
              {
                data: [fp.transport, fp.home_energy, fp.diet, fp.shopping],
                backgroundColor: ["#22c55e", "#16a34a", "#86efac", "#4ade80"],
                borderColor: "#0a0f0d",
                borderWidth: 3,
                hoverOffset: 6,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { labels: { color: "#e8f5e9", padding: 16 } },
              tooltip: {
                callbacks: {
                  label: (c) =>
                    ` ${c.label}: ${c.parsed.toLocaleString()} kg CO₂e`,
                },
              },
            },
            cutout: "65%",
          },
        });
      }

      function renderForecastChart(forecast) {
        if (appState.forecastChart) appState.forecastChart.destroy();
        const ctx = document.getElementById("forecast-chart").getContext("2d");
        const trends = {
          improving: ["📉 Improving", "#22c55e"],
          stable: ["➡️ Stable", "#f59e0b"],
          worsening: ["📈 Worsening", "#ef4444"],
        };
        const [tt, tc] = trends[forecast.trend] || trends.stable;
        document.getElementById("trend-tag").innerHTML =
          `<span style="padding:0.25rem 0.75rem;border-radius:999px;font-size:0.8rem;font-weight:600;background:${tc}22;color:${tc};border:1px solid ${tc}44">${tt}</span>`;
        appState.forecastChart = new Chart(ctx, {
          type: "line",
          data: {
            labels: forecast.months,
            datasets: [
              {
                label: "Predicted kg CO₂e/month",
                data: forecast.predicted_kg.map((v) => Math.round(v / 12)),
                borderColor: "#22c55e",
                backgroundColor: "rgba(34,197,94,0.08)",
                borderWidth: 2.5,
                pointRadius: 5,
                pointBackgroundColor: "#22c55e",
                fill: true,
                tension: 0.4,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: { ticks: { color: "#6b8f72" }, grid: { color: "#1e3024" } },
              y: {
                ticks: { color: "#6b8f72", callback: (v) => `${v} kg` },
                grid: { color: "#1e3024" },
              },
            },
            plugins: {
              legend: { labels: { color: "#e8f5e9" } },
              tooltip: {
                callbacks: { label: (c) => ` ${c.parsed.y} kg CO₂e/month` },
              },
            },
          },
        });
      }

      function renderCompareBars(u, g, ia) {
        const max = Math.max(u, g, 10000);
        const items = [
          { label: "You", value: u, color: u > g ? "#ef4444" : "#22c55e" },
          { label: "Global avg", value: g, color: "#f59e0b" },
          { label: "India avg", value: ia, color: "#60a5fa" },
          { label: "1.5°C target", value: 2300, color: "#a78bfa" },
        ];
        document.getElementById("compare-bars").innerHTML = items
          .map(
            (i) =>
              `<div class="compare-bar"><div class="compare-bar-label">${i.label}</div><div class="compare-bar-track"><div class="compare-bar-fill" style="width:${((i.value / max) * 100).toFixed(1)}%;background:${i.color}"></div></div><div class="compare-bar-value" style="color:${i.color}">${i.value.toLocaleString()}</div></div>`,
          )
          .join("");
      }

      function renderBreakdownBars(fp) {
        const total = fp.total;
        const cats = [
          { label: "🚗 Transport", value: fp.transport, color: "#22c55e" },
          { label: "🏠 Home Energy", value: fp.home_energy, color: "#16a34a" },
          { label: "🥗 Diet", value: fp.diet, color: "#86efac" },
          { label: "🛍️ Shopping", value: fp.shopping, color: "#4ade80" },
        ];
        document.getElementById("breakdown-bars").innerHTML = cats
          .map(
            (c) =>
              `<div class="progress-row"><div class="progress-header"><span>${c.label}</span><span style="font-weight:600">${c.value.toLocaleString()} kg <span class="text-dim">(${((c.value / total) * 100).toFixed(0)}%)</span></span></div><div class="progress-track"><div class="progress-fill" style="width:${((c.value / total) * 100).toFixed(1)}%;background:${c.color}"></div></div></div>`,
          )
          .join("");
      }

      function renderTips(tips, rp) {
        document.getElementById("no-tips-msg").classList.add("hidden");
        document.getElementById("tips-content").classList.remove("hidden");
        const dc = { easy: "#22c55e", medium: "#f59e0b", hard: "#ef4444" };
        document.getElementById("tips-list").innerHTML = tips
          .map(
            (t, i) =>
              `<div class="tip-card fade-in" style="animation-delay:${i * 0.08}s" role="article"><div class="tip-icon">${t.icon}</div><div><div class="tip-title">${t.title}<span class="tip-diff" style="color:${dc[t.difficulty]}">${t.difficulty}</span></div><div class="tip-desc">${t.desc}</div><div class="tip-impact">💚 Save ~${t.impact.toLocaleString()} kg CO₂e/year</div></div></div>`,
          )
          .join("");
        document.getElementById("reduction-potential").textContent =
          `~${rp.toLocaleString()} kg CO₂e`;
      }

      /* ── AUTH ────────────────────────────────────────────────────────── */
      async function doLogin() {
        const email = document.getElementById("login-email").value.trim();
        const pass = document.getElementById("login-password").value;
        const errEl = document.getElementById("login-error");
        errEl.classList.add("hidden");
        if (!email || !pass) {
          errEl.textContent = "Please enter your email and password.";
          errEl.classList.remove("hidden");
          return;
        }
        if (DEMO_MODE) {
          appState.token = "demo-token";
          appState.userName = email.split("@")[0];
          updateAuthUI();
          navTo("home");
          return;
        }
        try {
          const res = await fetch(`${API_BASE}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password: pass }),
          });
          if (res.ok) {
            const d = await res.json();
            appState.token = d.access_token;
            appState.userName = d.name || email.split("@")[0];
            localStorage.setItem("eco_token", d.access_token);
            localStorage.setItem("eco_user", appState.userName);
            updateAuthUI();
            navTo("home");
          } else {
            const e = await res.json();
            errEl.textContent = e.detail || "Login failed.";
            errEl.classList.remove("hidden");
          }
        } catch (e) {
          errEl.textContent = "Could not connect to server.";
          errEl.classList.remove("hidden");
        }
      }

      async function doRegister() {
        const name = document.getElementById("reg-name").value.trim();
        const email = document.getElementById("reg-email").value.trim();
        const pass = document.getElementById("reg-password").value;
        const errEl = document.getElementById("register-error");
        errEl.classList.add("hidden");
        if (!name || !email || !pass) {
          errEl.textContent = "All fields are required.";
          errEl.classList.remove("hidden");
          return;
        }
        if (pass.length < 8) {
          errEl.textContent = "Password must be at least 8 characters.";
          errEl.classList.remove("hidden");
          return;
        }
        if (DEMO_MODE) {
          appState.token = "demo-token";
          appState.userName = name;
          updateAuthUI();
          navTo("home");
          return;
        }
        try {
          const res = await fetch(`${API_BASE}/api/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, password: pass }),
          });
          if (res.ok) {
            const d = await res.json();
            appState.token = d.access_token;
            appState.userName = name;
            localStorage.setItem("eco_token", d.access_token);
            localStorage.setItem("eco_user", name);
            updateAuthUI();
            navTo("home");
          } else {
            const e = await res.json();
            errEl.textContent = e.detail || "Registration failed.";
            errEl.classList.remove("hidden");
          }
        } catch (e) {
          errEl.textContent = "Server unavailable.";
          errEl.classList.remove("hidden");
        }
      }
      function updateAuthUI() {
        const el = document.getElementById("auth-status");
        if (appState.token) {
          el.innerHTML = `<span class="text-dim" style="font-size:0.875rem;margin-right:0.75rem">👋 ${appState.userName || "User"}</span><button class="btn-secondary" onclick="logout()" style="padding:0.4rem 1rem;font-size:0.875rem">Sign out</button>`;
        } else {
          el.innerHTML = `<button class="btn-secondary" onclick="navTo('register')" style="padding:0.4rem 1rem;font-size:0.875rem;margin-right:0.5rem">Sign up</button><button class="btn-primary" onclick="navTo('login')" style="padding:0.4rem 1rem;font-size:0.875rem">Sign in</button>`;
        }
      }
      function logout() {
        appState.token = null;
        appState.userName = null;
        localStorage.removeItem("eco_token");
        localStorage.removeItem("eco_user");
        updateAuthUI();
        navTo("home");
      }

      /* ── UTILITIES ───────────────────────────────────────────────────── */
      function animateNumber(id, from, to, dur) {
        const el = document.getElementById(id);
        if (!el) return;
        const start = performance.now();
        function u(now) {
          const p = Math.min((now - start) / dur, 1);
          el.textContent = Math.round(
            from + (to - from) * (1 - Math.pow(1 - p, 3)),
          ).toLocaleString();
          if (p < 1) requestAnimationFrame(u);
        }
        requestAnimationFrame(u);
      }
      function getDom(fp) {
        const c = {
          transport: fp.transport,
          "home energy": fp.home_energy,
          diet: fp.diet,
          shopping: fp.shopping,
        };
        return Object.entries(c).sort((a, b) => b[1] - a[1])[0][0];
      }
      function getMax(fp) {
        return Math.max(fp.transport, fp.home_energy, fp.diet, fp.shopping);
      }

      /* ── AI INSIGHTS ─────────────────────────────────────────────────── */
      async function loadAIInsights() {
        if (!appState.result) return;
        document.getElementById("no-insights-msg").classList.add("hidden");
        document.getElementById("insights-content").classList.remove("hidden");
        document.getElementById("insights-loading").classList.remove("hidden");
        document.getElementById("insights-result").classList.add("hidden");
        const fp = appState.result.footprint;
        try {
          if (DEMO_MODE) {
            await new Promise((r) => setTimeout(r, 1200));
            renderInsights({
              summary: `Your annual footprint of ${fp.total.toLocaleString()} kg CO₂e places you ${fp.total > 4000 ? "above" : "below"} the global average of 4,000 kg. Your biggest driver is ${getDom(fp)} at ${Math.round((getMax(fp) / fp.total) * 100)}% of your total emissions.`,
              dominant_category: getDom(fp),
              key_insight: `Reducing your ${getDom(fp)} emissions by 30% would save ${Math.round(getMax(fp) * 0.3).toLocaleString()} kg CO₂e — equivalent to planting ${Math.round((getMax(fp) * 0.3) / 21)} trees annually.`,
              action_plan: [
                `1. Target ${getDom(fp)} first — highest impact area.`,
                "2. Set a monthly tracking reminder — users who measure reduce 23% more.",
                "3. Share your target with one person — social commitment increases follow-through 65%.",
              ],
              motivational_close:
                "Every kilogram matters. Measuring means you're already ahead of 90% of people.",
            });
          } else {
            const res = await fetch(`${API_BASE}/api/insights/analyze`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                footprint: fp,
                country: "IN",
                user_name: appState.userName || null,
              }),
            });
            if (!res.ok) throw new Error("API error");
            renderInsights(await res.json());
          }
          const history = Array.from({ length: 6 }, (_, i) => ({
            transport: fp.transport * (1 + (5 - i) * 0.015),
            home_energy: fp.home_energy * (1 + (5 - i) * 0.01),
            diet: fp.diet * (1 + (5 - i) * 0.012),
            shopping: fp.shopping * (1 + (5 - i) * 0.02),
            total: fp.total * (1 + (5 - i) * 0.013),
          }));
          if (!DEMO_MODE) {
            const ar = await fetch(`${API_BASE}/api/insights/anomaly`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ current: fp, history }),
            });
            if (ar.ok) renderAnomaly(await ar.json());
          }
        } catch (e) {
          console.warn("Insights error:", e);
          document.getElementById("insights-loading").classList.add("hidden");
        }
      }

      function renderInsights(d) {
        document.getElementById("insights-loading").classList.add("hidden");
        document.getElementById("insights-result").classList.remove("hidden");
        document.getElementById("ai-summary").textContent = d.summary;
        document.getElementById("ai-key-insight").textContent = d.key_insight;
        document.getElementById("ai-action-plan").innerHTML = d.action_plan
          .map(
            (s, i) =>
              `<div style="display:flex;gap:1rem;padding:0.875rem;background:var(--surface2);border-radius:var(--radius);margin-bottom:0.75rem;align-items:flex-start"><div style="width:1.75rem;height:1.75rem;background:var(--green);color:#000;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.8rem;flex-shrink:0">${i + 1}</div><p style="line-height:1.6;font-size:0.9rem;margin:0">${s.replace(/^\d+\.\s*/, "")}</p></div>`,
          )
          .join("");
        document.getElementById("ai-motivational").textContent =
          `"${d.motivational_close}"`;
      }

      function renderAnomaly(d) {
        if (!d.is_anomaly && d.flagged_categories.length === 0) return;
        document.getElementById("anomaly-card").classList.remove("hidden");
        document.getElementById("anomaly-explanation").textContent =
          d.explanation;
        const cl = {
          transport: "🚗 Transport",
          home_energy: "🏠 Home",
          diet: "🥗 Diet",
          shopping: "🛍️ Shopping",
        };
        document.getElementById("anomaly-zscores").innerHTML = Object.entries(
          d.z_scores,
        )
          .map(([cat, z]) => {
            const f = d.flagged_categories.includes(cat);
            const c = z > 2 ? "#ef4444" : z > 1 ? "#f59e0b" : "#22c55e";
            return `<div style="background:var(--surface2);border:1px solid ${f ? c : "var(--border)"};border-radius:var(--radius);padding:0.75rem;text-align:center"><div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:0.25rem">${cl[cat]}</div><div style="font-family:var(--font-disp);font-size:1.1rem;color:${c};font-weight:700">${z > 0 ? "+" : ""}${z}σ</div></div>`;
          })
          .join("");
      }

      /* ── ECOBOT ──────────────────────────────────────────────────────── */
      const chatHistory = [];

      async function sendChatMessage() {
        const input = document.getElementById("chat-input");
        const msg = input.value.trim();
        if (!msg) return;
        input.value = "";
        appendMsg("user", msg);
        chatHistory.push({ role: "user", content: msg });
        const btn = document.getElementById("chat-send-btn");
        btn.disabled = true;
        btn.textContent = "...";
        const tid = appendTyping();
        try {
          let reply;
          if (DEMO_MODE) {
            await new Promise((r) => setTimeout(r, 800));
            reply = localReply(msg, appState.result?.footprint);
          } else {
            const res = await fetch(`${API_BASE}/api/insights/chat`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                messages: chatHistory.slice(-10),
                footprint_context: appState.result?.footprint || null,
              }),
            });
            if (!res.ok) throw new Error("API");
            reply = (await res.json()).reply;
          }
          removeTyping(tid);
          appendMsg("assistant", reply);
          chatHistory.push({ role: "assistant", content: reply });
          awardBadge("ecobot_chat");
        } catch (e) {
          removeTyping(tid);
          appendMsg(
            "assistant",
            "Sorry, I couldn't reach the server. Check your connection and try again.",
          );
        }
        btn.disabled = false;
        btn.textContent = "Send →";
      }

      function sendSuggestion(btn) {
        document.getElementById("chat-input").value = btn.textContent;
        document.getElementById("chat-suggestions").classList.add("hidden");
        sendChatMessage();
      }

      function appendMsg(role, text) {
        const c = document.getElementById("chat-messages");
        const isBot = role === "assistant";
        const w = document.createElement("div");
        w.style.cssText = `display:flex;gap:0.75rem;align-items:flex-start;${isBot ? "" : "flex-direction:row-reverse"}`;
        const av = document.createElement("div");
        av.style.cssText =
          "width:2rem;height:2rem;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:0.9rem;";
        av.style.background = isBot
          ? "rgba(34,197,94,0.15)"
          : "rgba(255,255,255,0.08)";
        av.textContent = isBot ? "🤖" : "👤";
        const b = document.createElement("div");
        b.style.cssText = `background:${isBot ? "var(--surface2)" : "rgba(34,197,94,0.12)"};border:1px solid ${isBot ? "var(--border)" : "rgba(34,197,94,0.25)"};border-radius:12px;padding:0.75rem 1rem;max-width:85%;line-height:1.6;font-size:0.9rem;white-space:pre-wrap`;
        b.textContent = text;
        w.appendChild(av);
        w.appendChild(b);
        c.appendChild(w);
        c.scrollTop = c.scrollHeight;
      }

      function appendTyping() {
        const c = document.getElementById("chat-messages");
        const id = "t" + Date.now();
        const d = document.createElement("div");
        d.id = id;
        d.style.cssText =
          "display:flex;gap:0.75rem;align-items:center;opacity:0.6";
        d.innerHTML =
          '<div style="width:2rem;height:2rem;background:rgba(34,197,94,0.15);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:0.9rem">🤖</div><div style="background:var(--surface2);border:1px solid var(--border);border-radius:12px;padding:0.75rem 1rem;font-size:0.9rem" class="pulse">EcoBot is thinking...</div>';
        c.appendChild(d);
        c.scrollTop = c.scrollHeight;
        return id;
      }
      function removeTyping(id) {
        const e = document.getElementById(id);
        if (e) e.remove();
      }

      function localReply(msg, fp) {
        const m = msg.toLowerCase();
        if (
          fp &&
          (m.includes("biggest") || m.includes("most") || m.includes("drive"))
        ) {
          const dom = getDom(fp);
          return `Your biggest driver is ${dom} at ${Math.round(getMax(fp))} kg CO₂e/year — ${Math.round((getMax(fp) / fp.total) * 100)}% of your total.`;
        }
        if (m.includes("transport") || m.includes("car"))
          return "Transport wins you the fastest. EV, WFH 2 days, or one fewer flight can cut 25-70%.";
        if (m.includes("solar"))
          return "A 2kW rooftop system in India costs ₹1-1.5L and covers 60-80% of electricity. 5-7 year payback.";
        if (m.includes("vegan") || m.includes("diet") || m.includes("meat"))
          return "Going vegan saves ~1,000 kg CO₂e/year vs omnivore. Lentils produce 20× less CO₂ per gram of protein than beef.";
        if (m.includes("offset"))
          return "Look for Gold Standard certified projects — reforestation in India costs $5-8/tonne. Offsets supplement, not replace, real reductions.";
        return "Ask me about any specific category — transport, home energy, diet, or shopping — and I'll give you concrete India-relevant advice.";
      }

      /* ── AR SCANNER ──────────────────────────────────────────────────── */
      const PCARBON = {
        food_meat: {
          name: "Meat Product",
          icon: "🥩",
          kg: 6.5,
          tip: "Consider plant-based alternatives",
        },
        food_dairy: {
          name: "Dairy Product",
          icon: "🥛",
          kg: 3.2,
          tip: "Oat milk has 80% less carbon than cow milk",
        },
        food_veg: {
          name: "Vegetable/Fruit",
          icon: "🥦",
          kg: 0.4,
          tip: "Great low carbon food choice",
        },
        food_snack: {
          name: "Packaged Snack",
          icon: "🍪",
          kg: 1.8,
          tip: "Packaging adds significant carbon",
        },
        food_beverage: {
          name: "Beverage",
          icon: "🥤",
          kg: 0.9,
          tip: "Tap water has near-zero carbon",
        },
        electronics_phone: {
          name: "Smartphone",
          icon: "📱",
          kg: 70,
          tip: "Keeping your phone 1 extra year saves 70kg CO2",
        },
        electronics_laptop: {
          name: "Laptop",
          icon: "💻",
          kg: 300,
          tip: "Refurbished laptops save 150kg CO2",
        },
        clothing_tshirt: {
          name: "T-Shirt",
          icon: "👕",
          kg: 7,
          tip: "One cotton t-shirt uses 2,700L of water",
        },
        clothing_jeans: {
          name: "Jeans",
          icon: "👖",
          kg: 33,
          tip: "Second-hand jeans save 33kg CO2",
        },
        household_plastic: {
          name: "Plastic Product",
          icon: "🧴",
          kg: 2.1,
          tip: "Choose glass or metal alternatives",
        },
        unknown: {
          name: "Consumer Product",
          icon: "📦",
          kg: 2.5,
          tip: "Ask the manufacturer about their carbon footprint",
        },
      };
      const BMAP = {
        890: "food_snack",
        893: "food_beverage",
        "00": "food_snack",
        "02": "food_meat",
        "03": "food_dairy",
        "04": "food_veg",
        "05": "food_beverage",
        30: "food_meat",
        31: "food_veg",
        32: "food_dairy",
        40: "household_plastic",
        45: "electronics_phone",
        49: "electronics_laptop",
        50: "clothing_tshirt",
        54: "clothing_jeans",
        69: "electronics_phone",
        70: "food_snack",
        75: "food_beverage",
        80: "food_snack",
        84: "clothing_jeans",
      };

      let scannerStream = null,
        scannerInterval = null,
        scannedHistory = [],
        lastScanned = null;
      function getCat(b) {
        return BMAP[b.substring(0, 3)] || BMAP[b.substring(0, 2)] || "unknown";
      }

      async function startScanner() {
        try {
          const v = document.getElementById("scanner-video");
          scannerStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment" },
          });
          v.srcObject = scannerStream;
          await v.play();
          document.getElementById("start-scan-btn").textContent =
            "📷 Scanning...";
          document.getElementById("start-scan-btn").disabled = true;
          if ("BarcodeDetector" in window) {
            const det = new BarcodeDetector({
              formats: ["ean_13", "ean_8", "upc_a", "code_128"],
            });
            scannerInterval = setInterval(async () => {
              const cv = document.getElementById("scanner-canvas");
              const cx = cv.getContext("2d");
              cv.width = v.videoWidth;
              cv.height = v.videoHeight;
              cx.drawImage(v, 0, 0);
              const bc = await det.detect(cv).catch(() => []);
              if (bc.length > 0) {
                stopScanner();
                lookupBarcode(bc[0].rawValue);
              }
            }, 500);
          } else {
            setTimeout(() => {
              stopScanner();
              alert("BarcodeDetector not supported. Use manual entry below.");
            }, 3000);
          }
        } catch (e) {
          alert("Camera access denied. Please use manual barcode entry below.");
        }
      }

      function stopScanner() {
        if (scannerStream) {
          scannerStream.getTracks().forEach((t) => t.stop());
          scannerStream = null;
        }
        if (scannerInterval) {
          clearInterval(scannerInterval);
          scannerInterval = null;
        }
        document.getElementById("start-scan-btn").textContent =
          "📷 Start Camera";
        document.getElementById("start-scan-btn").disabled = false;
      }

      function lookupBarcode(b) {
        if (!b || b.length < 6) {
          alert("Please enter a valid barcode (at least 6 digits)");
          return;
        }
        const p = PCARBON[getCat(b)];
        lastScanned = { ...p, barcode: b };
        document
          .getElementById("scan-result-overlay")
          .classList.remove("hidden");
        document.getElementById("scan-product-icon").textContent = p.icon;
        document.getElementById("scan-product-name").textContent = p.name;
        document.getElementById("scan-carbon-value").textContent = p.kg;
        document.getElementById("scan-carbon-context").textContent =
          `Equivalent to driving ${Math.round(p.kg / 0.192)} km in a petrol car · ${p.tip}`;
        scannedHistory.unshift({ ...p, barcode: b });
        if (scannedHistory.length > 5) scannedHistory.pop();
        renderScanHistory();
        awardBadge("scanner_used");
      }

      function renderScanHistory() {
        const el = document.getElementById("scan-history");
        if (!scannedHistory.length) {
          el.innerHTML =
            '<p class="text-dim" style="font-size:0.875rem;text-align:center">No products scanned yet</p>';
          return;
        }
        el.innerHTML = scannedHistory
          .map(
            (i) =>
              `<div class="scanner-history-item"><span style="font-size:1.5rem">${i.icon}</span><div style="flex:1"><div style="font-weight:600;font-size:0.9rem">${i.name}</div><div style="font-size:0.75rem;color:var(--text-dim)">${i.barcode}</div></div><div style="font-family:var(--font-disp);font-weight:700;color:var(--green)">${i.kg} kg</div></div>`,
          )
          .join("");
      }
      function restartScanner() {
        document.getElementById("scan-result-overlay").classList.add("hidden");
        startScanner();
      }
      function addScannedToFootprint() {
        if (!lastScanned) return;
        alert(
          `Added ${lastScanned.name} (${lastScanned.kg} kg CO₂e) to your footprint tracking!`,
        );
        document.getElementById("scan-result-overlay").classList.add("hidden");
      }

      /* ── OFFSET MARKETPLACE ──────────────────────────────────────────── */
      const OPROJ = [
        {
          name: "Sundarbans Mangrove Restoration",
          loc: "West Bengal",
          icon: "🌿",
          price: 8,
          rating: "Gold Standard",
          desc: "Restores mangrove forests that absorb 4× more carbon than tropical rainforests.",
        },
        {
          name: "Rajasthan Solar Energy",
          loc: "Rajasthan",
          icon: "☀️",
          price: 6,
          rating: "Verified Carbon Standard",
          desc: "Funds solar installations for rural villages, replacing diesel generators.",
        },
        {
          name: "Himalayan Clean Cookstoves",
          loc: "Uttarakhand",
          icon: "🔥",
          price: 5,
          rating: "Gold Standard",
          desc: "Provides efficient cookstoves reducing wood consumption and indoor air pollution.",
        },
        {
          name: "Western Ghats Reforestation",
          loc: "Karnataka",
          icon: "🌳",
          price: 7,
          rating: "Plan Vivo",
          desc: "Plants native species in degraded forest areas of the biodiversity hotspot.",
        },
      ];
      const OACT = [
        {
          icon: "🌱",
          action: "Plant trees in your neighbourhood",
          saving: "21 kg CO₂/tree/year",
          diff: "easy",
        },
        {
          icon: "🚲",
          action: "Replace 2 car trips/week with cycling",
          saving: "~200 kg CO₂/year",
          diff: "easy",
        },
        {
          icon: "☀️",
          action: "Switch to green electricity tariff",
          saving: "Up to 1,200 kg CO₂/year",
          diff: "medium",
        },
        {
          icon: "🥗",
          action: "Go meat-free one day per week",
          saving: "~180 kg CO₂/year",
          diff: "easy",
        },
        {
          icon: "♻️",
          action: "Compost food waste at home",
          saving: "~100 kg CO₂/year",
          diff: "easy",
        },
      ];

      function loadOffsetContent() {
        awardBadge("offset_viewed");
        if (!appState.result) {
          document.getElementById("no-offset-msg").classList.remove("hidden");
          document.getElementById("offset-content").classList.add("hidden");
          return;
        }
        document.getElementById("no-offset-msg").classList.add("hidden");
        document.getElementById("offset-content").classList.remove("hidden");
        const t = appState.result.footprint.total;
        document.getElementById("offset-trees").textContent = Math.ceil(
          t / 21,
        ).toLocaleString();
        document.getElementById("offset-cost").textContent =
          `$${Math.ceil((t / 1000) * 6)} USD`;
        document.getElementById("offset-projects").innerHTML = OPROJ.map(
          (p) =>
            `<div class="card" style="border-color:rgba(34,197,94,0.2)"><div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.75rem"><span style="font-size:2rem">${p.icon}</span><div><div style="font-family:var(--font-disp);font-weight:600">${p.name}</div><div style="font-size:0.75rem;color:var(--text-dim)">${p.loc}</div></div></div><p style="font-size:0.85rem;color:var(--text-dim);margin-bottom:0.75rem">${p.desc}</p><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:0.75rem;background:rgba(34,197,94,0.1);color:var(--green);padding:0.2rem 0.5rem;border-radius:999px">${p.rating}</span><span style="font-family:var(--font-disp);font-weight:700;color:var(--green)">$${p.price}/tonne</span></div></div>`,
        ).join("");
        document.getElementById("free-offset-actions").innerHTML = OACT.map(
          (a) =>
            `<div style="display:flex;align-items:center;gap:1rem;padding:0.75rem;background:var(--surface2);border-radius:var(--radius)"><span style="font-size:1.5rem">${a.icon}</span><div style="flex:1"><div style="font-size:0.9rem;font-weight:500">${a.action}</div><div style="font-size:0.75rem;color:var(--green)">${a.saving}</div></div><span style="font-size:0.7rem;padding:0.15rem 0.5rem;border-radius:999px;background:var(--surface);color:var(--text-dim)">${a.diff}</span></div>`,
        ).join("");
      }

      /* ── COMMUNITY LEADERBOARD ───────────────────────────────────────── */
      const CDATA = [
        { rank: 1, name: "Priya S.", city: "Bengaluru", kg: 1102, badge: "🌟" },
        { rank: 2, name: "Arjun M.", city: "Mumbai", kg: 1245, badge: "🌟" },
        { rank: 3, name: "Meera K.", city: "Chennai", kg: 1380, badge: "🏆" },
        { rank: 4, name: "Rohan P.", city: "Delhi", kg: 1520, badge: "🏆" },
        { rank: 5, name: "Aisha T.", city: "Pune", kg: 1680, badge: "🥇" },
        {
          rank: 6,
          name: "Vikram S.",
          city: "Hyderabad",
          kg: 1750,
          badge: "🥇",
        },
        { rank: 7, name: "Neha R.", city: "Kolkata", kg: 1820, badge: "🥈" },
        { rank: 8, name: "Karan A.", city: "Jaipur", kg: 1950, badge: "🥈" },
        { rank: 9, name: "Divya L.", city: "Ahmedabad", kg: 2100, badge: "🥉" },
        { rank: 10, name: "Aditya V.", city: "Surat", kg: 2280, badge: "🥉" },
      ];

      let distChartInstance = null;
      function loadCommunityContent() {
        document.getElementById("leaderboard-list").innerHTML = CDATA.map(
          (u) =>
            `<div style="display:flex;align-items:center;gap:1rem;padding:0.75rem;border-bottom:1px solid var(--border)"><div style="width:2rem;text-align:center;font-family:var(--font-disp);font-weight:700;color:${u.rank <= 3 ? "var(--green)" : "var(--text-dim)"}">${u.rank}</div><div style="font-size:1.25rem">${u.badge}</div><div style="flex:1"><div style="font-weight:500;font-size:0.9rem">${u.name}</div><div style="font-size:0.75rem;color:var(--text-dim)">${u.city}</div></div><div style="font-family:var(--font-disp);font-weight:700;color:var(--green)">${u.kg.toLocaleString()} kg</div></div>`,
        ).join("");
        if (appState.result) {
          const uk = appState.result.footprint.total;
          const bt = CDATA.filter((u) => u.kg > uk).length;
          document
            .getElementById("community-rank-card")
            .classList.remove("hidden");
          document.getElementById("community-rank-number").textContent =
            `#${CDATA.length - bt + 1}`;
          document.getElementById("community-rank-text").textContent =
            `Your ${uk.toLocaleString()} kg footprint is better than ${Math.round((bt / CDATA.length) * 100)}% of our community`;
        }
        if (!distChartInstance) {
          const ctx = document
            .getElementById("distribution-chart")
            .getContext("2d");
          distChartInstance = new Chart(ctx, {
            type: "bar",
            data: {
              labels: [
                "<1000",
                "1000-2000",
                "2000-3000",
                "3000-4000",
                "4000-5000",
                ">5000",
              ],
              datasets: [
                {
                  label: "People (%)",
                  data: [8, 22, 28, 20, 14, 8],
                  backgroundColor: [
                    "rgba(34,197,94,0.8)",
                    "rgba(34,197,94,0.6)",
                    "rgba(245,158,11,0.6)",
                    "rgba(245,158,11,0.8)",
                    "rgba(239,68,68,0.6)",
                    "rgba(239,68,68,0.8)",
                  ],
                  borderRadius: 4,
                },
              ],
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: { legend: { display: false } },
              scales: {
                x: { ticks: { color: "#6b8f72" }, grid: { color: "#1e3024" } },
                y: {
                  ticks: { color: "#6b8f72", callback: (v) => `${v}%` },
                  grid: { color: "#1e3024" },
                },
              },
            },
          });
        }
      }

      /* ── GAMIFICATION ────────────────────────────────────────────────── */
      const BADGES = [
        {
          id: "first_calc",
          icon: "🌱",
          name: "First Step",
          xp: 50,
          desc: "Calculated your carbon footprint for the first time",
          req: "Complete the calculator",
        },
        {
          id: "below_global",
          icon: "🌍",
          name: "Global Citizen",
          xp: 100,
          desc: "Your footprint is below the global average of 4,000 kg",
          req: "Get below 4,000 kg CO₂e",
        },
        {
          id: "below_india",
          icon: "🇮🇳",
          name: "India Champion",
          xp: 150,
          desc: "Your footprint is below the India average of 1,800 kg",
          req: "Get below 1,800 kg CO₂e",
        },
        {
          id: "below_target",
          icon: "🎯",
          name: "Climate Hero",
          xp: 300,
          desc: "Your footprint is below the IPCC 1.5°C target of 2,300 kg",
          req: "Get below 2,300 kg CO₂e",
        },
        {
          id: "ev_user",
          icon: "⚡",
          name: "EV Pioneer",
          xp: 200,
          desc: "Using an electric vehicle — cutting transport emissions by 70%",
          req: "Select electric car",
        },
        {
          id: "solar_user",
          icon: "☀️",
          name: "Solar Warrior",
          xp: 200,
          desc: "Using renewable energy — reducing grid dependency",
          req: "Set renewable % > 0",
        },
        {
          id: "vegan",
          icon: "🥗",
          name: "Plant Power",
          xp: 150,
          desc: "Following a vegan diet — the lowest carbon diet choice",
          req: "Select vegan diet",
        },
        {
          id: "low_waste",
          icon: "♻️",
          name: "Zero Waster",
          xp: 100,
          desc: "Low food waste level — maximising every meal",
          req: "Set food waste to low",
        },
        {
          id: "scanner_used",
          icon: "📷",
          name: "Carbon Detective",
          xp: 75,
          desc: "Used the AR scanner to check a product's carbon footprint",
          req: "Scan a product barcode",
        },
        {
          id: "ecobot_chat",
          icon: "🤖",
          name: "AI Student",
          xp: 50,
          desc: "Had a conversation with EcoBot about your footprint",
          req: "Send a message to EcoBot",
        },
        {
          id: "offset_viewed",
          icon: "🌿",
          name: "Offset Explorer",
          xp: 50,
          desc: "Explored carbon offset options to neutralise your impact",
          req: "Visit the Offset page",
        },
        {
          id: "streak_7",
          icon: "🔥",
          name: "Week Warrior",
          xp: 200,
          desc: "Visited EcoTrack 7 days in a row",
          req: "7-day streak",
        },
      ];

      const LEVELS = [
        { name: "Eco Newcomer", min: 0 },
        { name: "Green Learner", min: 100 },
        { name: "Carbon Cutter", min: 250 },
        { name: "Climate Aware", min: 500 },
        { name: "Eco Warrior", min: 800 },
        { name: "Green Champion", min: 1200 },
        { name: "Climate Hero", min: 1800 },
        { name: "Earth Guardian", min: 2500 },
      ];

      let gameState = {
        earnedBadges: [],
        totalXP: 0,
        streak: 0,
        lastVisit: null,
        co2Saved: 0,
      };

      function loadGameState() {
        try {
          const s = localStorage.getItem("ecotrack_g");
          if (s) gameState = { ...gameState, ...JSON.parse(s) };
        } catch (e) {}
        const today = new Date().toDateString();
        const last = gameState.lastVisit;
        if (!last) {
          gameState.streak = 1;
        } else if (last !== today) {
          const y = new Date(Date.now() - 86400000).toDateString();
          gameState.streak = last === y ? gameState.streak + 1 : 1;
        }
        gameState.lastVisit = today;
        if (gameState.streak >= 7) awardBadge("streak_7", true);
        saveGameState();
      }

      function saveGameState() {
        try {
          localStorage.setItem("ecotrack_g", JSON.stringify(gameState));
        } catch (e) {}
      }

      function awardBadge(id, silent = false) {
        if (gameState.earnedBadges.includes(id)) return;
        const b = BADGES.find((b) => b.id === id);
        if (!b) return;
        gameState.earnedBadges.push(id);
        gameState.totalXP += b.xp;
        saveGameState();
        if (!silent) {
          showBadgeModal(b);
          spawnConfetti();
        }
      }

      function showBadgeModal(b) {
        document.getElementById("modal-badge-icon").textContent = b.icon;
        document.getElementById("modal-badge-name").textContent = b.name;
        document.getElementById("modal-badge-desc").textContent = b.desc;
        document.getElementById("modal-badge-xp").textContent =
          `+${b.xp} XP earned!`;
        document.getElementById("badge-modal").classList.remove("hidden");
      }
      function closeBadgeModal() {
        document.getElementById("badge-modal").classList.add("hidden");
        renderBadgesPage();
      }

      function spawnConfetti() {
        const cols = ["#22c55e", "#86efac", "#f59e0b", "#a78bfa", "#60a5fa"];
        for (let i = 0; i < 30; i++) {
          const el = document.createElement("div");
          el.style.cssText = `position:fixed;top:-10px;left:${Math.random() * 100}vw;width:${6 + Math.random() * 8}px;height:${6 + Math.random() * 8}px;background:${cols[Math.floor(Math.random() * cols.length)]};border-radius:${Math.random() > 0.5 ? "50%" : "2px"};animation:confettiAnim ${1.5 + Math.random() * 2}s linear forwards;z-index:9999;pointer-events:none;`;
          document.body.appendChild(el);
          setTimeout(() => el.remove(), 4000);
        }
      }

      function getLevel(xp) {
        let c = LEVELS[0];
        for (const l of LEVELS) if (xp >= l.min) c = l;
        return c;
      }
      function getNextLevel(xp) {
        for (const l of LEVELS) if (xp < l.min) return l;
        return null;
      }

      function checkBadgesFromResult(r) {
        if (!r) return;
        awardBadge("first_calc");
        if (r.footprint.total < 4000) awardBadge("below_global");
        if (r.footprint.total < 2300) awardBadge("below_target");
        if (r.footprint.total < 1800) awardBadge("below_india");
      }

      function checkBadgesFromForm(fd) {
        if (fd.fuelType === "electric") awardBadge("ev_user");
        if (parseFloat(fd.solar) > 0) awardBadge("solar_user");
        if (fd.dietType === "vegan") awardBadge("vegan");
        if (fd.wasteLevel === "low") awardBadge("low_waste");
      }

      function renderBadgesPage() {
        const xp = gameState.totalXP;
        const lv = getLevel(xp);
        const nx = getNextLevel(xp);
        const pct = nx
          ? Math.round(((xp - lv.min) / (nx.min - lv.min)) * 100)
          : 100;
        document.getElementById("player-level").textContent = lv.name;
        document.getElementById("player-xp").textContent = `${xp} XP`;
        document.getElementById("xp-bar").style.width = `${pct}%`;
        document.getElementById("xp-next").textContent = nx
          ? `${xp} / ${nx.min} XP`
          : "Max Level!";
        document.getElementById("badge-count").textContent =
          gameState.earnedBadges.length;
        document.getElementById("streak-count").textContent = gameState.streak;
        document.getElementById("total-xp-display").textContent = xp;
        document.getElementById("co2-saved").textContent = gameState.co2Saved;
        document.getElementById("badges-grid").innerHTML = BADGES.map((b) => {
          const earned = gameState.earnedBadges.includes(b.id);
          return `<div class="badge-card ${earned ? "earned" : "locked"}" role="article" aria-label="${b.name} ${earned ? "earned" : "locked"}">
      ${earned ? '<div class="badge-earned-tick">✓</div>' : ""}
      <span class="badge-icon">${b.icon}</span>
      <div class="badge-name">${b.name}</div>
      <div class="badge-req">${b.req}</div>
      <div class="badge-xp">+${b.xp} XP${earned ? " ✓" : ""}</div>
    </div>`;
        }).join("");
        const challenges = [
          {
            icon: "🌱",
            title: "First Calculation",
            desc: "Complete the carbon calculator",
            target: 1,
            current: appState.result ? 1 : 0,
            xp: 50,
          },
          {
            icon: "🌍",
            title: "Beat Global Average",
            desc: "Get below 4,000 kg",
            target: 1,
            current:
              appState.result && appState.result.footprint.total < 4000 ? 1 : 0,
            xp: 100,
          },
          {
            icon: "🎯",
            title: "Hit 1.5°C Target",
            desc: "Get below 2,300 kg CO₂e",
            target: 1,
            current:
              appState.result && appState.result.footprint.total < 2300 ? 1 : 0,
            xp: 300,
          },
          {
            icon: "📷",
            title: "Scan a Product",
            desc: "Use the AR scanner",
            target: 1,
            current: scannedHistory.length > 0 ? 1 : 0,
            xp: 75,
          },
          {
            icon: "💬",
            title: "Chat with EcoBot",
            desc: "Ask EcoBot a question",
            target: 1,
            current: chatHistory.length > 0 ? 1 : 0,
            xp: 50,
          },
          {
            icon: "🔥",
            title: "7-Day Streak",
            desc: "Visit EcoTrack 7 days in a row",
            target: 7,
            current: Math.min(gameState.streak, 7),
            xp: 200,
          },
        ];
        document.getElementById("challenges-list").innerHTML = challenges
          .map((c) => {
            const pct = Math.min(Math.round((c.current / c.target) * 100), 100);
            const done = pct >= 100;
            return `<div class="challenge-item ${done ? "completed" : ""}">
      <span style="font-size:1.5rem">${c.icon}</span>
      <div style="flex:1">
        <div style="display:flex;justify-content:space-between;margin-bottom:0.35rem">
          <span style="font-size:0.875rem;font-weight:600">${c.title}</span>
          <span style="font-size:0.75rem;color:${done ? "var(--green)" : "var(--text-dim)"}">${done ? "✓ Complete" : c.desc}</span>
        </div>
        <div class="challenge-progress-track"><div class="challenge-progress-fill" style="width:${pct}%"></div></div>
        <div style="display:flex;justify-content:space-between;margin-top:0.25rem">
          <span style="font-size:0.72rem;color:var(--text-dim)">${c.current} / ${c.target}</span>
          <span style="font-size:0.72rem;color:var(--green)">+${c.xp} XP</span>
        </div>
      </div>
    </div>`;
          })
          .join("");
      }

      /* ── INIT ────────────────────────────────────────────────────────── */
      document.addEventListener("DOMContentLoaded", () => {
        const savedToken = localStorage.getItem("eco_token");
        const savedUser = localStorage.getItem("eco_user");
        if (savedToken) {
          appState.token = savedToken;
          appState.userName = savedUser;
        }
        navTo("home");
        updateAuthUI();
        loadGameState();
        // Keep HuggingFace space awake
        setInterval(() => {
          fetch(`${API_BASE}/health`).catch(() => {});
        }, 240000);
      });
