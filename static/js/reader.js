/**
 * 🌌 Manga Galactic — In-App Webtoon & Manga PDF Reader
 * Powered by Mozilla PDF.js (100% Client-Side Rendering — 0 Server Storage / RAM)
 */

// Initialize Telegram WebApp SDK
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  if (tg.disableVerticalSwipes) {
    try { tg.disableVerticalSwipes(); } catch (e) {}
  }
  if (tg.requestFullscreen) {
    try { tg.requestFullscreen(); } catch (e) {}
  }
  if (tg.setHeaderColor) tg.setHeaderColor('#000000');
  if (tg.setBackgroundColor) tg.setBackgroundColor('#000000');
}

// PDF.js worker setup
if (window.pdfjsLib) {
  window.pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}

// URL Params & User ID
const urlParams = new URLSearchParams(window.location.search);
const channelId = urlParams.get('cid') || urlParams.get('channel_id');
let currentChapter = parseInt(urlParams.get('ch') || urlParams.get('chapter')) || 1;
const currentUserId = tg?.initDataUnsafe?.user?.id || urlParams.get('user_id') || localStorage.getItem('galactic_user_id') || 6600689593;

// Reader State
let pdfDoc = null;
let totalPages = 0;
let currentPageNum = 1;
let currentMode = 'webtoon'; // 'webtoon' | 'page'
let mangaData = null;
let availableChapters = [1];
let renderedPages = new Set();
let isRenderingPage = false;
let lastScrollTop = 0;

// Width Presets for PC / Desktop
const WIDTH_PRESETS = ['normal', 'compact', 'wide', 'full'];
let currentWidthPreset = localStorage.getItem('galactic_reader_width') || 'normal';

// =========================================================
// 🚀 Initializer
// =========================================================
document.addEventListener('DOMContentLoaded', () => {
  if (!channelId) {
    showErrorState('Invalid manga ID provided.');
    return;
  }

  applyReaderWidth(currentWidthPreset);
  setupEventListeners();
  loadMangaChapterMeta();
});

function applyReaderWidth(preset) {
  currentWidthPreset = preset;
  document.body.setAttribute('data-reader-width', preset);
  localStorage.setItem('galactic_reader_width', preset);
}

function cycleReaderWidth() {
  const currentIdx = WIDTH_PRESETS.indexOf(currentWidthPreset);
  const nextPreset = WIDTH_PRESETS[(currentIdx + 1) % WIDTH_PRESETS.length];
  applyReaderWidth(nextPreset);

  const labels = {
    normal: 'Standard Width (740px)',
    compact: 'Compact Width (580px)',
    wide: 'Wide Reading (960px)',
    full: 'Full Screen (100%)'
  };
  showToast(`📐 ${labels[nextPreset] || nextPreset}`);

  if (currentMode === 'webtoon') {
    // Refresh visible canvas scaling
    renderedPages.clear();
    const wrappers = document.querySelectorAll('.webtoon-page-wrapper');
    wrappers.forEach(el => {
      const pNum = parseInt(el.getAttribute('data-page-num'));
      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight + 600 && rect.bottom > -600) {
        renderCanvasPage(pNum);
      }
    });
  }
}

