/**
 * 🌌 Manga Galactic — In-App Webtoon & Manga PDF Reader
 * Powered by Mozilla PDF.js (100% Client-Side Rendering — 0 Server Storage / RAM)
 */

// Initialize Telegram WebApp SDK
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
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
const channelId = urlParams.get('cid');
let currentChapter = parseInt(urlParams.get('ch')) || 1;
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

// =========================================================
// 🚀 Initializer
// =========================================================
document.addEventListener('DOMContentLoaded', () => {
  if (!channelId) {
    showErrorState('Invalid manga ID provided.');
    return;
  }

  setupEventListeners();
  loadMangaChapterMeta();
});

// =========================================================
// ⚙️ Setup UI Event Listeners
// =========================================================
function setupEventListeners() {
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
  document.getElementById('btnFullscreen').addEventListener('click', toggleFullscreen);

  // Page Flip Tap Zones
  document.getElementById('tapLeft').addEventListener('click', () => changeFlipPage(-1));
  document.getElementById('tapRight').addEventListener('click', () => changeFlipPage(1));

  // Tap Webtoon Viewport to Toggle Toolbars (Immersive Mode)
  const webtoonView = document.getElementById('webtoonContainer');
  if (webtoonView) {
    webtoonView.addEventListener('click', () => {
      document.getElementById('readerNavbar')?.classList.toggle('hidden');
      document.getElementById('readerFooter')?.classList.toggle('hidden');
    });
  }

  // Auto-hide toolbar on scroll
  window.addEventListener('scroll', handleToolbarScroll, { passive: true });
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
  showLoader(true, `Streaming Chapter ${currentChapter} from Telegram CDN...`);
  renderedPages.clear();
  pdfDoc = null;

  // Update dropdown value
  const select = document.getElementById('chapterSelect');
  if (select) select.value = currentChapter;

  const pdfUrl = `/api/chapter/file/${channelId}/${currentChapter}`;

  try {
    // 1. Quick check response header
    const headRes = await fetch(pdfUrl, { method: 'HEAD' });
    const cType = headRes.headers.get('content-type') || '';

    if (!headRes.ok || !cType.includes('application/pdf')) {
      const errRes = await fetch(pdfUrl);
      const errData = await errRes.json().catch(() => ({}));
      showErrorState(
        errData.error || `Chapter ${currentChapter} is available in Telegram channel.`,
        errData.channel_link || mangaData?.channel_link
      );
      return;
    }

    // 2. Stream & Render with PDF.js
    const loadingTask = window.pdfjsLib.getDocument({
      url: pdfUrl,
      cMapUrl: 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/cmaps/',
      cMapPacked: true,
      rangeChunkSize: 65536 // 64KB HTTP Range chunk stream
    });

    loadingTask.onProgress = (progress) => {
      if (progress.total > 0) {
        const percent = Math.round((progress.loaded / progress.total) * 100);
        document.getElementById('loadProgress').style.width = `${percent}%`;
        document.getElementById('loaderStatusText').textContent = `Streaming Chapter ${currentChapter} (${percent}%)...`;
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

    // Auto-save read progress
    syncProgressBookmark();

  } catch (err) {
    console.error('PDF load error:', err);
    showErrorState(`Chapter ${currentChapter} is available in Telegram channel.`, mangaData?.channel_link);
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

        // Render page canvas if not already rendered
        if (!renderedPages.has(pageNum)) {
          renderCanvasPage(pageNum);
        }
      }
    });
  }, {
    rootMargin: '400px 0px 400px 0px', // Pre-render 400px before scrolling into view
    threshold: 0.1
  });

  document.querySelectorAll('.webtoon-page-wrapper').forEach(el => observer.observe(el));
}

async function renderCanvasPage(pageNum) {
  if (!pdfDoc || renderedPages.has(pageNum)) return;
  renderedPages.add(pageNum);

  try {
    const page = await pdfDoc.getPage(pageNum);
    const canvas = document.getElementById(`canvas-page-${pageNum}`);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 800;
    const unscaledViewport = page.getViewport({ scale: 1 });
    const dpr = Math.min(window.devicePixelRatio || 1, 2); // Crisp retina rendering
    const scale = (viewportWidth / unscaledViewport.width) * dpr;
    const viewport = page.getViewport({ scale: scale });

    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = '100%';
    canvas.style.height = 'auto';

    await page.render({
      canvasContext: ctx,
      viewport: viewport
    }).promise;

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

function toggleFullscreen() {
  if (window.Telegram?.WebApp?.requestFullscreen) {
    try {
      if (window.Telegram.WebApp.isFullscreen) {
        window.Telegram.WebApp.exitFullscreen();
      } else {
        window.Telegram.WebApp.requestFullscreen();
      }
    } catch (e) {}
  }

  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
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
