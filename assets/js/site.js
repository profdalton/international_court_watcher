/* International Court Watcher — front-end rendering
   Reads data/hearings.json + data/courts.json (produced by the
   Python scrapers in /scrapers, refreshed via GitHub Actions) and
   renders them into the homepage feed / court pages. No build step. */

const DATA_ROOT = document.body.dataset.root || '.';

async function loadData() {
  const [hearingsRes, courtsRes] = await Promise.all([
    fetch(`${DATA_ROOT}/data/hearings.json`),
    fetch(`${DATA_ROOT}/data/courts.json`),
  ]);
  const hearings = await hearingsRes.json();
  const courts = await courtsRes.json();
  return { hearings, courts };
}

function fmtDate(iso) {
  const d = new Date(iso + 'T00:00:00Z');
  return {
    day: d.toLocaleDateString('en-US', { day: '2-digit', timeZone: 'UTC' }),
    weekday: d.toLocaleDateString('en-US', { weekday: 'short', timeZone: 'UTC' }),
    monthYear: d.toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' }),
  };
}

function isUpcoming(iso) {
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  return new Date(iso + 'T00:00:00Z') >= today;
}

function hearingRow(h, courts) {
  const meta = courts[h.court] || {};
  const { day, weekday, monthYear } = fmtDate(h.date);
  const row = document.createElement('div');
  row.className = 'hearing-row';
  row.dataset.court = h.court;
  row.style.setProperty('--row-accent', meta.accent || '#2571bb');
  row.innerHTML = `
    <div><span class="date">${day}</span><span class="weekday">${weekday}</span></div>
    <div class="time">${h.time || ''}</div>
    <div class="court-tag">${meta.abbr || h.court.toUpperCase()}</div>
    <div class="case">
      ${h.url ? `<a href="${h.url}" target="_blank" rel="noopener">${h.case_name}</a>` : h.case_name}
      <span class="type">${h.hearing_type || ''}${h.location ? ' · ' + h.location : ''}</span>
    </div>
  `;
  return { row, monthYear };
}

function renderFeed(container, hearings, courts, filterCourt) {
  container.innerHTML = '';
  const upcoming = hearings
    .filter((h) => isUpcoming(h.date))
    .filter((h) => !filterCourt || filterCourt === 'all' || h.court === filterCourt)
    .sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));

  if (upcoming.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'No upcoming hearings currently on the docket for this view. Check back after the next update, or see each court\u2019s official calendar linked below.';
    container.appendChild(empty);
    return;
  }

  let lastMonth = null;
  upcoming.forEach((h) => {
    const { row, monthYear } = hearingRow(h, courts);
    if (monthYear !== lastMonth) {
      const heading = document.createElement('div');
      heading.className = 'month-heading';
      heading.textContent = monthYear;
      container.appendChild(heading);
      lastMonth = monthYear;
    }
    container.appendChild(row);
  });
}

async function initHomepage() {
  const feedEl = document.getElementById('feed');
  const filtersEl = document.getElementById('filters');
  const gridEl = document.getElementById('court-grid');
  const updatedEl = document.getElementById('updated');
  if (!feedEl) return;

  const { hearings, courts } = await loadData();
  const list = hearings.hearings || [];

  if (updatedEl) {
    const d = new Date(hearings.generated_at);
    updatedEl.textContent = `Data last refreshed ${d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`;
  }

  let active = 'all';
  if (filtersEl) {
    const courtOrder = Object.keys(courts);
    const chips = [{ key: 'all', label: 'All courts' }].concat(
      courtOrder.map((k) => ({ key: k, label: courts[k].abbr }))
    );
    chips.forEach(({ key, label }) => {
      const btn = document.createElement('button');
      btn.className = 'chip';
      btn.setAttribute('aria-pressed', key === 'all' ? 'true' : 'false');
      btn.dataset.key = key;
      const dot = key === 'all' ? '' : `<span class="dot" style="background:${courts[key].accent}"></span>`;
      btn.innerHTML = `${dot}${label}`;
      btn.addEventListener('click', () => {
        active = key;
        filtersEl.querySelectorAll('.chip').forEach((c) => c.setAttribute('aria-pressed', c.dataset.key === key ? 'true' : 'false'));
        renderFeed(feedEl, list, courts, active);
      });
      filtersEl.appendChild(btn);
    });
  }

  renderFeed(feedEl, list, courts, active);

  if (gridEl) {
    gridEl.innerHTML = '';
    Object.entries(courts).forEach(([slug, c]) => {
      const count = list.filter((h) => h.court === slug && isUpcoming(h.date)).length;
      const a = document.createElement('a');
      a.className = 'court-card';
      a.href = `courts/${slug}.html`;
      a.style.setProperty('--card-accent', c.accent);
      a.innerHTML = `
        <span class="abbr">${c.system}</span>
        <h3>${c.abbr}</h3>
        <span class="seat">${c.seat}</span>
        <span class="count">${count} upcoming</span>
      `;
      gridEl.appendChild(a);
    });
  }
}

async function initCourtPage(slug) {
  const feedEl = document.getElementById('feed');
  const updatedEl = document.getElementById('updated');
  if (!feedEl) return;
  const { hearings, courts } = await loadData();
  const list = (hearings.hearings || []).filter((h) => h.court === slug);

  if (updatedEl) {
    const d = new Date(hearings.generated_at);
    updatedEl.textContent = `Data last refreshed ${d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`;
  }

  renderFeed(feedEl, list, courts, slug);
}

window.ICW = { initHomepage, initCourtPage };