// =========================================================
// ⚙️ Setup UI Event Listeners
// =========================================================
function setupEventListeners() {
  // Width Toggle for PC
  const btnWidthToggle = document.getElementById('btnWidthToggle');
  if (btnWidthToggle) {
    btnWidthToggle.addEventListener('click', cycleReaderWidth);
  }

  // Mode Switchers
  const btnWebtoon = document.getElementById('btnModeWebtoon');
  const btnPage = document.getElementById('btnModePage');

  btnWebtoon.addEventListener('click', () => setReaderMode('webtoon'));
  btnPage.addEventListener('click', () => setReaderMode('page'));

  // Chapter Dropdown Selector
  const chapterSelect = document.getElementById('chapterSelect');
  chapterSelect.addEventListener('change', (e) => {
    currentChapter = parseInt(e.target.value);
    loadChapterPdf();
  });

  // Chapter Prev / Next Buttons
  document.getElementById('btnPrevChapter').addEventListener('click', goToPrevChapter);
  document.getElementById('btnNextChapter').addEventListener('click', goToNextChapter);

  // Quick Bookmark Button
  document.getElementById('btnQuickBookmark').addEventListener('click', triggerManualBookmark);

  // Fullscreen Button
  document.getElementById('btnFullscreen').addEventListener('click', () => toggleImmersiveZenMode());

  // Page Flip Tap Zones
  document.getElementById('tapLeft').addEventListener('click', () => changeFlipPage(-1));
  document.getElementById('tapRight').addEventListener('click', () => changeFlipPage(1));

  // Tap & Double-Tap detection for 100% pure Manhwa Immersive Mode
  setupImmersiveTapHandlers();

  // Auto-hide toolbar on scroll
  window.addEventListener('scroll', handleToolbarScroll, { passive: true });

  // ⌨️ PC / Laptop Keyboard Shortcuts
  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key === 'ArrowRight' || e.key === 'd' || e.key === 'D') {
      if (currentMode === 'page') changeFlipPage(1);
      else goToNextChapter();
    } else if (e.key === 'ArrowLeft' || e.key === 'a' || e.key === 'A') {
      if (currentMode === 'page') changeFlipPage(-1);
      else goToPrevChapter();
    } else if (e.key === 'w' || e.key === 'W') {
      cycleReaderWidth();
    } else if (e.key === 'f' || e.key === 'F') {
      toggleImmersiveZenMode();
    } else if (e.key === 'b' || e.key === 'B') {
      triggerManualBookmark();
    } else if (e.key === 'm' || e.key === 'M') {
      setReaderMode(currentMode === 'webtoon' ? 'page' : 'webtoon');
    }
  });
}

// =========================================================
// 📚 Load Manga Chapter Metadata
// =========================================================
async function loadMangaChapterMeta() {
  try {
    const res = await fetch(`/api/chapters/${channelId}`);
    const data = await res.json();

    if (data.success) {
      mangaData = data;
      availableChapters = data.chapters || [1];

      document.getElementById('readerMangaTitle').textContent = data.name;
      document.title = `${data.name} — Ch. ${currentChapter} | Manga Galactic`;

      populateChapterDropdown();
      loadChapterPdf();
    } else {
      showErrorState(data.error || 'Failed to load manga chapters');
    }
  } catch (err) {
    console.error('Failed to load chapter metadata:', err);
    loadChapterPdf(); // Attempt direct load
  }
}

function populateChapterDropdown() {
  const select = document.getElementById('chapterSelect');
  select.innerHTML = availableChapters.map(ch =>
    `<option value="${ch}" ${ch === currentChapter ? 'selected' : ''}>Chapter ${ch}</option>`
  ).join('');
}

// =========================================================
// 📄 Stream & Render Chapter PDF (via PDF.js)
// =========================================================
async function loadChapterPdf() {
  showLoader(true, `Loading Chapter ${currentChapter}...`);
  renderedPages.clear();
  pdfDoc = null;

  const select = document.getElementById('chapterSelect');
  if (select) select.value = currentChapter;

  const pdfUrl = `/api/chapter/file/${channelId}/${currentChapter}`;

  try {
    const loadingTask = window.pdfjsLib.getDocument({
      url: pdfUrl,
      cMapUrl: 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/cmaps/',
      cMapPacked: true,
      rangeChunkSize: 131072, // 128KB HTTP Range chunk stream for 2x faster buffering!
      disableAutoFetch: false
    });

    loadingTask.onProgress = (progress) => {
      if (progress.total > 0) {
        const percent = Math.round((progress.loaded / progress.total) * 100);
        const bar = document.getElementById('loadProgress');
        const text = document.getElementById('loaderStatusText');
        if (bar) bar.style.width = `${percent}%`;
        if (text) text.textContent = `Streaming Chapter ${currentChapter} (${percent}%)...`;
      }
    };

    pdfDoc = await loadingTask.promise;
    totalPages = pdfDoc.numPages;
    showLoader(false);

    // Render based on current reading mode
    if (currentMode === 'webtoon') {
      renderWebtoonMode();
    } else {
      currentPageNum = 1;
      renderPageFlipMode();
    }

    // Auto-save read progress & pre-fetch next chapter in background!
    syncProgressBookmark();
    prefetchNextChapter();

    // Show and load social reactions & discussion
    const socialSec = document.getElementById('chapterSocialSection');
    if (socialSec) socialSec.style.display = 'flex';
    loadChapterReactions();
    loadChapterComments();

  } catch (err) {
    console.error('PDF load error:', err);
    const socialSec = document.getElementById('chapterSocialSection');
    if (socialSec) socialSec.style.display = 'none';
    try {
      const errRes = await fetch(pdfUrl);
      const errData = await errRes.json();
      showErrorState(errData.error || `Chapter ${currentChapter} is available in Telegram channel.`, errData.channel_link || mangaData?.channel_link);
    } catch (e) {
      showErrorState(`Chapter ${currentChapter} is available in Telegram channel.`, mangaData?.channel_link);
    }
  }
}

