function toggleCard(idx) {
  const card = document.getElementById('card-'+idx);
  if (!card) return;
  card.classList.toggle('expanded');
  const job = _jobs[idx];
  if (job && !_viewedIds.has(job.id)) {
    _viewedIds.add(job.id);
    card.classList.add('viewed-card');
    fetch('/viewed',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:job.id})});
  }
}

// ── Apply checkbox ────────────────────────────────────────────────────
async function onApplyCheckbox(e, idx) {
  e.stopPropagation();
  const checked = e.target.checked;
  const job = _jobs[idx];
  if (!job) return;

  const label = e.target.closest('.applied-checkbox-label');
  const span  = label ? label.querySelector('.applied-check-text') : null;

  if (checked) {
    _appliedIds.add(job.id);
    job.applied_at = new Date().toISOString();
    _appliedJobs.push({...job});
    if (span) span.textContent = '✅ Applied';

    // Add badge to card title row
    const card = document.getElementById('card-'+idx);
    if (card) {
      const titleRow = card.querySelector('.job-title-row');
      if (titleRow && !titleRow.querySelector('.applied-badge')) {
        titleRow.insertAdjacentHTML('beforeend','<span class="applied-badge">✅ Applied</span>');
      }
    }
    try {
      await fetch('/applied',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job})});
    } catch(_) {}
  } else {
    // Uncheck = unapply
    _appliedIds.delete(job.id);
    _appliedJobs = _appliedJobs.filter(j => j.id !== job.id);
    if (span) span.textContent = 'Mark Applied';

    const card = document.getElementById('card-'+idx);
    if (card) {
      const badge = card.querySelector('.applied-badge');
      if (badge) badge.remove();
    }
    try { await fetch('/applied/'+job.id,{method:'DELETE'}); } catch(_) {}
  }
  updateAppliedBadge();
  renderApplied();
}

function updateAppliedBadge() {
  const n = _appliedJobs.length;
  const b = document.getElementById('appliedBadge');
  b.textContent = n;
  b.classList.toggle('show', n > 0);
}

// ── Applied page ──────────────────────────────────────────────────────
function renderApplied() {
  const el  = document.getElementById('appliedList');
  const sub = document.getElementById('appliedSub');
  sub.textContent = `${_appliedJobs.length} application${_appliedJobs.length!==1?'s':''}`;

  if (!_appliedJobs.length) {
    el.innerHTML = '<div class="empty">No applications yet — tick the checkbox on any listing to mark as applied.</div>';
    return;
  }

  // Sort by applied_at descending
  const sorted = [..._appliedJobs].sort((a,b) => {
    return new Date(b.applied_at||0) - new Date(a.applied_at||0);
  });

  // Group by date label
  function dateLabel(iso) {
    if (!iso) return 'Unknown Date';
    const d = new Date(iso);
    const today = new Date(); today.setHours(0,0,0,0);
    const yesterday = new Date(today); yesterday.setDate(today.getDate()-1);
    const dDay = new Date(d); dDay.setHours(0,0,0,0);
    if (dDay.getTime() === today.getTime()) return 'Today';
    if (dDay.getTime() === yesterday.getTime()) return 'Yesterday';
    return d.toLocaleDateString('en-US',{weekday:'long', month:'short', day:'numeric', year:'numeric'});
  }

  // Group by date then by normalized title
  const byDate = {};
  for (const j of sorted) {
    const dl = dateLabel(j.applied_at);
    if (!byDate[dl]) byDate[dl] = {};
    const titleKey = (j.title||'Untitled').trim().toLowerCase();
    if (!byDate[dl][titleKey]) byDate[dl][titleKey] = {title: j.title||'Untitled', jobs: []};
    byDate[dl][titleKey].jobs.push(j);
  }

  let html = '';
  for (const [date, titleGroups] of Object.entries(byDate)) {
    html += `<div class="applied-date-group">
      <div class="applied-date-label">${esc(date)}</div>`;

    for (const [, group] of Object.entries(titleGroups)) {
      const hasMultiple = group.jobs.length > 1;
      html += `<div class="applied-title-group">
        <div class="applied-title-header">
          <span class="applied-title-name">${esc(group.title)}</span>
          ${hasMultiple ? `<span class="applied-title-count">${group.jobs.length} applications</span>` : ''}
        </div>`;

      for (const j of group.jobs) {
        const src = (j.source||'').toLowerCase();
        const dotClass = 'dot-'+(src||'unknown');
        const time = j.applied_at
          ? new Date(j.applied_at).toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'})
          : '';
        html += `
        <div class="applied-card">
          <div class="source-dot ${dotClass}"></div>
          <div class="applied-info">
            <div class="applied-meta">
              ${j.company  ? `<span class="applied-company">${esc(j.company)}</span>`:''}
              ${j.location ? `<span>📍 ${esc(j.location)}</span>`:''}
              ${time       ? `<span>⏱ ${time}</span>`:''}
            </div>
          </div>
          <div class="applied-actions">
            ${j.url ? `<a class="btn-icon" href="${esc(j.url)}" target="_blank" rel="noopener" title="Open listing">↗</a>`:''}
            <button class="btn-icon del" onclick="deleteApplied('${j.id}')" title="Remove">🗑</button>
          </div>
        </div>`;
      }
      html += `</div>`;
    }
    html += `</div>`;
  }

  el.innerHTML = html;
}

