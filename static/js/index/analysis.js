function onFileChange(input) {
  const file = input.files[0];
  document.getElementById('fileName').textContent = file ? '✔ '+file.name : '';
  if (file) {
    _selectedSavedResumeId = '';
    document.getElementById('savedResumeSelect').value = '';
  }
  syncResumeChoiceState();
}

function onSavedResumeChange(select) {
  _selectedSavedResumeId = select.value || '';
  if (_selectedSavedResumeId) {
    document.getElementById('resumeFile').value = '';
    document.getElementById('fileName').textContent = `Using saved resume: ${select.options[select.selectedIndex].text}`;
  } else if (!document.getElementById('resumeFile').files[0]) {
    document.getElementById('fileName').textContent = '';
  }
  syncResumeChoiceState();
}

function syncResumeChoiceState() {
  const hasUpload = !!document.getElementById('resumeFile').files[0];
  const hasSaved = !!_selectedSavedResumeId;
  document.getElementById('runBtn').disabled = !(hasUpload || hasSaved);
}

// ── Analysis ──────────────────────────────────────────────────────────
async function runAnalysis() {
  const fileInput = document.getElementById('resumeFile');
  const resultDiv = document.getElementById('analysisResult');
  const btn       = document.getElementById('runBtn');
  if (!fileInput.files[0] && !_selectedSavedResumeId) return;
  if (!_activeJobDesc) {
    resultDiv.innerHTML = `<div class="error-box">⚠️ No job description for this listing.</div>`; return;
  }

  btn.disabled = true; btn.textContent = 'Analyzing…';
  _analysisRunning = true;
  resultDiv.innerHTML = `<div class="loader-inline"><div class="spinner"></div> Running analysis…</div>`;
  showPill(`Analyzing: ${_activeJobTitle}`, 'Running AI analysis…', false);

  const fd = new FormData();
  fd.append('job_desc', _activeJobDesc);
  if (fileInput.files[0]) {
    fd.append('file', fileInput.files[0]);
  }
  if (_selectedSavedResumeId) {
    fd.append('saved_resume_id', _selectedSavedResumeId);
  }

  try {
    const res  = await fetch('/analyze',{method:'POST',body:fd});
    if (!res.ok) throw new Error('Server error '+res.status);
    const data = await res.json();

    if (data.error) {
      resultDiv.innerHTML = `<div class="error-box">❌ ${data.error}<br><small style="margin-top:5px;display:block">Make sure Ollama is running: <code>ollama serve</code></small></div>`;
      showPill(`Failed: ${_activeJobTitle}`,'See error',true); return;
    }

    renderResult(data, resultDiv);

    // store for outreach message gen
    _activeAnalysis   = data.result || {};
    _activeResumeText = data.resume_text || '';

    // persist resume skills for recommendations
    if (data.resume_text) {
      const skills = extractSkills(data.resume_text);
      _resumeSkills = skills;
      fetch('/resume/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:data.resume_text,skills})});
      document.getElementById('resumeBanner').classList.add('show');
      if (_jobs.length) renderJobs(_jobs);
    }

    if (fileInput.files[0]) {
      await loadSavedResumes();
      document.getElementById('fileName').textContent = 'Saved and analyzed successfully';
    }

    const score = Math.round((data.result||{}).match_score||0);
    showPill(`Done: ${_activeJobTitle}`,`Match: ${score}%`,true);
    if (!_drawerMin) setTimeout(hidePill, 4000);
  } catch(e) {
    resultDiv.innerHTML = `<div class="error-box">❌ ${e.message}</div>`;
    showPill(`Failed: ${_activeJobTitle}`,'Error',true);
  } finally {
    _analysisRunning = false;
    btn.textContent = 'Analyze Resume →';
    syncResumeChoiceState();
  }
}

function extractSkills(text) {
  const lower = text.toLowerCase();
  return KNOWN_SKILLS.filter(s => lower.includes(s));
}

function renderResult(data, el) {
  const r     = data.result || {};
  const score = Math.round(r.match_score || 0);
  const label = score>=75 ? 'Strong match 🎯' : score>=50 ? 'Good match 📊' : 'Moderate match ⚠️';
  const model = data.model_used ? `<span style="font-size:0.68rem;color:#555;margin-left:8px">via ${data.model_used}</span>` : '';

  const section = (title, items, render) => {
    if (!items||!items.length) return '';
    return `<div class="result-section"><h4>${title}</h4><ul>${items.map(render).join('')}</ul></div>`;
  };

  // ReAct trace block
  let reactHtml = '';
  const trace = r.react_trace;
  if (trace) {
    const matchRows = (trace.match_analysis||[]).map(m => {
      const color = m.status==='PRESENT' ? '#4ade80' : m.status==='PARTIAL' ? '#fbbf24' : '#f87171';
      return `<li style="display:flex;gap:8px;align-items:flex-start;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)">
        <span style="color:${color};font-size:0.7rem;font-family:'Syne',sans-serif;font-weight:700;min-width:60px;margin-top:1px">${esc(m.status||'')}</span>
        <span style="flex:1;font-size:0.76rem;color:#ccc"><strong style="color:#e8e8f0">${esc(m.requirement||'')}</strong>${m.evidence ? ` — <em style="color:#888">${esc(m.evidence)}</em>` : ''}</span>
      </li>`;
    }).join('');

    reactHtml = `
    <details class="react-trace-block" style="margin-bottom:12px">
      <summary style="cursor:pointer;font-size:0.72rem;color:#6c63ff;font-family:'Syne',sans-serif;font-weight:700;letter-spacing:0.5px;padding:7px 10px;background:rgba(108,99,255,0.07);border:1px solid rgba(108,99,255,0.15);border-radius:8px;list-style:none;user-select:none">
        🧠 View AI Reasoning Trace ▾
      </summary>
      <div style="margin-top:6px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:10px 12px">
        ${trace.scoring_rationale ? `<p style="font-size:0.76rem;color:#aaa;margin-bottom:10px;line-height:1.5"><strong style="color:#d1d1ff">Scoring rationale:</strong> ${esc(trace.scoring_rationale)}</p>` : ''}
        ${matchRows ? `<ul style="list-style:none;padding:0">${matchRows}</ul>` : ''}
      </div>
    </details>`;
  }

  // Line edits with before/after diff style
  const lineEditsHtml = (r.line_edits||[]).length ? `
  <div class="result-section">
    <h4>✏️ Resume Line Edits</h4>
    <ul>${(r.line_edits||[]).map(p => {
      if (typeof p==='string') return `<li>${esc(p)}</li>`;
      return `<li style="padding:7px 0">
        ${p.location ? `<div style="font-size:0.66rem;color:#555;margin-bottom:4px;font-family:'Syne',sans-serif;letter-spacing:0.3px">${esc(p.location)}</div>` : ''}
        <div style="background:rgba(255,80,80,0.07);border-left:2px solid #f87171;padding:5px 8px;border-radius:0 5px 5px 0;font-size:0.75rem;color:#aaa;margin-bottom:4px">
          <span style="font-size:0.6rem;color:#f87171;font-family:'Syne',sans-serif;font-weight:700;letter-spacing:0.4px;display:block;margin-bottom:2px">BEFORE</span>
          ${esc(p.original||'')}
        </div>
        <div style="background:rgba(74,222,128,0.07);border-left:2px solid #4ade80;padding:5px 8px;border-radius:0 5px 5px 0;font-size:0.75rem;color:#d1ffd1">
          <span style="font-size:0.6rem;color:#4ade80;font-family:'Syne',sans-serif;font-weight:700;letter-spacing:0.4px;display:block;margin-bottom:2px">AFTER</span>
          ${esc(p.improved||'')}
        </div>
      </li>`;
    }).join('')}</ul>
  </div>` : '';

  el.innerHTML = `
    <div class="result-area">
      <div class="score-ring">
        <div class="score-circle" style="--score:${score}">
          <span class="score-num">${score}%</span>
        </div>
        <div class="score-label">
          <h3>Match Score: ${score}% ${model}</h3>
          <p>${label}</p>
        </div>
      </div>
      ${reactHtml}
      ${section('🚫 Missing Skills', r.missing_skills, s =>
        `<li><span class="pill">${esc(s.skill||s)}</span>${s.action?' — '+esc(s.action):''}</li>`
      )}
      ${section('⚠️ Areas to Strengthen', r.weaknesses, w => `<li>${esc(w)}</li>`)}
      ${lineEditsHtml}
      ${section('➕ New Points to Add', r.new_points, p =>
        `<li>
          ${p.location?`<span class="pill" style="margin-bottom:4px">${esc(p.location)}</span><br>`:''}
          <span style="color:#d1d1ff">${esc(p.point||p)}</span>
        </li>`
      )}
      ${r.raw ? `<div class="error-box" style="margin-top:12px;font-size:0.74rem"><strong>Raw response (JSON parse failed):</strong><br><pre style="white-space:pre-wrap;margin-top:6px;word-break:break-word">${esc(r.raw)}</pre></div>` : ''}
    </div>`;
}

// ── Network / Recruiter ───────────────────────────────────────────────