function prefetchNextChapter() {
  const idx = availableChapters.indexOf(currentChapter);
  if (idx !== -1 && idx < availableChapters.length - 1) {
    const nextChap = availableChapters[idx + 1];
    // Background cache warm on server
    fetch(`/api/chapter/file/${channelId}/${nextChap}`, { method: 'HEAD' }).catch(() => {});
  }
}

// =========================================================
// 📜 Webtoon Mode (Continuous Vertical Scroll)
// =========================================================
function renderWebtoonMode() {
  const container = document.getElementById('webtoonContainer');
  container.innerHTML = '';

  for (let i = 1; i <= totalPages; i++) {
    const pageWrapper = document.createElement('div');
    pageWrapper.className = 'webtoon-page-wrapper';
    pageWrapper.id = `page-wrap-${i}`;
    pageWrapper.setAttribute('data-page-num', i);

    // Initial placeholder with aspect ratio
    pageWrapper.style.minHeight = '300px';

    const canvas = document.createElement('canvas');
    canvas.className = 'webtoon-page-canvas';
    canvas.id = `canvas-page-${i}`;

    pageWrapper.appendChild(canvas);
    container.appendChild(pageWrapper);
  }

  // Setup Lazy Page Intersection Observer
  setupPageIntersectionObserver();
  updatePageIndicator(1);
}

function setupPageIntersectionObserver() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      const pageNum = parseInt(entry.target.getAttribute('data-page-num'));

      if (entry.isIntersecting) {
        // Update visible page indicator
        updatePageIndicator(pageNum);

        // Pre-render page canvas smoothly before scroll
        if (!renderedPages.has(pageNum)) {
          renderCanvasPage(pageNum);
        }
      }
    });
  }, {
    rootMargin: '1000px 0px 1000px 0px', // Pre-render 1000px ahead for instant buffer
    threshold: 0.01
  });

  document.querySelectorAll('.webtoon-page-wrapper').forEach(el => observer.observe(el));
}

async function renderCanvasPage(pageNum) {
  if (!pdfDoc || renderedPages.has(pageNum)) return;
  renderedPages.add(pageNum);

  try {
    const page = await pdfDoc.getPage(pageNum);
    const canvas = document.getElementById(`canvas-page-${pageNum}`);
    const wrapper = document.getElementById(`page-wrap-${pageNum}`);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const container = document.getElementById('webtoonContainer');

    // Bound viewport to container width on PC (prevents 4K stretching and slowness)
    const targetWidth = container ? Math.min(container.clientWidth || 740, 1000) : Math.min(window.innerWidth || 740, 740);
    const unscaledViewport = page.getViewport({ scale: 1 });

    // Set wrapper aspect-ratio to prevent layout shifts
    if (wrapper && unscaledViewport.width && unscaledViewport.height) {
      const aspectRatio = unscaledViewport.height / unscaledViewport.width;
      wrapper.style.minHeight = `${Math.round(targetWidth * aspectRatio)}px`;
    }

    // High performance DPR capped at 1.75 for 3x faster rendering with retina sharpness
    const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
    const scale = (targetWidth / unscaledViewport.width) * dpr;
    const viewport = page.getViewport({ scale: scale });

    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = '100%';
    canvas.style.height = 'auto';

    await page.render({
      canvasContext: ctx,
      viewport: viewport
    }).promise;

    // Reset placeholder minHeight once rendered
    if (wrapper) wrapper.style.minHeight = 'auto';

  } catch (err) {
    console.error(`Failed to render page ${pageNum}:`, err);
  }
}

