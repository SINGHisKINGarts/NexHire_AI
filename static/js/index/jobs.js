function isRecommended(job) {
  if (!_resumeSkills.length) return false;
  const haystack = [job.title, job.description, ...(job.skills||[])].join(' ').toLowerCase();
  const hits = _resumeSkills.filter(s => haystack.includes(s));
  return hits.length >= Math.max(1, Math.floor(_resumeSkills.length * 0.2));
}

// ── Render jobs ───────────────────────────────────────────────────────
function renderJobs(jobs) {
  const el = document.getElementById('jobs');
  if (!jobs.length) { el.innerHTML = '<div class="empty">No jobs found. Try different keywords.</div>'; return; }

  const sorted = [...jobs].sort((a,b) => {
    const ra = isRecommended(a), rb = isRecommended(b);
    if (ra !== rb) return rb - ra;
    return (_viewedIds.has(a.id)?1:0) - (_viewedIds.has(b.id)?1:0);
  });

  el.innerHTML = sorted.map((j) => {
    const rec     = isRecommended(j);
    const viewed  = _viewedIds.has(j.id);
    const applied = _appliedIds.has(j.id);
    const src     = (j.source||'').toLowerCase();
    const srcLbl  = SOURCE_LABELS[src] || src;
    const preview = j.description_preview || (j.description||'').slice(0,200);
    const idx     = _jobs.indexOf(j);

    return `
    <div class="job-card${rec?' recommended':''}${viewed?' viewed-card':''}" id="card-${idx}">
      <div class="job-header" onclick="toggleCard(${idx})">
        <div class="job-top-row">
          <div class="job-left">
            <div class="job-title-row">
              <span class="job-title">${esc(j.title||'Untitled')}</span>
              ${rec     ? `<span class="rec-badge">✨ Recommended</span>` : ''}
              ${applied ? `<span class="applied-badge">✅ Applied</span>` : ''}
            </div>
            <div class="job-meta">
              ${j.company  ? `<span class="company">${esc(j.company)}</span>`:''}
              ${j.location ? `<span>📍 ${esc(j.location)}</span>`:''}
              ${j.posted_at && j.posted_at!=='unknown' ? `<span>🗓 ${esc(j.posted_at)}</span>`:''}
              ${j.salary   ? `<span class="salary-pill">💰 ${esc(j.salary)}</span>`:''}
            </div>
          </div>
          <div class="job-badges">
            ${srcLbl ? `<span class="source-badge source-${src}">${esc(srcLbl)}</span>`:''}
            <span class="expand-icon">▾</span>
          </div>
        </div>
        ${preview ? `<div class="job-preview">${esc(preview)}</div>`:''}
        ${j.skills&&j.skills.length ? `
          <div class="skills-wrap">
            ${j.skills.slice(0,6).map(s=>`<span class="skill-tag">${esc(s)}</span>`).join('')}
            ${j.skills.length>6?`<span class="skill-tag">+${j.skills.length-6}</span>`:''}
          </div>`:''}
      </div>
      <div class="job-body">
        ${j.description ? `<div class="desc-label">Description</div><div class="desc-text">${esc(j.description)}</div>`:''}
        <div class="job-actions">
          ${j.url ? `<a class="btn-outline" href="${esc(j.url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">↗ Apply on ${esc(srcLbl||'site')}</a>`:''}
          <label class="applied-checkbox-label" onclick="event.stopPropagation()">
            <input type="checkbox" class="applied-checkbox" id="chk-${idx}"
              ${applied ? 'checked' : ''}
              onchange="onApplyCheckbox(event,${idx})">
            <span class="applied-check-text">${applied ? '✅ Applied' : 'Mark Applied'}</span>
          </label>
          <button class="btn-primary" onclick="openDrawer(${idx},'analyze');event.stopPropagation()">🔍 Analyze Resume</button>
        </div>
      </div>
    </div>`;
  }).join('');
}

function updateLoadMore(show) {
  const wrap = document.getElementById('jobsFooter');
  wrap.classList.toggle('hidden', !show);
}

// ── Toggle card ───────────────────────────────────────────────────────
