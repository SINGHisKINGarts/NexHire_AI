async function loadResume() {
  try {
    const r = await fetch('/resume');
    if (!r.ok) return;
    const d = await r.json();
    if (d.skills && d.skills.length) {
      _resumeSkills = d.skills.map(s => s.toLowerCase());
      document.getElementById('resumeBanner').classList.add('show');
    }
  } catch(_) {}
}

async function loadViewed() {
  try {
    const d = await (await fetch('/viewed')).json();
    _viewedIds = new Set(d.viewed || []);
  } catch(_) {}
}

async function loadApplied() {
  try {
    const d = await (await fetch('/applied')).json();
    _appliedJobs = d.applied || [];
    _appliedIds  = new Set(_appliedJobs.map(j => j.id));
    updateAppliedBadge();
    renderApplied();
  } catch(_) {}
}

async function loadSavedResumes(preferredId='') {
  try {
    const res = await fetch('/resumes');
    if (!res.ok) return;
    const data = await res.json();
    _savedResumes = data.resumes || [];
    const select = document.getElementById('savedResumeSelect');
    const current = preferredId || _selectedSavedResumeId;
    select.innerHTML = `<option value="">Select a saved resume</option>` + _savedResumes.map(r =>
      `<option value="${esc(r.id)}">${esc(r.name || r.filename)}</option>`
    ).join('');
    if (current && _savedResumes.some(r => r.id === current)) {
      select.value = current;
      _selectedSavedResumeId = current;
    } else {
      select.value = '';
      _selectedSavedResumeId = '';
    }
    syncResumeChoiceState();
  } catch(_) {}
}

function refreshSavedResumes() {
  loadSavedResumes(_selectedSavedResumeId);
}

// ── Navigation ────────────────────────────────────────────────────────