// =========================================================
// 📖 Page Flip Mode
// =========================================================
async function renderPageFlipMode() {
  if (!pdfDoc || isRenderingPage) return;
  isRenderingPage = true;

  try {
    const page = await pdfDoc.getPage(currentPageNum);
    const canvas = document.getElementById('flipCanvas');
    const ctx = canvas.getContext('2d');

    const viewportHeight = window.innerHeight - 130;
    const viewportWidth = window.innerWidth - 20;
    const unscaledViewport = page.getViewport({ scale: 1 });

    const scaleX = viewportWidth / unscaledViewport.width;
    const scaleY = viewportHeight / unscaledViewport.height;
    const scale = Math.min(scaleX, scaleY) * (window.devicePixelRatio || 1);
    const viewport = page.getViewport({ scale: scale });

    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = `${viewport.width / (window.devicePixelRatio || 1)}px`;
    canvas.style.height = `${viewport.height / (window.devicePixelRatio || 1)}px`;

    await page.render({
      canvasContext: ctx,
      viewport: viewport
    }).promise;

    updatePageIndicator(currentPageNum);
  } catch (err) {
    console.error('Page Flip render error:', err);
  } finally {
    isRenderingPage = false;
  }
}

function changeFlipPage(delta) {
  const next = currentPageNum + delta;
  if (next >= 1 && next <= totalPages) {
    currentPageNum = next;
    renderPageFlipMode();
    hapticFeedback('selection');
  } else if (next > totalPages) {
    goToNextChapter();
  } else if (next < 1) {
    goToPrevChapter();
  }
}

// =========================================================
// 🔄 Mode Switcher
// =========================================================
function setReaderMode(mode) {
  currentMode = mode;
  document.getElementById('btnModeWebtoon').classList.toggle('active', mode === 'webtoon');
  document.getElementById('btnModePage').classList.toggle('active', mode === 'page');

  const webtoonView = document.getElementById('webtoonContainer');
  const pageView = document.getElementById('pageFlipContainer');

  if (mode === 'webtoon') {
    webtoonView.style.display = 'flex';
    pageView.style.display = 'none';
    if (pdfDoc) renderWebtoonMode();
  } else {
    webtoonView.style.display = 'none';
    pageView.style.display = 'flex';
    if (pdfDoc) renderPageFlipMode();
  }

  hapticFeedback('impact');
  showToast(mode === 'webtoon' ? '📜 Webtoon Vertical Mode' : '📖 Page-by-Page Flip Mode');
}

// =========================================================
// 🧭 Chapter Navigation
// =========================================================
function goToPrevChapter() {
  const idx = availableChapters.indexOf(currentChapter);
  if (idx > 0) {
    currentChapter = availableChapters[idx - 1];
    loadChapterPdf();
    hapticFeedback('impact');
  } else {
    showToast('Already at the first chapter');
  }
}

function goToNextChapter() {
  const idx = availableChapters.indexOf(currentChapter);
  if (idx !== -1 && idx < availableChapters.length - 1) {
    currentChapter = availableChapters[idx + 1];
    loadChapterPdf();
    hapticFeedback('impact');
  } else {
    showToast('You have reached the latest chapter! 🎉');
  }
}

// =========================================================
// 🔖 Bookmark & Auto-Progress Sync
// =========================================================
async function syncProgressBookmark() {
  if (!mangaData?.name || !currentChapter) return;

  try {
    await fetch('/api/bookmark', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUserId,
        manga_name: mangaData.name,
        chapter: currentChapter
      })
    });
  } catch (e) {}
}

async function triggerManualBookmark() {
  if (!mangaData?.name) return;

  hapticFeedback('notification');
  try {
    const res = await fetch('/api/bookmark', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUserId,
        manga_name: mangaData.name,
        chapter: currentChapter
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`🔖 Bookmarked Chapter ${currentChapter}!`);
    }
  } catch (err) {
    showToast('Failed to bookmark');
  }
}

// =========================================================
// 🔔 Helper Functions & UI
// =========================================================
function updatePageIndicator(page) {
  currentPageNum = page;
  const el = document.getElementById('pageIndicator');
  if (el) el.textContent = `Page ${page} / ${totalPages || 1}`;
}