async function deleteApplied(jobId) {
  _appliedJobs = _appliedJobs.filter(j => j.id !== jobId);
  _appliedIds.delete(jobId);
  updateAppliedBadge();
  renderApplied();
  renderJobs(_jobs);  // refresh badges on search cards
  try { await fetch('/applied/'+jobId,{method:'DELETE'}); } catch(_) {}
}

function clearResume() {
  _resumeSkills = [];
  document.getElementById('resumeBanner').classList.remove('show');
  fetch('/resume/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:'',skills:[]})});
  if (_jobs.length) renderJobs(_jobs);
}

// ── Drawer ────────────────────────────────────────────────────────────
function openDrawer(idx, tab) {
  const job = _jobs[idx];
  if (!job) return;

  const isSameJob = (idx === _activeJobIdx);
  _activeJobIdx   = idx;
  _activeJobDesc  = job.description || '';
  _activeJobTitle = job.title || 'this job';

  document.getElementById('drawerTitle').textContent   = job.title   || 'Job Listing';
  document.getElementById('drawerCompany').textContent = job.company || '';
  document.getElementById('analyzeJobLabel').textContent =
    `Analyzing: ${_activeJobTitle}` + (job.company ? ` @ ${job.company}` : '');
  document.getElementById('networkJobLabel').textContent =
    `Finding contacts at: ${job.company || _activeJobTitle}`;

  // Reset network pane on job change
  if (!isSameJob) {
    document.getElementById('recruiterResult').innerHTML = '';
    document.getElementById('msgPanel').style.display = 'none';
    document.getElementById('msgResult').innerHTML = '';
    _activeRecruiter = null;
  }

  // Only reset the analyze pane if it is a different job, or no analysis is running
  if (!isSameJob || !_analysisRunning) {
    document.getElementById('fileName').textContent     = '';
    document.getElementById('resumeFile').value         = '';
    document.getElementById('savedResumeSelect').value  = '';
    _selectedSavedResumeId                              = '';
    document.getElementById('runBtn').disabled          = true;
    document.getElementById('analysisResult').innerHTML = '';
  }

  loadSavedResumes(_selectedSavedResumeId);

  // Only reload the iframe if it is a different job
  if (!isSameJob) {
    const iframe  = document.getElementById('drawerIframe');
    const loading = document.getElementById('drawerLoading');
    const blocked = document.getElementById('drawerBlocked');
    blocked.classList.remove('show');
    loading.classList.remove('hidden');
    iframe.src = 'about:blank';

    if (job.url) {
      document.getElementById('drawerBlockedLink').href = job.url;
      let loaded = false;
      const to = setTimeout(() => { if (!loaded) showBlocked(); }, 7000);
      iframe.onload = () => {
        loaded = true; clearTimeout(to);
        try {
          const doc = iframe.contentDocument || iframe.contentWindow?.document;
          if (!doc || doc.body?.innerHTML?.trim() === '') { showBlocked(); return; }
        } catch(_) {}
        loading.classList.add('hidden');
      };
      iframe.onerror = () => { loaded=true; clearTimeout(to); showBlocked(); };
      setTimeout(() => { iframe.src = job.url; }, 50);
    } else {
      showBlocked();
    }
  }

  document.getElementById('drawerOverlay').classList.add('open');
  document.body.classList.add('drawer-open');
  // If reopening the same job while analysis is still running, go straight to analyze tab
  switchTab(isSameJob && _analysisRunning ? 'analyze' : (tab || 'apply'));
}

function switchTab(tab) {
  document.getElementById('tabApply').classList.toggle('active',   tab==='apply');
  document.getElementById('tabAnalyze').classList.toggle('active', tab==='analyze');
  document.getElementById('tabNetwork').classList.toggle('active', tab==='network');
  document.getElementById('paneApply').classList.toggle('hidden',   tab!=='apply');
  document.getElementById('paneAnalyze').classList.toggle('hidden', tab!=='analyze');
  document.getElementById('paneNetwork').classList.toggle('hidden', tab!=='network');
}

function showBlocked() {
  document.getElementById('drawerLoading').classList.add('hidden');
  document.getElementById('drawerBlocked').classList.add('show');
  document.getElementById('drawerIframe').src = 'about:blank';
}

function expandFromPill() {
  _drawerMin = false;
  // Re-open the drawer for the active job; openDrawer preserves in-progress state
  if (_activeJobIdx >= 0) {
    openDrawer(_activeJobIdx, 'analyze');
  } else {
    document.getElementById('drawerOverlay').classList.add('open');
    document.body.classList.add('drawer-open');
    switchTab('analyze');
  }
}

function showPill(label, sub, isDone) {
  document.getElementById('pillLabel').textContent  = label;
  document.getElementById('pillSub').textContent    = sub;
  document.getElementById('pillSpinner').style.display = isDone ? 'none' : 'block';
  document.getElementById('pillDone').style.display    = isDone ? 'flex' : 'none';
  document.getElementById('pillExpand').textContent    = isDone ? 'View →' : 'Expand';
  document.getElementById('analysisPill').classList.add('visible');
}
function hidePill() { document.getElementById('analysisPill').classList.remove('visible'); }

function closeDrawer() {
  document.getElementById('drawerOverlay').classList.remove('open');
  document.body.classList.remove('drawer-open');
  _drawerMin = false;
  // Keep the pill alive if analysis is still running so user can reopen
  if (!_analysisRunning) hidePill();
  setTimeout(() => {
    document.getElementById('drawerIframe').src = 'about:blank';
    document.getElementById('drawerLoading').classList.remove('hidden');
    document.getElementById('drawerBlocked').classList.remove('show');
  }, 300);
}


// ── File upload ───────────────────────────────────────────────────────
