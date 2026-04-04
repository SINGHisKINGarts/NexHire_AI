// App bootstrap
(async () => {
  await Promise.all([loadResume(), loadViewed(), loadApplied(), loadSavedResumes()]);
})();

document.getElementById('drawerOverlay').addEventListener('click', function(e) {
  if (e.target === this) closeDrawer();
});

const zone = document.getElementById('uploadZone');
zone.addEventListener('dragover',  () => zone.classList.add('dragover'));
zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
zone.addEventListener('drop',      () => zone.classList.remove('dragover'));

document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && document.activeElement.closest('.search-card')) searchJobs();
});