function showLoader(show, text) {
  const loader = document.getElementById('readerLoader');
  const errorCard = document.getElementById('readerErrorState');
  if (loader) loader.style.display = show ? 'flex' : 'none';
  if (errorCard && show) errorCard.style.display = 'none';
  if (text) document.getElementById('loaderStatusText').textContent = text;
}

function showErrorState(msg, channelLink) {
  showLoader(false);
  const errorCard = document.getElementById('readerErrorState');
  const errorMsg = document.getElementById('readerErrorMsg');
  const linkBtn = document.getElementById('errorChannelLink');

  if (errorMsg) errorMsg.textContent = msg;
  if (linkBtn && channelLink) {
    linkBtn.href = channelLink;
    linkBtn.onclick = (e) => openTgLink(channelLink, e);
  }
  if (errorCard) errorCard.style.display = 'block';
}

function openTgLink(url, e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  if (!url) return;

  if (window.Telegram?.WebApp) {
    if (url.includes('t.me/') || url.startsWith('tg://')) {
      if (window.Telegram.WebApp.openTelegramLink) {
        window.Telegram.WebApp.openTelegramLink(url);
        return;
      }
    }
    if (window.Telegram.WebApp.openLink) {
      window.Telegram.WebApp.openLink(url);
      return;
    }
  }

  window.open(url, '_blank');
}

function handleToolbarScroll() {
  const st = window.pageYOffset || document.documentElement.scrollTop;
  const navbar = document.getElementById('readerNavbar');
  const footer = document.getElementById('readerFooter');

  if (st > lastScrollTop && st > 100) {
    navbar.classList.add('hidden');
    footer.classList.add('hidden');
  } else {
    navbar.classList.remove('hidden');
    footer.classList.remove('hidden');
  }
  lastScrollTop = st <= 0 ? 0 : st;
}

let isImmersiveMode = false;
let touchStartX = 0;
let touchStartY = 0;
let touchStartTime = 0;

function toggleImmersiveZenMode(forceState = null) {
  if (forceState !== null) {
    isImmersiveMode = forceState;
  } else {
    isImmersiveMode = !isImmersiveMode;
  }

  hapticFeedback('selection');

  const navbar = document.getElementById('readerNavbar');
  const footer = document.getElementById('readerFooter');
  const body = document.body;

  if (isImmersiveMode) {
    // 🌌 Enter True Immersive Zen Mode (Hide all bars & phone status bar)
    navbar?.classList.add('hidden');
    footer?.classList.add('hidden');
    body.classList.add('zen-immersive-mode');

    // 1. Telegram Fullscreen SDK (Hides Telegram close bar + Android status bar)
    if (window.Telegram?.WebApp?.requestFullscreen) {
      try {
        window.Telegram.WebApp.requestFullscreen();
      } catch (e) {}
    }

    // 2. HTML5 System Fullscreen (Hides Android navigation buttons)
    if (!document.fullscreenElement) {
      try {
        if (document.documentElement.requestFullscreen) {
          document.documentElement.requestFullscreen().catch(() => {});
        } else if (document.documentElement.webkitRequestFullscreen) {
          document.documentElement.webkitRequestFullscreen();
        }
      } catch (e) {}
    }

    showToast('🌌 Pure Manhwa Mode (Tap to show controls)');
  } else {
    // ☀️ Restore toolbars & Telegram controls
    navbar?.classList.remove('hidden');
    footer?.classList.remove('hidden');
    body.classList.remove('zen-immersive-mode');

    if (window.Telegram?.WebApp?.exitFullscreen && window.Telegram.WebApp.isFullscreen) {
      try {
        window.Telegram.WebApp.exitFullscreen();
      } catch (e) {}
    }

    if (document.fullscreenElement && document.exitFullscreen) {
      try {
        document.exitFullscreen().catch(() => {});
      } catch (e) {}
    }
  }
}

