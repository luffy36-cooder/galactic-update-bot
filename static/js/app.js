/**
 * 🌌 Manga Galactic — Web Mini App Client Logic
 */

// Initialize Telegram WebApp SDK
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  // Set header color to match dark background
  if (tg.setHeaderColor) tg.setHeaderColor('#0b0c13');
  if (tg.setBackgroundColor) tg.setBackgroundColor('#0b0c13');
}

// Identify user from Telegram SDK, URL params, or fallback
const tgUser = tg?.initDataUnsafe?.user;
const urlParams = new URLSearchParams(window.location.search);
const currentUserId = tgUser?.id || urlParams.get('user_id') || localStorage.getItem('galactic_user_id') || 6600689593;

if (currentUserId) {
  localStorage.setItem('galactic_user_id', currentUserId);
}

// Global Catalog Data State
let catalogData = [];
let activeFilter = 'all';
let selectedBookmarkManga = null;

// =========================================================
// 🚀 Main Entry Point
// =========================================================
document.addEventListener('DOMContentLoaded', () => {
  if (document.body.classList.contains('profile-page')) {
    initProfilePage();
  } else {
    initCatalogPage();
  }
});

// =========================================================
// 📚 Catalog Page Logic (/web)
// =========================================================
function initCatalogPage() {
  const greetingEl = document.getElementById('userGreeting');
  if (greetingEl && tgUser) {
    greetingEl.textContent = `Hey ${tgUser.first_name || 'Reader'} 🚀`;
  }

  // Setup Search Input
  const searchInput = document.getElementById('searchInput');
  const clearBtn = document.getElementById('clearSearchBtn');

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      if (clearBtn) clearBtn.style.display = q ? 'block' : 'none';
      filterAndRenderCatalog();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      searchInput.value = '';
      clearBtn.style.display = 'none';
      filterAndRenderCatalog();
      searchInput.focus();
    });
  }

  // Setup Filter Pills
  document.querySelectorAll('.filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      activeFilter = pill.getAttribute('data-filter');
      hapticFeedback('selection');
      filterAndRenderCatalog();
    });
  });

  // Setup Bookmark Modal Save Button
  const bmSaveBtn = document.getElementById('bmSaveBtn');
  if (bmSaveBtn) {
    bmSaveBtn.addEventListener('click', submitBookmark);
  }

  // Fetch Catalog from API
  fetchCatalog();
}

async function fetchCatalog() {
  const countEl = document.getElementById('catalogCount');
  try {
    const res = await fetch(`/api/manga?user_id=${currentUserId}`);
    const data = await res.json();

    if (data.success) {
      catalogData = data.manga;
      if (countEl) countEl.textContent = `${catalogData.length} Titles Available`;
      filterAndRenderCatalog();
    } else {
      if (countEl) countEl.textContent = 'Failed to load catalog';
    }
  } catch (err) {
    console.error('Failed to fetch catalog:', err);
    if (countEl) countEl.textContent = 'Offline / Error loading';
  }
}

