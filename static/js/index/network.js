async function findRecruiters() {
  const job = _jobs[_activeJobIdx];
  if (!job) return;
  const btn = document.getElementById('findBtn');
  const el  = document.getElementById('recruiterResult');
  btn.disabled = true; btn.textContent = '🔍 Searching…';
  el.innerHTML = `<div class="loader-inline"><div class="spinner"></div> Finding recruiters at ${esc(job.company||job.title)}…</div>`;
  try {
    const res  = await fetch('/recruiter/find', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ company: job.company||'', title: job.title||'' })
    });
    const data = await res.json();
    if (data.error) { el.innerHTML = `<div class="error-box">❌ ${esc(data.error)}</div>`; return; }
    renderRecruiters(data, el);
  } catch(e) {
    el.innerHTML = `<div class="error-box">❌ ${e.message}</div>`;
  } finally {
    btn.disabled = false; btn.textContent = '👥 Find Recruiters & HRs';
  }
}

function renderRecruiters(data, el) {
  let html = '';

  if (data.company_people_url) {
    html += `<div class="email-formats-block">
      <div class="email-formats-title">👥 Start with the company people page</div>
      <div class="rec-actions" style="margin-top:10px">
        <a class="btn-li" href="${esc(data.company_people_url)}" target="_blank" rel="noopener">🔗 Open LinkedIn People</a>
      </div>
    </div>`;
  }

  // Email formats block
  if (data.email_formats && data.email_formats.length) {
    html += `<div class="email-formats-block">
      <div class="email-formats-title">📧 Email Formats at ${esc(data.company_domain||'this company')}</div>`;
    for (const f of data.email_formats) {
      html += `<div class="email-format-row">
        <span class="email-format-label">${esc(f.format||'')} &nbsp;<span style="color:#555;font-size:0.68rem">e.g. ${esc(f.example||'')}</span></span>
        <span class="email-format-copy" onclick='copyText(${JSON.stringify(f.example || "")},this)'>Copy example</span>
      </div>`;
    }
    html += `</div>`;
  }

  // Recruiter cards
  for (const c of (data.suggested_contacts||[])) {
    const pri = (c.outreach_priority||'MEDIUM').toLowerCase();
    // Safely encode recruiter object for inline onclick
    const safeJson = JSON.stringify(c).replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'&quot;');
    html += `<div class="recruiter-card priority-${pri}">
      <div class="rec-role">
        ${esc(c.role||'')}
        <span class="priority-badge ${pri}">${esc(c.outreach_priority||'')}</span>
      </div>
      <div class="rec-why">${esc(c.why||'')}</div>
      ${c.search_hint ? `<div class="rec-why" style="margin-top:6px;color:#9aa0b7">Search hint: ${esc(c.search_hint)}</div>` : ''}
      <div class="rec-actions">
        ${c.linkedin_search_url
          ? `<a class="btn-li" href="${esc(c.linkedin_search_url)}" target="_blank" rel="noopener">🔗 ${esc(c.linkedin_search_label||'Search on LinkedIn')}</a>`
          : ''}
        ${c.google_search_url
          ? `<a class="btn-outline" href="${esc(c.google_search_url)}" target="_blank" rel="noopener">🌐 Google profile search</a>`
          : ''}
        ${c.email_guess
          ? `<button class="btn-email-copy" onclick='copyText(${JSON.stringify(c.email_guess || "")},this)'>📋 ${esc(c.email_guess)}${c.email_type==='guessed' ? ' · guessed' : ''}</button>`
          : ''}
        <button class="btn-msg" onclick="openMsgPanel(${safeJson})">✍️ Write Message</button>
      </div>
    </div>`;
  }

  // Pro tips
  if (data.pro_tips && data.pro_tips.length) {
    html += `<div class="pro-tips-block">
      <div class="pro-tips-title">💡 Pro Tips</div>
      ${data.pro_tips.map(t=>`<div class="pro-tip-item">${esc(t)}</div>`).join('')}
    </div>`;
  }

  el.innerHTML = html;
}