function setupImmersiveTapHandlers() {
  const viewport = document.getElementById('readerViewport');
  if (!viewport) return;

  // Touch handling on mobile: Detect clean tap vs scroll
  viewport.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
      touchStartTime = Date.now();
    }
  }, { passive: true });

  viewport.addEventListener('touchend', (e) => {
    // Ignore interactive UI components
    if (e.target.closest('button, input, select, textarea, .comment-card-item, .reaction-pill-btn, .modal-card, .social-box-header, .comment-input-wrap, a, .chapter-reactions-box, .chapter-comments-box')) {
      return;
    }

    if (e.changedTouches.length === 1) {
      const deltaX = Math.abs(e.changedTouches[0].clientX - touchStartX);
      const deltaY = Math.abs(e.changedTouches[0].clientY - touchStartY);
      const duration = Date.now() - touchStartTime;

      // Clean tap without significant drag/scroll
      if (deltaX < 14 && deltaY < 14 && duration < 320) {
        toggleImmersiveZenMode();
      }
    }
  });

  // Desktop click handler on canvas/viewport
  viewport.addEventListener('click', (e) => {
    if (e.target.closest('button, input, select, textarea, .comment-card-item, .reaction-pill-btn, .modal-card, .social-box-header, .comment-input-wrap, a, .chapter-reactions-box, .chapter-comments-box')) {
      return;
    }
    if (e.target.closest('.webtoon-page-wrapper, .webtoon-scroll-view, #pageFlipContainer, #flipCanvas')) {
      toggleImmersiveZenMode();
    }
  });
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2500);
}

function hapticFeedback(type = 'impact') {
  try {
    if (tg?.HapticFeedback) {
      if (type === 'impact') tg.HapticFeedback.impactOccurred('light');
      if (type === 'selection') tg.HapticFeedback.selectionChanged();
      if (type === 'notification') tg.HapticFeedback.notificationOccurred('success');
    }
  } catch (e) {}
}

// =========================================================
// 🔥 Chapter Reactions & 💬 Discussion Logic
// =========================================================
let currentChapterReactions = {
  fire: 0, heart: 0, crown: 0, shock: 0,
  laugh: 0, cry: 0, angry: 0, dislike: 0,
  total: 0, user_reaction: null
};
let currentCommentsList = [];
let activeEditingCommentId = null;

async function loadChapterReactions() {
  if (!channelId || !currentChapter) return;
  try {
    const res = await fetch(`/api/chapter/reactions?cid=${channelId}&ch=${currentChapter}&user_id=${currentUserId}`);
    const data = await res.json();
    if (data.success && data.reactions) {
      currentChapterReactions = data.reactions;
      renderReactionsUI();
    }
  } catch (err) {
    console.error('Failed to load reactions:', err);
  }
}

function renderReactionsUI() {
  const r = currentChapterReactions;
  const types = ['fire', 'heart', 'crown', 'shock', 'laugh', 'cry', 'angry', 'dislike'];

  types.forEach(type => {
    const capitalized = type.charAt(0).toUpperCase() + type.slice(1);
    const countEl = document.getElementById(`reactCount${capitalized}`);
    if (countEl) countEl.textContent = r[type] || 0;

    const btn = document.getElementById(`reactBtn_${type}`);
    if (btn) {
      if (r.user_reaction === type) {
        btn.classList.add('active-reaction');
      } else {
        btn.classList.remove('active-reaction');
      }
    }
  });

  const totalEl = document.getElementById('reactTotalCount');
  if (totalEl) totalEl.textContent = `${r.total || 0} Reactions`;
}

async function handleReaction(reactionType) {
  if (!channelId || !currentChapter) return;
  hapticFeedback('notification');

  const emojiMap = {
    fire: '🔥', heart: '❤️', crown: '👑', shock: '😱',
    laugh: '😂', cry: '😭', angry: '😡', dislike: '👎'
  };

  const btn = document.getElementById(`reactBtn_${reactionType}`);
  if (btn) {
    const rect = btn.getBoundingClientRect();
    showFloatingConfetti(emojiMap[reactionType] || '🔥', rect.left + rect.width / 2, rect.top);
  }

  // Optimistic UI update
  const prevUserReact = currentChapterReactions.user_reaction;
  if (prevUserReact === reactionType) {
    currentChapterReactions.user_reaction = null;
    currentChapterReactions[reactionType] = Math.max(0, (currentChapterReactions[reactionType] || 1) - 1);
    currentChapterReactions.total = Math.max(0, (currentChapterReactions.total || 1) - 1);
  } else {
    if (prevUserReact && currentChapterReactions[prevUserReact]) {
      currentChapterReactions[prevUserReact] = Math.max(0, currentChapterReactions[prevUserReact] - 1);
    } else {
      currentChapterReactions.total = (currentChapterReactions.total || 0) + 1;
    }
    currentChapterReactions.user_reaction = reactionType;
    currentChapterReactions[reactionType] = (currentChapterReactions[reactionType] || 0) + 1;
  }
  renderReactionsUI();

  try {
    const res = await fetch('/api/chapter/reaction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel_id: channelId,
        chapter: currentChapter,
        user_id: currentUserId,
        reaction: reactionType
      })
    });
    const data = await res.json();
    if (data.success && data.reactions) {
      currentChapterReactions = data.reactions;
      renderReactionsUI();
    }
  } catch (err) {
    console.error('Failed to toggle reaction:', err);
  }
}

