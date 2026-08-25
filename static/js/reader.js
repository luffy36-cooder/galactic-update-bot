/**
 * 🌌 Manga Galactic — Ultra-Fast In-App Webtoon & Manga Reader
 * Powered by Mozilla PDF.js (Optimized Client-Side Rendering + Zero-Latency Caching)
 */

// Initialize Telegram WebApp SDK
const tg = window.Telegram?.WebApp;
if (tg) {
  try {
    tg.ready();
    tg.expand();
    if (tg.disableVerticalSwipes) tg.disableVerticalSwipes();
    if (tg.requestFullscreen) tg.requestFullscreen();
    if (tg.setHeaderColor) tg.setHeaderColor('#000000');
    if (tg.setBackgroundColor) tg.setBackgroundColor('#000000');
  } catch (e) {}
}

// PDF.js worker setup
if (window.pdfjsLib) {
  window.pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}

// =========================================================
// ⚡ IndexedDB Local Chapter Cache for Instant 0ms Re-reads
// =========================================================
const ChapterCache = {
  dbPromise: null,
  getDB() {
    if (!this.dbPromise) {
      this.dbPromise = new Promise((resolve) => {
        try {
          if (!window.indexedDB) return resolve(null);
          const req = indexedDB.open('GalacticReaderDB_v2', 1);
          req.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains('chapters')) {
              db.createObjectStore('chapters');
            }
          };
          req.onsuccess = (e) => resolve(e.target.result);
          req.onerror = () => resolve(null);
        } catch (e) {
          resolve(null);
        }
      });
    }
    return this.dbPromise;
  },
  async get(key) {
    try {
      const db = await this.getDB();
      if (!db) return null;
      return new Promise((resolve) => {
        const tx = db.transaction('chapters', 'readonly');
        const store = tx.objectStore('chapters');
        const req = store.get(key);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => resolve(null);
      });
    } catch (e) {
      return null;
    }
  },
  async set(key, buffer) {
    try {
      const db = await this.getDB();
      if (!db) return;
      const tx = db.transaction('chapters', 'readwrite');
      const store = tx.objectStore('chapters');
      store.put(buffer, key);
    } catch (e) {}
  }
};

// URL Params & User ID
const urlParams = new URLSearchParams(window.location.search);
const channelId = urlParams.get('cid') || urlParams.get('channel_id');
let currentChapter = parseInt(urlParams.get('ch') || urlParams.get('chapter')) || 1;
const currentUserId = tg?.initDataUnsafe?.user?.id || urlParams.get('user_id') || localStorage.getItem('galactic_user_id') || 6600689593;

// Reader Global State
let pdfDoc = null;
let totalPages = 0;
let currentPageNum = 1;
let currentMode = 'webtoon'; // 'webtoon' | 'page'
let mangaData = null;
let availableChapters = [1];
let renderedPages = new Set();
let renderingPages = new Set();
let activeRenderTasks = new Map(); // pageNum -> RenderTask
let renderQueue = [];
let isProcessingQueue = false;
let isRenderingFlipPage = false;
let lastScrollTop = 0;
let pageHeights = new Map(); // pageNum -> height

// Width Presets for PC / Desktop
const WIDTH_PRESETS = ['normal', 'compact', 'wide', 'full'];
let currentWidthPreset = localStorage.getItem('galactic_reader_width') || 'normal';

