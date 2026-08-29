const state = {
  user: null,
  scenario: null,
  entries: {},
  attemptsUsed: 0,
  maxAttempts: 3,
  grading: null,
  solution: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const type = response.headers.get('content-type') || '';
  const payload = type.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = payload?.error || payload || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return payload;
}

function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove('show'), 2600);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
}

function parseNumeric(value) {
  if (value === null || value === undefined) return '';
  let text = String(value).trim().replace(/[$,%\s]/g, '').replace(/,/g, '');
  if (/^\(.*\)$/.test(text)) text = `-${text.slice(1, -1)}`;
  if (text === '' || text === '-') return '';
  const number = Number(text);
  return Number.isFinite(number) ? number : '';
}

function formatNumber(value, format = 'currency') {
  if (value === '—' || value === null || value === undefined || value === '') return value ?? '';
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  if (format === 'units' || format === 'hours') {
    return number.toLocaleString(undefined, { maximumFractionDigits: 1 });
  }
  return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function showLogin() {
  $('#loginView').classList.remove('hidden');
  $('#appView').classList.add('hidden');
}

function showApp() {
  $('#loginView').classList.add('hidden');
  $('#appView').classList.remove('hidden');
  $('#userBadge').textContent = `${state.user.display_name} · ${state.user.role}`;
}

function switchView(viewId, navSelector) {
  $$('.view').forEach(view => view.classList.add('hidden'));
  const target = document.getElementById(viewId);
  if (target) target.classList.remove('hidden');
  if (navSelector) {
    $$(`${navSelector} button`).forEach(btn => btn.classList.toggle('active', btn.dataset.view === viewId));
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderAssumptions() {
  const rows = state.scenario.assumptions.map(item => `
    <tr><td>${escapeHtml(item.category)}</td><td>${escapeHtml(item.item)}</td><td>${escapeHtml(item.value)}</td></tr>
  `).join('');
  $('#assumptionsTable').innerHTML = `
    <table><thead><tr><th>Area</th><th>Assumption</th><th>Budget Data</th></tr></thead><tbody>${rows}</tbody></table>
  `;
}

function cellForColumn(row, column) {
  return row.cells.find(cell => cell.column === column);
}

function salesSellingPrice() {
  const schedule = state.scenario?.schedules?.find(item => item.id === 'sales');
  const priceRow = schedule?.rows?.find(row => row.label === 'Selling price per unit');
  const priceCell = priceRow?.cells?.find(cell => cell.column === 'Q1');
  const parsed = parseNumeric(priceCell?.display);
  return parsed === '' ? 0 : Number(parsed);
}

function setComputedValue(key, value, format) {
  const input = document.querySelector(`[data-key="${CSS.escape(key)}"]`);
  if (value === '' || value === null || value === undefined || !Number.isFinite(Number(value))) {
    state.entries[key] = '';
    if (input) input.value = '';
    return;
  }
  const numeric = Number(value);
  state.entries[key] = numeric;
  if (input) {
    input.value = formatNumber(numeric, format);
    input.classList.remove('correct', 'incorrect');
  }
}

function recalculateSalesBudget() {
  if (!state.scenario) return;
  const quarters = ['Q1', 'Q2', 'Q3', 'Q4'];
  const price = salesSellingPrice();
  let complete = true;
  let totalUnits = 0;
  let totalRevenue = 0;

  quarters.forEach(quarter => {
    const key = `sales.units.${quarter}`;
    const input = document.querySelector(`[data-key="${CSS.escape(key)}"]`);
    const units = parseNumeric(input ? input.value : state.entries[key]);
    if (units === '') {
      complete = false;
      setComputedValue(`sales.revenue.${quarter}`, '', 'currency');
      return;
    }
    const numericUnits = Number(units);
    state.entries[key] = numericUnits;
    totalUnits += numericUnits;
    const revenue = numericUnits * price;
    totalRevenue += revenue;
    setComputedValue(`sales.revenue.${quarter}`, revenue, 'currency');
  });

  setComputedValue('sales.units.Total', complete ? totalUnits : '', 'units');
  setComputedValue('sales.revenue.Total', complete ? totalRevenue : '', 'currency');
}

function renderSchedules(container, linksContainer, solutionMode = false) {
  const schedules = state.scenario.schedules;
  linksContainer.innerHTML = schedules.map(s => `<a href="#${solutionMode ? 'solution-' : ''}${s.id}">${escapeHtml(s.title)}</a>`).join('');
  container.innerHTML = schedules.map(schedule => {
    const head = schedule.columns.map(col => `<th class="numeric">${escapeHtml(col)}</th>`).join('');
    const body = schedule.rows.map(row => {
      const cells = schedule.columns.map(column => {
        const cell = cellForColumn(row, column);
        if (!cell) return '<td class="readonly-cell numeric">—</td>';
        if (solutionMode && cell.key) {
          return `<td class="numeric readonly-cell">${formatNumber(state.solution[cell.key], cell.format)}</td>`;
        }
        if (cell.key) {
          const value = state.entries[cell.key] ?? '';
          const computed = Boolean(cell.computed);
          return `<td class="numeric"><input class="budget-input${computed ? ' computed-input' : ''}" inputmode="decimal" data-key="${escapeHtml(cell.key)}" data-format="${escapeHtml(cell.format || 'currency')}" data-computed="${computed ? 'true' : 'false'}" value="${escapeHtml(value)}" ${computed ? 'readonly aria-readonly="true"' : ''} aria-label="${escapeHtml(row.label)} ${escapeHtml(column)}"></td>`;
        }
        return `<td class="numeric readonly-cell">${formatNumber(cell.display, cell.format)}</td>`;
      }).join('');
      return `<tr><td>${escapeHtml(row.label)}${row.note ? `<span class="row-note">${escapeHtml(row.note)}</span>` : ''}</td>${cells}</tr>`;
    }).join('');
    return `
      <section id="${solutionMode ? 'solution-' : ''}${schedule.id}" class="panel schedule-card">
        <header><div><h2>${escapeHtml(schedule.title)}</h2><p class="instructions">${escapeHtml(schedule.instructions)}</p></div><span class="weight-pill">${schedule.weight} points</span></header>
        <div class="responsive-table"><table class="budget-table"><thead><tr><th>Budget line</th>${head}</tr></thead><tbody>${body}</tbody></table></div>
      </section>
    `;
  }).join('');

  if (!solutionMode) {
    $$('.budget-input', container).forEach(input => {
      input.addEventListener('input', () => {
        if (input.dataset.computed === 'true') return;
        state.entries[input.dataset.key] = parseNumeric(input.value);
        input.classList.remove('correct', 'incorrect');
        if (input.dataset.key.startsWith('sales.units.')) recalculateSalesBudget();
      });
      input.addEventListener('blur', () => {
        if (input.dataset.computed === 'true') return;
        const parsed = parseNumeric(input.value);
        if (parsed !== '') {
          input.value = formatNumber(parsed, input.dataset.format);
          state.entries[input.dataset.key] = parsed;
        }
        if (input.dataset.key.startsWith('sales.units.')) recalculateSalesBudget();
      });
      input.addEventListener('focus', () => {
        if (input.dataset.computed === 'true') return;
        const parsed = parseNumeric(input.value);
        input.value = parsed === '' ? '' : parsed;
      });
    });
    recalculateSalesBudget();
    if (state.grading?.details) applyFeedback(state.grading.details);
  }
}

function collectEntries() {
  recalculateSalesBudget();
  $$('.budget-input').forEach(input => {
    state.entries[input.dataset.key] = parseNumeric(input.value);
  });
  return state.entries;
}

function updateAttemptStatus() {
  $('#attemptStatus').textContent = `${state.attemptsUsed} of ${state.maxAttempts} used`;
  $('#submitBtn').disabled = state.attemptsUsed >= state.maxAttempts;
}

async function loadStudent() {
  const [scenarioPayload, work] = await Promise.all([api('/api/scenario'), api('/api/student/work')]);
  state.scenario = scenarioPayload.scenario;
  state.entries = work.entries || {};
  state.attemptsUsed = work.attempts_used;
  state.maxAttempts = work.max_attempts;
  renderSchedules($('#scheduleContainer'), $('#scheduleLinks'));
  updateAttemptStatus();
  await loadResults(false);
  $('#studentNav').classList.remove('hidden');
  $('#professorNav').classList.add('hidden');
  switchView('workspace', '#studentNav');
}

function renderResults(submission) {
  const host = $('#resultsContent');
  if (!submission) {
    host.innerHTML = `<p class="eyebrow">Grading</p><h2>No Submitted Attempt</h2><p class="muted">Complete the budget schedules and submit the assignment to receive a score.</p>`;
    return;
  }
  const grading = submission.grading;
  state.grading = grading;
  const score = Number(submission.score);
  const cards = Object.values(grading.schedule_results || {}).map(result => `
    <div class="feedback-card"><strong>${escapeHtml(result.title)}</strong><span>${result.correct} of ${result.possible_cells} cells correct</span><p>${Number(result.score).toFixed(2)} / ${result.weight} points</p></div>
  `).join('');
  host.innerHTML = `
    <p class="eyebrow">Latest graded attempt</p>
    <div class="results-score">
      <div class="score-circle" style="--score-angle:${Math.max(0, Math.min(100, score)) * 3.6}deg"><strong>${score.toFixed(2)}%</strong></div>
      <div><h2>Attempt ${submission.attempt_number}</h2><p class="muted">Submitted ${new Date(submission.submitted_at).toLocaleString()}</p></div>
    </div>
    <div class="feedback-grid">${cards}</div>
    <p class="small muted">Green cells are within the grading tolerance. Red cells require revision. Currency amounts are graded within $1; units and hours within 0.5.</p>
  `;
  if (grading.details) applyFeedback(grading.details);
}

function applyFeedback(details) {
  Object.entries(details).forEach(([key, detail]) => {
    const input = document.querySelector(`[data-key="${CSS.escape(key)}"]`);
    if (!input) return;
    input.classList.toggle('correct', Boolean(detail.correct));
    input.classList.toggle('incorrect', !detail.correct);
    input.title = detail.correct ? 'Correct' : `Review this amount. Your entry: ${detail.actual ?? 'blank'}`;
  });
}

async function loadResults(show = true) {
  const payload = await api('/api/student/results');
  renderResults(payload.submission);
  if (show) switchView('results', '#studentNav');
}

async function saveDraft() {
  const entries = collectEntries();
  const payload = await api('/api/student/save', { method: 'POST', body: JSON.stringify({ entries }) });
  $('#saveStatus').textContent = `Saved ${new Date(payload.saved_at).toLocaleTimeString()}`;
  toast('Draft saved');
}

async function submitAssignment() {
  const entries = collectEntries();
  const payload = await api('/api/student/submit', { method: 'POST', body: JSON.stringify({ entries }) });
  state.attemptsUsed = payload.attempt_number;
  state.grading = payload.grading;
  updateAttemptStatus();
  renderSchedules($('#scheduleContainer'), $('#scheduleLinks'));
  await loadResults(true);
  toast(`Attempt ${payload.attempt_number} submitted`);
}

function tableOrEmpty(headers, rows, emptyMessage) {
  if (!rows.length) return `<p class="muted">${escapeHtml(emptyMessage)}</p>`;
  return `<table><thead><tr>${headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>`;
}

async function loadProfessorDashboard() {
  const [studentsPayload, submissionsPayload] = await Promise.all([
    api('/api/professor/students'), api('/api/professor/submissions')
  ]);
  const studentRows = studentsPayload.students.map(s => `
    <tr>
      <td>${escapeHtml(s.display_name)}</td><td>${escapeHtml(s.username)}</td>
      <td class="numeric">${s.attempts}</td><td class="numeric">${s.best_score === null ? '—' : Number(s.best_score).toFixed(2)}</td>
      <td>${s.last_submitted ? new Date(s.last_submitted).toLocaleString() : '—'}</td>
      <td><button class="secondary reset-student" data-user-id="${s.user_id}" data-name="${escapeHtml(s.display_name)}">Reset</button></td>
    </tr>
  `);
  $('#studentTable').innerHTML = tableOrEmpty(['Student', 'Username', 'Attempts', 'Best Score', 'Last Submission', 'Action'], studentRows, 'No students have been created.');
  $$('.reset-student').forEach(btn => btn.addEventListener('click', async () => {
    if (!confirm(`Delete all saved work and submissions for ${btn.dataset.name}?`)) return;
    await api('/api/professor/reset', { method: 'POST', body: JSON.stringify({ user_id: Number(btn.dataset.userId) }) });
    toast('Student attempt history reset');
    await loadProfessorDashboard();
  }));

  const submissionRows = submissionsPayload.submissions.map(s => `
    <tr><td>${escapeHtml(s.display_name)}</td><td>${s.attempt_number}</td><td class="numeric">${Number(s.score).toFixed(2)}</td><td>${new Date(s.submitted_at).toLocaleString()}</td></tr>
  `);
  $('#submissionTable').innerHTML = tableOrEmpty(['Student', 'Attempt', 'Score', 'Submitted'], submissionRows, 'No submissions have been recorded.');

  $('#maxAttempts').value = studentsPayload.settings.max_attempts || 3;
  $('#passingScore').value = studentsPayload.settings.passing_score || 80;
  $('#allowFeedback').checked = studentsPayload.settings.allow_student_feedback === '1';
}

async function loadProfessor() {
  const assignmentPayload = await api('/api/professor/assignment');
  state.scenario = assignmentPayload.scenario;
  renderAssumptions();
  $('#studentNav').classList.add('hidden');
  $('#professorNav').classList.remove('hidden');
  await loadProfessorDashboard();
  switchView('professorDashboard', '#professorNav');
}

async function loadProfessorSolution() {
  if (!state.solution) {
    const payload = await api('/api/professor/solution');
    state.solution = payload.solution;
  }
  renderSchedules($('#solutionContainer'), $('#solutionLinks'), true);
}

async function loadDynamicsStatus() {
  const payload = await api('/api/professor/dynamics/status');
  const button = $('#syncDynamicsBtn');
  if (payload.configured) {
    $('#dynamicsStatusTitle').textContent = 'Dataverse connection configured';
    $('#dynamicsStatusText').textContent = `${payload.unsynced_submissions} unsynced submission(s) · ${payload.organization_url} · API ${payload.api_version}`;
    button.disabled = payload.unsynced_submissions === 0;
  } else {
    $('#dynamicsStatusTitle').textContent = 'Dataverse credentials not configured';
    $('#dynamicsStatusText').textContent = 'The local SQLite application is active. Set DATAVERSE_URL and DATAVERSE_ACCESS_TOKEN on the server to enable synchronization.';
    button.disabled = true;
  }
}

async function initialize() {
  try {
    const payload = await api('/api/session');
    if (!payload.authenticated) {
      showLogin();
      return;
    }
    state.user = payload.user;
    showApp();
    if (state.user.role === 'student') await loadStudent();
    else await loadProfessor();
  } catch (error) {
    showLogin();
    $('#loginError').textContent = error.message;
  }
}

$('#loginForm').addEventListener('submit', async event => {
  event.preventDefault();
  $('#loginError').textContent = '';
  try {
    const payload = await api('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username: $('#username').value, password: $('#password').value })
    });
    state.user = payload.user;
    showApp();
    if (state.user.role === 'student') await loadStudent();
    else await loadProfessor();
  } catch (error) {
    $('#loginError').textContent = error.message;
  }
});

$('#logoutBtn').addEventListener('click', async () => {
  await api('/api/logout', { method: 'POST', body: '{}' });
  state.user = null;
  location.reload();
});

$$('#studentNav button').forEach(btn => btn.addEventListener('click', async () => {
  if (btn.dataset.view === 'results') await loadResults(true);
  else switchView(btn.dataset.view, '#studentNav');
}));

$$('#professorNav button').forEach(btn => btn.addEventListener('click', async () => {
  if (btn.dataset.view === 'professorSolution') await loadProfessorSolution();
  if (btn.dataset.view === 'professorDashboard') await loadProfessorDashboard();
  if (btn.dataset.view === 'professorData') await loadDynamicsStatus();
  switchView(btn.dataset.view, '#professorNav');
}));

$('#saveBtn').addEventListener('click', () => saveDraft().catch(error => toast(error.message)));
$('#submitBtn').addEventListener('click', () => $('#confirmDialog').showModal());
$('#confirmSubmitBtn').addEventListener('click', event => {
  event.preventDefault();
  $('#confirmDialog').close();
  submitAssignment().catch(error => toast(error.message));
});
$('#printAssumptionsBtn').addEventListener('click', () => window.print());
$('#openProfessorSolutionBtn').addEventListener('click', async () => {
  await loadProfessorSolution();
  switchView('professorSolution', '#professorNav');
});
$('#printSolutionBtn').addEventListener('click', () => window.print());
$('#syncDynamicsBtn').addEventListener('click', async () => {
  try {
    const button = $('#syncDynamicsBtn');
    button.disabled = true;
    button.textContent = 'Synchronizing…';
    const payload = await api('/api/professor/dynamics/push', { method: 'POST', body: '{}' });
    toast(`Dataverse sync complete: ${payload.pushed} pushed, ${payload.failed} failed`);
    await loadDynamicsStatus();
    button.textContent = 'Push Unsynced Submissions';
  } catch (error) {
    $('#syncDynamicsBtn').textContent = 'Push Unsynced Submissions';
    toast(error.message);
    await loadDynamicsStatus().catch(() => {});
  }
});

$('#addStudentForm').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    await api('/api/professor/students', {
      method: 'POST',
      body: JSON.stringify({
        display_name: $('#newDisplayName').value,
        username: $('#newUsername').value,
        password: $('#newPassword').value,
      })
    });
    event.target.reset();
    toast('Student account created');
    await loadProfessorDashboard();
  } catch (error) { toast(error.message); }
});

$('#settingsForm').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    await api('/api/professor/settings', {
      method: 'POST',
      body: JSON.stringify({
        max_attempts: Number($('#maxAttempts').value),
        passing_score: Number($('#passingScore').value),
        allow_student_feedback: $('#allowFeedback').checked ? 1 : 0,
      })
    });
    toast('Assignment settings saved');
  } catch (error) { toast(error.message); }
});

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/service-worker.js').catch(() => {});
initialize();