function showFloatingConfetti(emoji, startX, startY) {
  for (let i = 0; i < 4; i++) {
    const el = document.createElement('div');
    el.className = 'floating-reaction-emoji';
    el.textContent = emoji;
    const randomOffsetX = (Math.random() - 0.5) * 60;
    const randomOffsetY = (Math.random() - 0.5) * 20;
    el.style.left = `${startX + randomOffsetX}px`;
    el.style.top = `${startY + randomOffsetY}px`;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1200);
  }
}

// -------------------------------------------------------------
// 💬 Chapter Comments Logic (Avatars, Edit & Delete)
// -------------------------------------------------------------
async function loadChapterComments() {
  if (!channelId || !currentChapter) return;
  const countEl = document.getElementById('commentsHeaderCount');
  const myPfp = document.getElementById('myCommentAvatar');

  if (myPfp) {
    myPfp.src = tg?.initDataUnsafe?.user?.photo_url || `/api/user/avatar/${currentUserId}`;
  }

  try {
    const res = await fetch(`/api/chapter/comments?cid=${channelId}&ch=${currentChapter}&user_id=${currentUserId}`);
    const data = await res.json();

    if (data.success) {
      currentCommentsList = data.comments || [];
      if (countEl) countEl.textContent = `(${data.count || 0})`;
      renderCommentsList(currentCommentsList);
    }
  } catch (err) {
    console.error('Failed to load comments:', err);
  }
}