// =========================================================
// 🚀 Initializer
// =========================================================
document.addEventListener('DOMContentLoaded', () => {
  if (!channelId) {
    showErrorState('Invalid manga channel ID provided.');
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

  if (currentMode === 'webtoon' && pdfDoc) {
    // Re-render visible pages for new width
    cancelAllActiveRenderTasks();
    renderedPages.clear();
    sweepVisiblePages();
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

  if (btnWebtoon) btnWebtoon.addEventListener('click', () => setReaderMode('webtoon'));
  if (btnPage) btnPage.addEventListener('click', () => setReaderMode('page'));

  // Chapter Dropdown Selector
  const chapterSelect = document.getElementById('chapterSelect');
  if (chapterSelect) {
    chapterSelect.addEventListener('change', (e) => {
      currentChapter = parseInt(e.target.value);
      loadChapterPdf();
    });
  }

  // Chapter Prev / Next Buttons
  const btnPrev = document.getElementById('btnPrevChapter');
  const btnNext = document.getElementById('btnNextChapter');
  if (btnPrev) btnPrev.addEventListener('click', goToPrevChapter);
  if (btnNext) btnNext.addEventListener('click', goToNextChapter);

  // Quick Bookmark Button
  const btnBm = document.getElementById('btnQuickBookmark');
  if (btnBm) btnBm.addEventListener('click', triggerManualBookmark);

  // Fullscreen Button
  const btnFs = document.getElementById('btnFullscreen');
  if (btnFs) btnFs.addEventListener('click', () => toggleImmersiveZenMode());

  // Page Flip Tap Zones
  const tapL = document.getElementById('tapLeft');
  const tapR = document.getElementById('tapRight');
  if (tapL) tapL.addEventListener('click', () => changeFlipPage(-1));
  if (tapR) tapR.addEventListener('click', () => changeFlipPage(1));

  // Tap detection for Immersive Zen Mode
  setupImmersiveTapHandlers();

  // Auto-hide toolbar on scroll
  window.addEventListener('scroll', handleToolbarScroll, { passive: true });

  // Handle window resize cleanly
  let resizeTimeout;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      if (pdfDoc && currentMode === 'webtoon') {
        renderedPages.clear();
        sweepVisiblePages();
      }
    }, 250);
  });

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
    } else if (e.key === 'l' || e.key === 'L') {
      toggleScreenLock();
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

      const titleEl = document.getElementById('readerMangaTitle');
      if (titleEl) titleEl.textContent = data.name;
      document.title = `${data.name} — Ch. ${currentChapter} | Manga Galactic`;

      populateChapterDropdown();
      loadChapterPdf();
    } else {
      showErrorState(data.error || 'Failed to load manga chapters');
    }
  } catch (err) {
    console.error('Failed to load chapter metadata:', err);
    loadChapterPdf();
  }
}

function populateChapterDropdown() {
  const select = document.getElementById('chapterSelect');
  if (!select) return;
  select.innerHTML = availableChapters.map(ch =>
    `<option value="${ch}" ${ch === currentChapter ? 'selected' : ''}>Chapter ${ch}</option>`
  ).join('');
}