function openMsgPanel(recruiter) {
  _activeRecruiter = recruiter;
  document.getElementById('msgPanelTitle').textContent = `Write Message — ${recruiter.role||'Recruiter'}`;
  document.getElementById('msgPanel').style.display = 'block';
  document.getElementById('msgResult').innerHTML = '';

  const hasAnalysis = _activeResumeText || Object.keys(_activeAnalysis).length;
  if (!hasAnalysis) {
    document.getElementById('msgResult').innerHTML =
      `<div style="font-size:0.76rem;color:#fbbf24;background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.2);border-radius:8px;padding:9px 12px;margin-top:4px">
        💡 Tip: Run a resume analysis in the Analyze tab first — the message will be much more personalised.
      </div>`;
  }
  document.getElementById('msgPanel').scrollIntoView({ behavior:'smooth', block:'nearest' });
}

function closeMsgPanel() {
  document.getElementById('msgPanel').style.display = 'none';
  _activeRecruiter = null;
}

function setTone(btn, tone) {
  _activeTone = tone;
  document.querySelectorAll('.tone-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

async function generateMessage() {
  if (!_activeRecruiter) return;
  const job = _jobs[_activeJobIdx];
  if (!job) return;

  const btn = document.getElementById('genMsgBtn');
  const el  = document.getElementById('msgResult');
  btn.disabled = true; btn.textContent = '✨ Generating…';
  el.innerHTML = `<div class="loader-inline"><div class="spinner"></div> Writing personalised message…</div>`;

  try {
    const res = await fetch('/recruiter/message', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        recruiter:    _activeRecruiter,
        job_title:    job.title   || '',
        company:      job.company || '',
        job_desc:     job.description || '',
        resume_text:  _activeResumeText,
        analysis:     _activeAnalysis,
        tone:         _activeTone,
      })
    });
    const data = await res.json();
    if (data.error) { el.innerHTML = `<div class="error-box">❌ ${esc(data.error)}</div>`; return; }
    renderMessage(data, el);
  } catch(e) {
    el.innerHTML = `<div class="error-box">❌ ${e.message}</div>`;
  } finally {
    btn.disabled = false; btn.textContent = '✨ Generate Message';
  }
}

function renderMessage(data, el) {
  const dm    = data.linkedin_dm    || '';
  const subj  = data.email_subject  || '';
  const email = data.email_body     || '';
  const tips  = data.personalisation_tips || [];

  el.innerHTML = `
    <div class="msg-section">
      <div class="msg-section-header">
        <span class="msg-section-title">💬 LinkedIn DM</span>
        <button class="btn-copy-msg" onclick="copyMsgText(${JSON.stringify(dm)},this)">Copy</button>
      </div>
      <div class="msg-text">${esc(dm)}</div>
      <div class="msg-char-count" style="color:${dm.length>300?'#f87171':'var(--muted)'}">${dm.length}/300 chars</div>
    </div>
    <div class="msg-section">
      <div class="msg-section-header">
        <span class="msg-section-title">📧 Cold Email</span>
        <button class="btn-copy-msg" onclick="copyMsgText(${JSON.stringify('Subject: '+subj+'\n\n'+email)},this)">Copy All</button>
      </div>
      ${subj ? `<div class="msg-subject">Subject: ${esc(subj)}</div>` : ''}
      <div class="msg-text">${esc(email)}</div>
    </div>
    ${tips.length ? `
    <div class="personalisation-tips">
      <div style="font-family:'Syne',sans-serif;font-size:0.66rem;font-weight:700;text-transform:uppercase;letter-spacing:0.7px;color:#4ade80;margin-bottom:6px">Before you send</div>
      ${tips.map(t=>`<div class="personalisation-tip">${esc(t)}</div>`).join('')}
    </div>` : ''}`;
}

function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.textContent;
    btn.classList.add('copied');
    btn.textContent = '✅ Copied!';
    setTimeout(() => { btn.textContent = orig; btn.classList.remove('copied'); }, 2000);
  }).catch(() => { btn.textContent = '⚠️ Failed'; });
}

function copyMsgText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.textContent;
    btn.classList.add('done');
    btn.textContent = '✅ Copied';
    setTimeout(() => { btn.textContent = orig; btn.classList.remove('done'); }, 2500);
  }).catch(() => { btn.textContent = '⚠️ Failed'; });
}

// ── Helpers ───────────────────────────────────────────────────────────