function renderCommentsList(comments) {
  const feed = document.getElementById('commentsFeedList');
  if (!feed) return;

  if (!comments || comments.length === 0) {
    feed.innerHTML = `
      <div class="comments-empty-state" id="commentsEmptyState">
        <i class="fa-regular fa-comment-dots"></i>
        <p>No comments yet. Be the first to start the discussion!</p>
      </div>
    `;
    return;
  }

  feed.innerHTML = comments.map(c => {
    const isOwner = (c.user_id === currentUserId);
    const pfpUrl = c.user_avatar || `/api/user/avatar/${c.user_id}`;
    const editedTag = c.edited ? `<span class="comment-edited-tag">(edited)</span>` : '';

    return `
      <div class="comment-card-item" id="comment_${c.id}">
        <img src="${pfpUrl}" alt="${escapeHtml(c.user_name)}" class="comment-user-pfp" onerror="this.src='/static/images/default_cover.svg'">
        <div class="comment-content-col">
          <div class="comment-author-row">
            <span class="comment-author-name">
              ${escapeHtml(c.user_name)}
              ${editedTag}
            </span>
            <span class="comment-time-ago">${formatTimeAgo(c.created_at)}</span>
          </div>
          <div class="comment-body-text" id="commentText_${c.id}">${escapeHtml(c.text)}</div>
          <div class="comment-actions-bar">
            <div class="comment-author-actions">
              ${isOwner ? `
                <button class="btn-comment-action" onclick="openEditCommentModal('${c.id}')" title="Edit">
                  <i class="fa-solid fa-pen"></i> Edit
                </button>
                <button class="btn-comment-action btn-comment-delete" onclick="handleDeleteComment('${c.id}')" title="Delete">
                  <i class="fa-solid fa-trash-can"></i> Delete
                </button>
              ` : ''}
            </div>
            <button class="btn-comment-like ${c.is_liked ? 'active-like' : ''}" onclick="handleCommentLike('${c.id}')">
              <i class="fa-solid fa-thumbs-up"></i> <span id="likeCount_${c.id}">${c.likes_count || 0}</span>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

async function submitChapterComment() {
  const input = document.getElementById('commentTextInput');
  const submitBtn = document.getElementById('commentSubmitBtn');
  if (!input) return;

  const text = input.value.trim();
  if (!text) return;

  const userName = tg?.initDataUnsafe?.user?.first_name || localStorage.getItem('galactic_user_name') || 'Reader';
  const userAvatar = tg?.initDataUnsafe?.user?.photo_url || `/api/user/avatar/${currentUserId}`;

  if (submitBtn) submitBtn.disabled = true;
  hapticFeedback('impact');

  try {
    const res = await fetch('/api/chapter/comment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel_id: channelId,
        chapter: currentChapter,
        user_id: currentUserId,
        user_name: userName,
        user_avatar: userAvatar,
        text: text
      })
    });

    const data = await res.json();
    if (data.success) {
      input.value = '';
      showToast('💬 Comment posted!');
      loadChapterComments();
    } else {
      showToast(data.error || 'Failed to post comment');
    }
  } catch (err) {
    console.error('Failed to submit comment:', err);
    showToast('Failed to post comment');
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

// ✏️ Edit Comment Modal Handlers
function openEditCommentModal(commentId) {
  const comment = currentCommentsList.find(c => c.id === commentId);
  if (!comment) return;

  activeEditingCommentId = commentId;
  const input = document.getElementById('editCommentInput');
  if (input) input.value = comment.text || '';

  const modal = document.getElementById('editCommentModal');
  if (modal) modal.style.display = 'flex';
}

function closeEditCommentModal() {
  const modal = document.getElementById('editCommentModal');
  if (modal) modal.style.display = 'none';
  activeEditingCommentId = null;
}

async function saveEditedComment() {
  if (!activeEditingCommentId) return;

  const input = document.getElementById('editCommentInput');
  const saveBtn = document.getElementById('saveEditCommentBtn');
  const text = input?.value.trim();

  if (!text) {
    showToast('Comment cannot be empty');
    return;
  }

  if (saveBtn) saveBtn.disabled = true;
  hapticFeedback('impact');

  try {
    const res = await fetch('/api/chapter/comment/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        comment_id: activeEditingCommentId,
        user_id: currentUserId,
        text: text
      })
    });

    const data = await res.json();
    if (data.success) {
      showToast('✏️ Comment updated!');
      closeEditCommentModal();
      loadChapterComments();
    } else {
      showToast(data.error || 'Failed to update comment');
    }
  } catch (err) {
    console.error('Failed to edit comment:', err);
    showToast('Network error editing comment');
  } finally {
    if (saveBtn) saveBtn.disabled = false;
  }
}

// 🗑️ Delete Comment Handler
async function handleDeleteComment(commentId) {
  if (!confirm('Are you sure you want to delete this comment?')) return;
  hapticFeedback('impact');

  try {
    const res = await fetch('/api/chapter/comment/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        comment_id: commentId,
        user_id: currentUserId
      })
    });

    const data = await res.json();
    if (data.success) {
      showToast('🗑️ Comment deleted');
      loadChapterComments();
    } else {
      showToast(data.error || 'Failed to delete comment');
    }
  } catch (err) {
    console.error('Failed to delete comment:', err);
    showToast('Error deleting comment');
  }
}

async function handleCommentLike(commentId) {
  hapticFeedback('selection');
  try {
    const res = await fetch('/api/chapter/comment/like', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        comment_id: commentId,
        user_id: currentUserId
      })
    });

    const data = await res.json();
    if (data.success) {
      const countSpan = document.getElementById(`likeCount_${commentId}`);
      if (countSpan) countSpan.textContent = data.likes_count;
      const btn = countSpan?.closest('.btn-comment-like');
      if (btn) {
        if (data.is_liked) btn.classList.add('active-like');
        else btn.classList.remove('active-like');
      }
    }
  } catch (err) {
    console.error('Failed to like comment:', err);
  }
}

function formatTimeAgo(timestamp) {
  if (!timestamp) return 'recently';
  const sec = Math.floor(Date.now() / 1000 - timestamp);
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}