function filterAndRenderCatalog() {
  const grid = document.getElementById('mangaGrid');
  const emptyState = document.getElementById('emptyState');
  const searchInput = document.getElementById('searchInput');
  const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

  if (!grid) return;

  const filtered = catalogData.filter(item => {
    // 1. Search match
    const titleMatch = !query || item.name.toLowerCase().includes(query);
    if (!titleMatch) return false;

    // 2. Category filter match
    if (activeFilter === 'all') return true;
    if (activeFilter === 'bookmarked') return item.is_bookmarked;
    return item.status && item.status.includes(activeFilter);
  });

  if (filtered.length === 0) {
    grid.innerHTML = '';
    if (emptyState) emptyState.style.display = 'block';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';

  grid.innerHTML = filtered.map(item => createMangaCardHtml(item)).join('');
}

function createMangaCardHtml(item) {
  const isFav = item.status && item.status.includes('favorite');
  const isRead = item.status && item.status.includes('read');
  const isComp = item.status && item.status.includes('completed');
  const isBm = item.is_bookmarked;

  const chapCount = item.total_chapters ? `Ch. ${item.total_chapters}` : 'Ongoing';
  const bmBadge = isBm && item.bookmark_chapter ? `<span class="bookmark-tag">Ch. ${item.bookmark_chapter}</span>` : '';

  return `
    <div class="manga-card" data-cid="${item.channel_id}" data-name="${escapeHtml(item.name)}">
      <div class="poster-wrap">
        <img src="${item.image_url}" alt="${escapeHtml(item.name)}" loading="lazy" onerror="this.src='/static/images/default_cover.svg'">
        <span class="badge-chapters">${chapCount}</span>
        ${bmBadge}
      </div>
      <div class="card-details">
        <h4 class="manga-title" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</h4>
        <div class="card-actions">
          <a href="${item.channel_link}" target="_blank" class="btn-read-channel">
            <i class="fa-solid fa-book-open-reader"></i> Read Channel
          </a>
          <div class="status-actions-row">
            <button class="btn-icon-action ${isFav ? 'active-fav' : ''}" onclick="toggleStatus(${item.channel_id}, 'favorite', ${!isFav})" title="Favorite">
              <i class="${isFav ? 'fa-solid' : 'fa-regular'} fa-heart"></i>
            </button>
            <button class="btn-icon-action ${isRead ? 'active-read' : ''}" onclick="toggleStatus(${item.channel_id}, 'read', ${!isRead})" title="Mark Read">
              <i class="fa-solid fa-check"></i>
            </button>
            <button class="btn-icon-action ${isComp ? 'active-comp' : ''}" onclick="toggleStatus(${item.channel_id}, 'completed', ${!isComp})" title="Completed">
              <i class="fa-solid fa-flag-checkered"></i>
            </button>
            <button class="btn-icon-action ${isBm ? 'active-bm' : ''}" onclick="openBookmarkModal('${escapeHtml(item.name)}', ${item.bookmark_chapter || ''})" title="Bookmark">
              <i class="${isBm ? 'fa-solid' : 'fa-regular'} fa-bookmark"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

// =========================================================
// 🔄 Toggle Status Action
// =========================================================
async function toggleStatus(channelId, statusKey, add) {
  hapticFeedback('impact');

  // Optimistic UI Update
  const manga = catalogData.find(m => m.channel_id === channelId);
  if (manga) {
    if (!manga.status) manga.status = [];
    if (add) {
      if (!manga.status.includes(statusKey)) manga.status.push(statusKey);
    } else {
      manga.status = manga.status.filter(s => s !== statusKey);
    }
    filterAndRenderCatalog();
  }

  try {
    const res = await fetch('/api/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUserId,
        channel_id: channelId,
        status: statusKey,
        add: add
      })
    });

    const data = await res.json();
    if (data.success) {
      showToast(add ? `Added to ${statusKey}` : `Removed from ${statusKey}`);
    }
  } catch (err) {
    console.error('Failed to update status:', err);
    showToast('Failed to sync with server');
  }
}

// =========================================================
// 🔖 Bookmark Modal & Submission
// =========================================================
function openBookmarkModal(mangaName, currentChap) {
  selectedBookmarkManga = mangaName;
  const modal = document.getElementById('bookmarkModal');
  const titleEl = document.getElementById('bmModalTitle');
  const inputEl = document.getElementById('bmChapterInput');

  if (titleEl) titleEl.textContent = mangaName;
  if (inputEl) {
    inputEl.value = currentChap || '';
    setTimeout(() => inputEl.focus(), 150);
  }
  if (modal) modal.style.display = 'flex';
}

function closeBookmarkModal() {
  const modal = document.getElementById('bookmarkModal');
  if (modal) modal.style.display = 'none';
  selectedBookmarkManga = null;
}

async function submitBookmark() {
  const inputEl = document.getElementById('bmChapterInput');
  const chap = inputEl ? parseInt(inputEl.value) : null;

  if (!selectedBookmarkManga || !chap || chap < 1) {
    showToast('Please enter a valid chapter number');
    return;
  }

  try {
    const res = await fetch('/api/bookmark', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUserId,
        manga_name: selectedBookmarkManga,
        chapter: chap
      })
    });

    const data = await res.json();
    if (data.success) {
      // Update local state
      const m = catalogData.find(x => x.name.toLowerCase() === selectedBookmarkManga.toLowerCase());
      if (m) {
        m.is_bookmarked = true;
        m.bookmark_chapter = chap;
      }
      closeBookmarkModal();
      filterAndRenderCatalog();
      showToast(`Bookmarked Chapter ${chap} ✅`);
      hapticFeedback('notification');
    }
  } catch (err) {
    console.error('Failed to save bookmark:', err);
    showToast('Failed to save bookmark');
  }
}

// =========================================================
// 👤 Profile Page Logic (/webprofile)
// =========================================================
let profileShelves = {};
let activeShelf = 'read';

async function initProfilePage() {
  const nameEl = document.getElementById('profileName');
  const usernameEl = document.getElementById('profileUsername');
  const avatarEl = document.getElementById('profileAvatar');

  if (tgUser) {
    if (nameEl) nameEl.textContent = `${tgUser.first_name || ''} ${tgUser.last_name || ''}`.trim() || 'Reader';
    if (usernameEl) usernameEl.textContent = tgUser.username ? `@${tgUser.username}` : `ID: ${tgUser.id}`;
    if (avatarEl && tgUser.photo_url) avatarEl.src = tgUser.photo_url;
  }

  // Setup Shelf Tabs
  document.querySelectorAll('.shelf-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.shelf-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeShelf = tab.getAttribute('data-shelf');
      hapticFeedback('selection');
      renderActiveShelf();
    });
  });

  // Fetch Profile API
  try {
    const res = await fetch(`/api/profile?user_id=${currentUserId}`);
    const data = await res.json();

    if (data.success) {
      const p = data.profile;
      document.getElementById('statRead').textContent = p.read_count;
      document.getElementById('statBookmarks').textContent = p.bookmarks_count;
      document.getElementById('statFavorites').textContent = p.favorites_count;
      document.getElementById('statCompleted').textContent = p.completed_count;
      document.getElementById('profileRankText').textContent = p.rank;

      const badgesEl = document.getElementById('profileBadges');
      if (badgesEl && p.badges) {
        badgesEl.textContent = p.badges.join(' ');
      }

      profileShelves = p.shelves || {};
      renderActiveShelf();
    }
  } catch (err) {
    console.error('Failed to load profile:', err);
  }
}

function renderActiveShelf() {
  const grid = document.getElementById('shelfGrid');
  if (!grid) return;

  const items = profileShelves[activeShelf] || [];

  if (items.length === 0) {
    grid.innerHTML = `<div class="empty-shelf">No manga in your <b>${activeShelf}</b> shelf yet.</div>`;
    return;
  }

  grid.innerHTML = items.map(m => `
    <div class="manga-card">
      <div class="poster-wrap">
        <img src="${m.image_url}" alt="${escapeHtml(m.name)}" onerror="this.src='/static/images/default_cover.svg'">
      </div>
      <div class="card-details">
        <h4 class="manga-title">${escapeHtml(m.name)}</h4>
        <div class="card-actions">
          <a href="${m.channel_link}" target="_blank" class="btn-read-channel">
            <i class="fa-solid fa-book-open"></i> Read
          </a>
          <button class="btn-icon-action" style="width:100%;" onclick="removeShelfItem(${m.channel_id}, '${activeShelf}')">
            <i class="fa-solid fa-trash-can"></i> Remove
          </button>
        </div>
      </div>
    </div>
  `).join('');
}

async function removeShelfItem(channelId, shelfKey) {
  hapticFeedback('impact');
  profileShelves[shelfKey] = (profileShelves[shelfKey] || []).filter(m => m.channel_id !== channelId);
  renderActiveShelf();

  try {
    await fetch('/api/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUserId,
        channel_id: channelId,
        status: shelfKey,
        add: false
      })
    });
    showToast(`Removed from ${shelfKey}`);
  } catch (err) {
    console.error('Failed to remove shelf item:', err);
  }
}

// =========================================================
// 🔔 Helper Utilities
// =========================================================
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

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