// =========================================================
// 📄 Stream & Render Chapter PDF (High Speed + Zero Latency)
// =========================================================
function cancelAllActiveRenderTasks() {
  for (const [pNum, task] of activeRenderTasks.entries()) {
    try {
      if (task && typeof task.cancel === 'function') {
        task.cancel();
      }
    } catch (e) {}
  }
  activeRenderTasks.clear();
  renderingPages.clear();
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 MB';
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1)} MB`;
}

async function loadChapterPdf() {
  showLoader(true, `Loading Chapter ${currentChapter}...`, 'Connecting to stream...');
  cancelAllActiveRenderTasks();
  renderedPages.clear();
  renderingPages.clear();
  renderQueue = [];
  isProcessingQueue = false;

  if (pdfDoc) {
    try { pdfDoc.destroy(); } catch (e) {}
    pdfDoc = null;
  }

  const select = document.getElementById('chapterSelect');
  if (select) select.value = currentChapter;

  const cacheKey = `${channelId}_${currentChapter}`;
  const pdfUrl = `/api/chapter/file/${channelId}/${currentChapter}`;

  try {
    let pdfData = null;

    // 1. ⚡ Instant 0ms IndexedDB Local Cache Check
    const cachedBuffer = await ChapterCache.get(cacheKey);
    if (cachedBuffer && cachedBuffer.byteLength > 5000) {
      updateLoaderProgress(100, `Cached in Device • ${formatBytes(cachedBuffer.byteLength)}`);
      pdfData = new Uint8Array(cachedBuffer);
    } else {
      // 2. 🚀 High-Speed Progressive Stream with Real-Time Byte Counting
      const response = await fetch(pdfUrl);
      if (!response.ok) {
        let errData = {};
        try { errData = await response.json(); } catch (e) {}
        throw new Error(errData.error || `Server responded with HTTP ${response.status}`);
      }

      const contentLength = response.headers.get('content-length');
      const totalBytes = contentLength ? parseInt(contentLength, 10) : 0;
      let loadedBytes = 0;

      const reader = response.body.getReader();
      const chunks = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        loadedBytes += value.length;

        if (totalBytes > 0) {
          const percent = Math.min(Math.round((loadedBytes / totalBytes) * 100), 99);
          updateLoaderProgress(percent, `${percent}% • ${formatBytes(loadedBytes)} / ${formatBytes(totalBytes)}`);
        } else {
          updateLoaderProgress(50, `Streaming • ${formatBytes(loadedBytes)} downloaded`);
        }
      }

      // Combine chunks into single ArrayBuffer
      const fullBuffer = new Uint8Array(loadedBytes);
      let offset = 0;
      for (const chunk of chunks) {
        fullBuffer.set(chunk, offset);
        offset += chunk.length;
      }

      pdfData = fullBuffer;
      // Persist in background to IndexedDB for instant 0ms future reads!
      ChapterCache.set(cacheKey, fullBuffer.buffer);
    }

    showLoader(true, `Rendering Chapter ${currentChapter}...`, 'Parsing PDF structure...');
    updateLoaderProgress(100, 'Parsing pages...');

    pdfDoc = await window.pdfjsLib.getDocument({
      data: pdfData,
      cMapUrl: 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/cmaps/',
      cMapPacked: true,
      isEvalSupported: false,
      useSystemFonts: true
    }).promise;

    totalPages = pdfDoc.numPages;
    if (totalPages === 0) throw new Error('PDF document has 0 pages.');

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
      showErrorState(errData.error || `Chapter ${currentChapter} is available in the Telegram channel.`, errData.channel_link || mangaData?.channel_link);
    } catch (e) {
      showErrorState(`Chapter ${currentChapter} is available in the Telegram channel.`, mangaData?.channel_link);
    }
  }
}

function updateLoaderProgress(percent, subText) {
  const bar = document.getElementById('loadProgress');
  const sub = document.getElementById('loaderSubText');
  if (bar) bar.style.width = `${percent}%`;
  if (sub && subText) sub.textContent = subText;
}

function prefetchNextChapter() {
  const idx = availableChapters.indexOf(currentChapter);
  if (idx !== -1 && idx < availableChapters.length - 1) {
    const nextChap = availableChapters[idx + 1];
    const cacheKey = `${channelId}_${nextChap}`;

    ChapterCache.get(cacheKey).then(cached => {
      if (!cached) {
        fetch(`/api/chapter/file/${channelId}/${nextChap}`).then(async res => {
          if (res.ok) {
            const buf = await res.arrayBuffer();
            if (buf && buf.byteLength > 5000) {
              ChapterCache.set(cacheKey, buf);
            }
          }
        }).catch(() => {});
      }
    }).catch(() => {});
  }
}

// =========================================================
// 📜 Webtoon Mode (Continuous Vertical Scroll with Zero Blank Issues)
// =========================================================
let webtoonObserver = null;

function renderWebtoonMode() {
  const container = document.getElementById('webtoonContainer');
  if (!container) return;
  container.innerHTML = '';

  for (let i = 1; i <= totalPages; i++) {
    const pageWrapper = document.createElement('div');
    pageWrapper.className = 'webtoon-page-wrapper';
    pageWrapper.id = `page-wrap-${i}`;
    pageWrapper.setAttribute('data-page-num', i);

    // Initial placeholder height to prevent layout jumps
    pageWrapper.style.minHeight = pageHeights.get(i) ? `${pageHeights.get(i)}px` : '400px';

    // Page skeleton shimmer
    const skeleton = document.createElement('div');
    skeleton.className = 'page-skeleton-placeholder';
    skeleton.id = `skeleton-page-${i}`;
    skeleton.innerHTML = `<span>Page ${i}</span>`;

    const canvas = document.createElement('canvas');
    canvas.className = 'webtoon-page-canvas';
    canvas.id = `canvas-page-${i}`;

    pageWrapper.appendChild(skeleton);
    pageWrapper.appendChild(canvas);
    container.appendChild(pageWrapper);
  }

  // Setup Lazy Page Intersection Observer
  setupPageIntersectionObserver();
  updatePageIndicator(1);

  // Immediately render the first 3 pages
  queuePageRender(1);
  if (totalPages >= 2) queuePageRender(2);
  if (totalPages >= 3) queuePageRender(3);
}

function setupPageIntersectionObserver() {
  if (webtoonObserver) {
    webtoonObserver.disconnect();
  }

  webtoonObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      const pageNum = parseInt(entry.target.getAttribute('data-page-num'));

      if (entry.isIntersecting) {
        updatePageIndicator(pageNum);

        // Pre-render current page
        if (!renderedPages.has(pageNum)) {
          queuePageRender(pageNum);
        }

        // Aggressively pre-render upcoming pages
        for (let offset = 1; offset <= 3; offset++) {
          const nextP = pageNum + offset;
          if (nextP <= totalPages && !renderedPages.has(nextP)) {
            queuePageRender(nextP);
          }
        }
      }
    });
  }, {
    rootMargin: '1800px 0px 1800px 0px', // Buffer 1800px ahead
    threshold: 0.01
  });

  document.querySelectorAll('.webtoon-page-wrapper').forEach(el => webtoonObserver.observe(el));
}

function sweepVisiblePages() {
  const wrappers = document.querySelectorAll('.webtoon-page-wrapper');
  wrappers.forEach(el => {
    const pNum = parseInt(el.getAttribute('data-page-num'));
    if (!renderedPages.has(pNum) && !renderingPages.has(pNum)) {
      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight + 1600 && rect.bottom > -1600) {
        queuePageRender(pNum);
      }
    }
  });
}

function queuePageRender(pageNum) {
  if (!pdfDoc || renderedPages.has(pageNum) || renderingPages.has(pageNum) || renderQueue.includes(pageNum)) return;
  renderQueue.push(pageNum);
  processRenderQueue();
}

async function processRenderQueue() {
  if (isProcessingQueue || renderQueue.length === 0 || !pdfDoc) return;
  isProcessingQueue = true;

  while (renderQueue.length > 0) {
    const pageNum = renderQueue.shift();
    if (!renderedPages.has(pageNum) && !renderingPages.has(pageNum)) {
      await renderCanvasPage(pageNum);
    }
  }

  isProcessingQueue = false;
}

async function renderCanvasPage(pageNum) {
  if (!pdfDoc || renderedPages.has(pageNum) || renderingPages.has(pageNum)) return;
  renderingPages.add(pageNum);

  try {
    const page = await pdfDoc.getPage(pageNum);
    const canvas = document.getElementById(`canvas-page-${pageNum}`);
    const wrapper = document.getElementById(`page-wrap-${pageNum}`);
    const skeleton = document.getElementById(`skeleton-page-${pageNum}`);
    if (!canvas || !wrapper) {
      renderingPages.delete(pageNum);
      return;
    }

    const container = document.getElementById('webtoonContainer');
    const containerWidth = container ? container.clientWidth : 0;
    const targetWidth = Math.max(300, Math.min(containerWidth || window.innerWidth || 740, 1000));
    const unscaledViewport = page.getViewport({ scale: 1 });

    if (!unscaledViewport.width || !unscaledViewport.height) {
      renderingPages.delete(pageNum);
      return;
    }

    const aspectRatio = unscaledViewport.height / unscaledViewport.width;
    const computedHeight = Math.round(targetWidth * aspectRatio);
    pageHeights.set(pageNum, computedHeight);

    // Capped DPR (max 1.5) for optimal Retina sharpness, ultra-fast painting & low VRAM
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    const scale = (targetWidth / unscaledViewport.width) * dpr;
    const viewport = page.getViewport({ scale: scale });

    // Set canvas dimensions
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    canvas.style.width = '100%';
    canvas.style.height = 'auto';

    // Standard 2D context (without desynchronized to eliminate blank screen bug)
    const ctx = canvas.getContext('2d', { alpha: false });
    // Fill canvas background to prevent black/transparent holes
    ctx.fillStyle = '#11121d';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Cancel any previous render task on this page
    if (activeRenderTasks.has(pageNum)) {
      try { activeRenderTasks.get(pageNum).cancel(); } catch (e) {}
      activeRenderTasks.delete(pageNum);
    }

    const renderTask = page.render({
      canvasContext: ctx,
      viewport: viewport,
      intent: 'display'
    });

    activeRenderTasks.set(pageNum, renderTask);
    await renderTask.promise;

    activeRenderTasks.delete(pageNum);
    renderedPages.add(pageNum);
    renderingPages.delete(pageNum);

    // Fade out and remove skeleton placeholder
    if (skeleton) {
      skeleton.classList.add('fade-out');
      setTimeout(() => skeleton.remove(), 300);
    }

    // Lock wrapper height to match rendered height
    wrapper.style.minHeight = `${computedHeight}px`;

    // 🧹 Virtual Memory Windowing for long chapters (>30 pages)
    pruneOffscreenCanvases(pageNum);

  } catch (err) {
    activeRenderTasks.delete(pageNum);
    renderingPages.delete(pageNum);
    if (err.name !== 'RenderingCancelledException') {
      console.warn(`Render error on page ${pageNum}:`, err);
    }
  }
}

function pruneOffscreenCanvases(currentPage) {
  if (totalPages <= 30 || renderedPages.size <= 24) return;

  renderedPages.forEach(p => {
    if (Math.abs(p - currentPage) > 10) {
      const canvas = document.getElementById(`canvas-page-${p}`);
      const wrapper = document.getElementById(`page-wrap-${p}`);
      if (canvas && wrapper) {
        // Free GPU memory while maintaining scroll height
        canvas.width = 1;
        canvas.height = 1;
        renderedPages.delete(p);
      }
    }
  });
}

// =========================================================
// 📖 Page Flip Mode
// =========================================================
async function renderPageFlipMode() {
  if (!pdfDoc || isRenderingFlipPage) return;
  isRenderingFlipPage = true;

  try {
    const page = await pdfDoc.getPage(currentPageNum);
    const canvas = document.getElementById('flipCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d', { alpha: false });
    const viewportHeight = Math.max(300, window.innerHeight - 130);
    const viewportWidth = Math.max(300, window.innerWidth - 20);
    const unscaledViewport = page.getViewport({ scale: 1 });

    const scaleX = viewportWidth / unscaledViewport.width;
    const scaleY = viewportHeight / unscaledViewport.height;
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    const scale = Math.min(scaleX, scaleY) * dpr;
    const viewport = page.getViewport({ scale: scale });

    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    canvas.style.width = `${Math.floor(viewport.width / dpr)}px`;
    canvas.style.height = `${Math.floor(viewport.height / dpr)}px`;

    ctx.fillStyle = '#11121d';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    await page.render({
      canvasContext: ctx,
      viewport: viewport,
      intent: 'display'
    }).promise;

    updatePageIndicator(currentPageNum);
  } catch (err) {
    if (err.name !== 'RenderingCancelledException') {
      console.error('Page Flip render error:', err);
    }
  } finally {
    isRenderingFlipPage = false;
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
  cancelAllActiveRenderTasks();

  const btnWebtoon = document.getElementById('btnModeWebtoon');
  const btnPage = document.getElementById('btnModePage');
  if (btnWebtoon) btnWebtoon.classList.toggle('active', mode === 'webtoon');
  if (btnPage) btnPage.classList.toggle('active', mode === 'page');

  const webtoonView = document.getElementById('webtoonContainer');
  const pageView = document.getElementById('pageFlipContainer');

  if (mode === 'webtoon') {
    if (webtoonView) webtoonView.style.display = 'flex';
    if (pageView) pageView.style.display = 'none';
    if (pdfDoc) renderWebtoonMode();
  } else {
    if (webtoonView) webtoonView.style.display = 'none';
    if (pageView) pageView.style.display = 'flex';
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

function showLoader(show, text, subText) {
  const loader = document.getElementById('readerLoader');
  const errorCard = document.getElementById('readerErrorState');
  if (loader) loader.style.display = show ? 'flex' : 'none';
  if (errorCard && show) errorCard.style.display = 'none';
  if (text) {
    const t = document.getElementById('loaderStatusText');
    if (t) t.textContent = text;
  }
  if (subText) {
    const st = document.getElementById('loaderSubText');
    if (st) st.textContent = subText;
  }
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
    if (navbar) navbar.classList.add('hidden');
    if (footer) footer.classList.add('hidden');
  } else {
    if (navbar) navbar.classList.remove('hidden');
    if (footer) footer.classList.remove('hidden');
  }
  lastScrollTop = st <= 0 ? 0 : st;
}

let isImmersiveMode = false;
let isScreenLocked = false;
let touchStartX = 0;
let touchStartY = 0;
let touchStartTime = 0;
let lastTapTime = 0;
let lastTapX = 0;
let lastTapY = 0;
let lockBadgeTimeout = null;

function toggleScreenLock(forceState = null) {
  if (forceState !== null) {
    isScreenLocked = forceState;
  } else {
    isScreenLocked = !isScreenLocked;
  }

  hapticFeedback('impact');

  const body = document.body;
  const floatingBtn = document.getElementById('btnFloatingLock');
  const floatingIcon = document.getElementById('floatingLockIcon');

  if (isScreenLocked) {
    body.classList.add('reader-locked', 'zen-immersive-mode');
    if (floatingBtn) floatingBtn.classList.add('locked');
    if (floatingIcon) floatingIcon.className = 'fa-solid fa-lock';

    if (window.Telegram?.WebApp?.requestFullscreen) {
      try { window.Telegram.WebApp.requestFullscreen(); } catch (e) {}
    }

    showLockBadge('🔒 Screen Locked (Double-tap screen to unlock)');
  } else {
    body.classList.remove('reader-locked', 'zen-immersive-mode');
    if (floatingBtn) floatingBtn.classList.remove('locked');
    if (floatingIcon) floatingIcon.className = 'fa-solid fa-lock-open';

    showLockBadge('🔓 Screen Unlocked (Controls Active)');

    const navbar = document.getElementById('readerNavbar');
    const footer = document.getElementById('readerFooter');
    if (navbar) navbar.classList.remove('hidden');
    if (footer) footer.classList.remove('hidden');
  }
}

function showLockBadge(msg) {
  const badge = document.getElementById('screenLockBadge');
  if (!badge) return;
  const span = badge.querySelector('span');
  if (span) span.textContent = msg;
  badge.style.display = 'flex';
  clearTimeout(lockBadgeTimeout);
  lockBadgeTimeout = setTimeout(() => {
    badge.style.display = 'none';
  }, 2200);
}

function toggleImmersiveZenMode(forceState = null) {
  if (isScreenLocked) {
    showLockBadge('🔒 Screen is Locked • Double-tap to unlock');
    return;
  }

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
    navbar?.classList.add('hidden');
    footer?.classList.add('hidden');
    body.classList.add('zen-immersive-mode');

    if (window.Telegram?.WebApp?.requestFullscreen) {
      try { window.Telegram.WebApp.requestFullscreen(); } catch (e) {}
    }

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
    navbar?.classList.remove('hidden');
    footer?.classList.remove('hidden');
    body.classList.remove('zen-immersive-mode');

    if (window.Telegram?.WebApp?.exitFullscreen && window.Telegram.WebApp.isFullscreen) {
      try { window.Telegram.WebApp.exitFullscreen(); } catch (e) {}
    }

    if (document.fullscreenElement && document.exitFullscreen) {
      try { document.exitFullscreen().catch(() => {}); } catch (e) {}
    }
  }
}

function setupImmersiveTapHandlers() {
  const viewport = document.getElementById('readerViewport');
  const floatingBtn = document.getElementById('btnFloatingLock');

  if (floatingBtn) {
    floatingBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleScreenLock();
    });
  }

  if (!viewport) return;

  viewport.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
      touchStartTime = Date.now();
    }
  }, { passive: true });

  viewport.addEventListener('touchend', (e) => {
    if (e.target.closest('button, input, select, textarea, .comment-card-item, .reaction-pill-btn, .modal-card, .social-box-header, .comment-input-wrap, a, .chapter-reactions-box, .chapter-comments-box, .floating-lock-btn')) {
      return;
    }

    if (e.changedTouches.length === 1) {
      const curX = e.changedTouches[0].clientX;
      const curY = e.changedTouches[0].clientY;
      const deltaX = Math.abs(curX - touchStartX);
      const deltaY = Math.abs(curY - touchStartY);
      const duration = Date.now() - touchStartTime;
      const now = Date.now();

      // Clean tap without drag/scroll
      if (deltaX < 18 && deltaY < 18 && duration < 320) {
        const timeSinceLastTap = now - lastTapTime;
        const tapDistance = Math.hypot(curX - lastTapX, curY - lastTapY);

        if (timeSinceLastTap < 360 && tapDistance < 50) {
          // ⚡ DOUBLE-TAP DETECTED: Toggle Screen Lock!
          toggleScreenLock();
          lastTapTime = 0;
        } else {
          // 👆 SINGLE-TAP DETECTED
          lastTapTime = now;
          lastTapX = curX;
          lastTapY = curY;

          if (isScreenLocked) {
            showLockBadge('🔒 Screen is Locked • Double-tap to unlock');
            hapticFeedback('selection');
          } else {
            toggleImmersiveZenMode();
          }
        }
      }
    }
  });

  // Desktop double-click
  viewport.addEventListener('dblclick', (e) => {
    if (e.target.closest('button, input, select, textarea, .comment-card-item, .reaction-pill-btn, .modal-card, .social-box-header, .comment-input-wrap, a, .chapter-reactions-box, .chapter-comments-box, .floating-lock-btn')) {
      return;
    }
    toggleScreenLock();
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


