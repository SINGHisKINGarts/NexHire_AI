let _jobs         = [];
let _appliedJobs  = [];
let _viewedIds    = new Set();
let _appliedIds   = new Set();
let _resumeSkills = [];
let _activeJobIdx   = -1;
let _activeJobDesc  = '';
let _activeJobTitle = '';
let _drawerMin      = false;
let _analysisRunning = false;   // true while fetch is in-flight
let _activeRecruiter = null;    // currently selected recruiter for messaging
let _activeAnalysis  = {};      // last analysis result for message gen
let _activeResumeText = '';     // last extracted resume text
let _activeTone = 'professional';
let _searchPage = 1;
let _pageSize = 30;
let _hasMoreJobs = false;
let _lastSearch = { query:'', location:'', jobType:'' };
let _savedResumes = [];
let _selectedSavedResumeId = '';

// ── Boot ──────────────────────────────────────────────────────────────
