/**
 * 🌌 Manga Galactic — Web Mini App Client Logic
 */

// Initialize Telegram WebApp SDK
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  if (tg.setHeaderColor) tg.setHeaderColor('#0b0c13');
  if (tg.setBackgroundColor) tg.setBackgroundColor('#0b0c13');
}

// Identify user from Telegram SDK, URL params, or fallback
const tgUser = tg?.initDataUnsafe?.user;
const urlParams = new URLSearchParams(window.location.search);
const currentUserId = tgUser?.id || urlParams.get('user_id') || localStorage.getItem('galactic_user_id') || 6600689593;
const currentUserName = tgUser ? `${tgUser.first_name || ''} ${tgUser.last_name || ''}`.trim() : 'Reader';

if (currentUserId) {
  localStorage.setItem('galactic_user_id', currentUserId);
}

// Global Catalog Data State
let catalogData = [];
let activeFilter = 'all';
let selectedBookmarkManga = null;
let selectedRatingChannelId = null;
let selectedRatingValue = 5;

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

  // Setup Rating Modal Stars
  document.querySelectorAll('.star-pick').forEach(star => {
    star.addEventListener('click', () => {
      const val = parseInt(star.getAttribute('data-val'));
      setRatingStars(val);
      hapticFeedback('selection');
    });
  });

  // Setup Rating Modal Submit Button
  const rateSubmitBtn = document.getElementById('rateSubmitBtn');
  if (rateSubmitBtn) {
    rateSubmitBtn.addEventListener('click', submitRating);
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

  let filtered = catalogData.filter(item => {
    // 1. Search match
    const titleMatch = !query || item.name.toLowerCase().includes(query);
    if (!titleMatch) return false;

    // 2. Category filter match
    if (activeFilter === 'all') return true;
    if (activeFilter === 'toprated') return item.total_ratings > 0;
    if (activeFilter === 'subscribed') return item.is_subscribed;
    if (activeFilter === 'bookmarked') return item.is_bookmarked;
    return item.status && item.status.includes(activeFilter);
  });

  if (activeFilter === 'toprated') {
    filtered.sort((a, b) => (b.avg_rating || 0) - (a.avg_rating || 0) || (b.total_ratings || 0) - (a.total_ratings || 0));
  }

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
  const isSub = item.is_subscribed;

  const chapCount = item.total_chapters ? `Ch. ${item.total_chapters}` : 'Ongoing';
  const bmBadge = isBm && item.bookmark_chapter ? `<span class="bookmark-tag">Ch. ${item.bookmark_chapter}</span>` : '';
  const ratingBadge = item.total_ratings > 0 
    ? `<span class="badge-rating"><i class="fa-solid fa-star"></i> ${item.avg_rating}</span>`
    : `<span class="badge-rating" style="color:#94a3b8;"><i class="fa-regular fa-star"></i> New</span>`;

  return `
    <div class="manga-card" data-cid="${item.channel_id}" data-name="${escapeHtml(item.name)}">
      <div class="poster-wrap">
        <img src="${item.image_url}" alt="${escapeHtml(item.name)}" loading="lazy" onerror="this.src='/static/images/default_cover.svg'">
        <span class="badge-chapters">${chapCount}</span>
        ${bmBadge}
        ${ratingBadge}
      </div>
      <div class="card-details">
        <h4 class="manga-title" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</h4>
        <div class="card-actions">
          <div class="btn-read-row">
            <a href="/reader?cid=${item.channel_id}&ch=${item.bookmark_chapter || 1}&user_id=${currentUserId}" class="btn-read-online">
              <i class="fa-solid fa-bolt"></i> Read Online
            </a>
            <button class="btn-read-channel" onclick="openTgLink('${item.channel_link}', event)" title="Open Telegram Channel">
              <i class="fa-brands fa-telegram"></i>
            </button>
          </div>
          <div class="status-actions-row">
            <button class="btn-icon-action ${isSub ? 'active-sub' : ''}" onclick="toggleSubscribe(${item.channel_id}, ${!isSub})" title="Auto Chapter Alert">
              <i class="${isSub ? 'fa-solid' : 'fa-regular'} fa-bell"></i>
            </button>
            <button class="btn-icon-action ${isFav ? 'active-fav' : ''}" onclick="toggleStatus(${item.channel_id}, 'favorite', ${!isFav})" title="Favorite">
              <i class="${isFav ? 'fa-solid' : 'fa-regular'} fa-heart"></i>
            </button>
            <button class="btn-icon-action ${isRead ? 'active-read' : ''}" onclick="toggleStatus(${item.channel_id}, 'read', ${!isRead})" title="Mark Read">
              <i class="fa-solid fa-check"></i>
            </button>
            <button class="btn-icon-action ${isBm ? 'active-bm' : ''}" onclick="openBookmarkModal('${escapeHtml(item.name)}', ${item.bookmark_chapter || ''})" title="Bookmark">
              <i class="${isBm ? 'fa-solid' : 'fa-regular'} fa-bookmark"></i>
            </button>
            <button class="btn-icon-action" onclick="openRateModal(${item.channel_id}, '${escapeHtml(item.name)}', ${item.user_rating || 5})" title="Rate Manga">
              <i class="fa-solid fa-star" style="color:#fbbf24;"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

// =========================================================
// 🔔 Toggle Subscription Action
// =========================================================
async function toggleSubscribe(channelId, subAction) {
  hapticFeedback('impact');

  const manga = catalogData.find(m => m.channel_id === channelId);
  if (manga) {
    manga.is_subscribed = subAction;
    filterAndRenderCatalog();
  }

  try {
    const res = await fetch('/api/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUserId,
        channel_id: channelId,
        subscribe: subAction
      })
    });

    const data = await res.json();
    if (data.success) {
      showToast(subAction ? '🔔 Subscribed to new chapter alerts!' : '🔕 Unsubscribed');
      hapticFeedback('notification');
    }
  } catch (err) {
    console.error('Failed to toggle subscription:', err);
    showToast('Failed to sync subscription');
  }
}

// =========================================================
// ⭐ 5-Star Rating & Review Modal
// =========================================================
function openRateModal(channelId, mangaName, existingRating = 5) {
  selectedRatingChannelId = channelId;
  const modal = document.getElementById('rateModal');
  const titleEl = document.getElementById('rateModalTitle');
  const reviewInput = document.getElementById('reviewTextInput');

  if (titleEl) titleEl.textContent = `Rate ${mangaName}`;
  if (reviewInput) reviewInput.value = '';

  setRatingStars(existingRating || 5);
  if (modal) modal.style.display = 'flex';
}

function closeRateModal() {
  const modal = document.getElementById('rateModal');
  if (modal) modal.style.display = 'none';
  selectedRatingChannelId = null;
}

function setRatingStars(val) {
  selectedRatingValue = val;
  const hintEl = document.getElementById('ratingScoreHint');
  if (hintEl) hintEl.textContent = `${val} / 5 Stars`;

  document.querySelectorAll('.star-pick').forEach(star => {
    const starVal = parseInt(star.getAttribute('data-val'));
    if (starVal <= val) {
      star.classList.add('active-star');
      star.innerHTML = '<i class="fa-solid fa-star"></i>';
    } else {
      star.classList.remove('active-star');
      star.innerHTML = '<i class="fa-regular fa-star"></i>';
    }
  });
}

async function submitRating() {
  if (!selectedRatingChannelId) return;

  const reviewInput = document.getElementById('reviewTextInput');
  const reviewText = reviewInput ? reviewInput.value.trim() : '';

  try {
    const res = await fetch('/api/rate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUserId,
        user_name: currentUserName,
        channel_id: selectedRatingChannelId,
        rating: selectedRatingValue,
        review: reviewText
      })
    });

    const data = await res.json();
    if (data.success) {
      // Update catalog entry
      const m = catalogData.find(x => x.channel_id === selectedRatingChannelId);
      if (m && data.summary) {
        m.avg_rating = data.summary.avg_rating;
        m.total_ratings = data.summary.total_ratings;
        m.user_rating = selectedRatingValue;
      }
      if (typeof profileShelves !== 'undefined') {
        Object.values(profileShelves).forEach(shelfList => {
          const item = shelfList.find(x => x.channel_id === selectedRatingChannelId);
          if (item) item.user_rating = selectedRatingValue;
        });
        renderActiveShelf();
      }
      closeRateModal();
      filterAndRenderCatalog();
      showToast(`⭐ Rated ${selectedRatingValue}/5 stars! Thank you!`);
      hapticFeedback('notification');
    }
  } catch (err) {
    console.error('Failed to submit rating:', err);
    showToast('Failed to submit rating');
  }
}

// =========================================================
// 🔄 Toggle Status Action
// =========================================================
async function toggleStatus(channelId, statusKey, add) {
  hapticFeedback('impact');

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
      const m = catalogData.find(x => x.name.toLowerCase() === selectedBookmarkManga.toLowerCase());
      if (m) {
        m.is_bookmarked = true;
        m.bookmark_chapter = chap;
      }
      if (typeof profileShelves !== 'undefined') {
        Object.values(profileShelves).forEach(shelfList => {
          const item = shelfList.find(x => x.name.toLowerCase() === selectedBookmarkManga.toLowerCase());
          if (item) {
            item.is_bookmarked = true;
            item.bookmark_chapter = chap;
          }
        });
        renderActiveShelf();
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
      const elRead = document.getElementById('statRead');
      const elBm = document.getElementById('statBookmarks');
      const elFav = document.getElementById('statFavorites');
      const elComp = document.getElementById('statCompleted');
      const elRank = document.getElementById('profileRankText');

      if (elRead) elRead.textContent = p.read_count || 0;
      if (elBm) elBm.textContent = p.bookmarks_count || 0;
      if (elFav) elFav.textContent = p.favorites_count || 0;
      if (elComp) elComp.textContent = p.completed_count || 0;
      if (elRank) elRank.textContent = p.rank || 'Reader';

      // Calculate Gamified Level & XP
      const readCount = p.read_count || 0;
      const level = Math.floor(readCount / 5) + 1;
      const xpCurrent = readCount % 5;
      const xpPercent = Math.round((xpCurrent / 5) * 100);

      const titles = ["Novice", "Apprentice", "Explorer", "Bookworm", "Manga Sage", "Grandmaster", "Galactic Sovereign"];
      const currentTitle = titles[Math.min(level - 1, titles.length - 1)];

      const levelEl = document.getElementById('profileLevelText');
      const xpTextEl = document.getElementById('profileXpText');
      const xpFillEl = document.getElementById('profileXpFill');

      if (levelEl) levelEl.textContent = `Level ${level} • ${currentTitle}`;
      if (xpTextEl) xpTextEl.textContent = `${xpCurrent} / 5 Chapters`;
      if (xpFillEl) xpFillEl.style.width = `${Math.max(12, xpPercent)}%`;

      const badgesEl = document.getElementById('profileBadges');
      if (badgesEl && p.badges) {
        badgesEl.textContent = p.badges.join(' ');
      }

      profileShelves = p.shelves || {};

      // Setup Bookmark and Rating Modals in Profile
      const bmSaveBtn = document.getElementById('bmSaveBtn');
      if (bmSaveBtn) bmSaveBtn.onclick = submitBookmark;

      const rateSubmitBtn = document.getElementById('rateSubmitBtn');
      if (rateSubmitBtn) rateSubmitBtn.onclick = submitRating;

      document.querySelectorAll('.star-pick').forEach(star => {
        star.onclick = () => {
          const val = parseInt(star.getAttribute('data-val'));
          setRatingStars(val);
          hapticFeedback('selection');
        };
      });

      // Populate Shelf Counters
      updateShelfTabCounters();
      renderActiveShelf();
    } else {
      const grid = document.getElementById('shelfGrid');
      if (grid) grid.innerHTML = `<div class="empty-shelf">Could not load profile data.</div>`;
    }
  } catch (err) {
    console.error('Failed to load profile:', err);
    const grid = document.getElementById('shelfGrid');
    if (grid) grid.innerHTML = `<div class="empty-shelf">Failed to load profile. Please check your connection.</div>`;
  }
}

function updateShelfTabCounters() {
  const readCount = (profileShelves.read || []).length;
  const favCount = (profileShelves.favorite || []).length;
  const compCount = (profileShelves.completed || []).length;
  const holdCount = (profileShelves.hold || []).length;
  const dropCount = (profileShelves.dropped || []).length;

  const elRead = document.getElementById('countRead');
  const elFav = document.getElementById('countFav');
  const elComp = document.getElementById('countComp');
  const elHold = document.getElementById('countHold');
  const elDrop = document.getElementById('countDrop');

  if (elRead) elRead.textContent = readCount;
  if (elFav) elFav.textContent = favCount;
  if (elComp) elComp.textContent = compCount;
  if (elHold) elHold.textContent = holdCount;
  if (elDrop) elDrop.textContent = dropCount;
}

function renderActiveShelf() {
  const grid = document.getElementById('shelfGrid');
  if (!grid) return;

  const items = profileShelves[activeShelf] || [];

  if (items.length === 0) {
    grid.innerHTML = `
      <div class="empty-shelf">
        <i class="fa-solid fa-book-open" style="font-size: 28px; margin-bottom: 8px; opacity: 0.6; display: block; color: var(--accent-purple);"></i>
        No manga in your <b>${activeShelf}</b> shelf yet.
        <br>
        <a href="/web" class="btn btn-primary" style="display: inline-block; margin-top: 14px; padding: 7px 16px; text-decoration: none;">
          <i class="fa-solid fa-compass"></i> Browse Manga Catalog
        </a>
      </div>
    `;
    return;
  }

  grid.innerHTML = items.map(m => {
    const chapCount = m.total_chapters ? `Ch. ${m.total_chapters}` : 'Ongoing';
    const isBm = Boolean(m.is_bookmarked);
    const isSub = Boolean(m.is_subscribed);
    const isFav = Boolean(m.is_favorite);
    const isRead = Boolean(m.is_read);
    const bmBadge = isBm && m.bookmark_chapter ? `<span class="bookmark-tag">Ch. ${m.bookmark_chapter}</span>` : '';
    const readChap = m.bookmark_chapter || 1;

    return `
      <div class="manga-card" data-cid="${m.channel_id}">
        <div class="poster-wrap">
          <img src="${m.image_url}" alt="${escapeHtml(m.name)}" loading="lazy" onerror="this.src='/static/images/default_cover.svg'">
          <span class="badge-chapters">${chapCount}</span>
          ${bmBadge}
        </div>
        <div class="card-details">
          <h4 class="manga-title" title="${escapeHtml(m.name)}">${escapeHtml(m.name)}</h4>
          <div class="card-actions">
            <div class="btn-read-row">
              <a href="/reader?cid=${m.channel_id}&ch=${readChap}&user_id=${currentUserId}" class="btn-read-online">
                <i class="fa-solid fa-bolt"></i> Read Online
              </a>
              <button class="btn-read-channel" onclick="openTgLink('${m.channel_link}', event)" title="Open Telegram Channel">
                <i class="fa-brands fa-telegram"></i>
              </button>
            </div>
            <div class="status-actions-row">
              <button class="btn-icon-action ${isSub ? 'active-sub' : ''}" onclick="toggleShelfSubscribe(${m.channel_id}, ${!isSub})" title="Auto Chapter Alert">
                <i class="${isSub ? 'fa-solid' : 'fa-regular'} fa-bell"></i>
              </button>
              <button class="btn-icon-action ${isFav ? 'active-fav' : ''}" onclick="toggleShelfStatus(${m.channel_id}, 'favorite', ${!isFav})" title="Favorite">
                <i class="${isFav ? 'fa-solid' : 'fa-regular'} fa-heart"></i>
              </button>
              <button class="btn-icon-action ${isRead ? 'active-read' : ''}" onclick="toggleShelfStatus(${m.channel_id}, 'read', ${!isRead})" title="Mark Read">
                <i class="fa-solid fa-check"></i>
              </button>
              <button class="btn-icon-action ${isBm ? 'active-bm' : ''}" onclick="openBookmarkModal('${escapeHtml(m.name)}', ${m.bookmark_chapter || ''})" title="Bookmark">
                <i class="${isBm ? 'fa-solid' : 'fa-regular'} fa-bookmark"></i>
              </button>
              <button class="btn-icon-action" onclick="openRateModal(${m.channel_id}, '${escapeHtml(m.name)}', ${m.user_rating || 5})" title="Rate Manga">
                <i class="fa-solid fa-star" style="color:#fbbf24;"></i>
              </button>
            </div>
            <button class="btn-icon-action" style="width:100%; margin-top:2px;" onclick="removeShelfItem(${m.channel_id}, '${activeShelf}')">
              <i class="fa-solid fa-trash-can"></i> Remove from Shelf
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

async function toggleShelfSubscribe(channelId, subAction) {
  hapticFeedback('impact');
  // Update all occurrences in all shelves
  Object.values(profileShelves).forEach(shelfList => {
    const item = shelfList.find(m => m.channel_id === channelId);
    if (item) item.is_subscribed = subAction;
  });
  renderActiveShelf();

  try {
    const res = await fetch('/api/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUserId,
        channel_id: channelId,
        subscribe: subAction
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(subAction ? '🔔 Subscribed to new chapter alerts!' : '🔕 Unsubscribed');
      hapticFeedback('notification');
    }
  } catch (err) {
    console.error('Failed to toggle subscription in profile:', err);
    showToast('Failed to sync subscription');
  }
}

async function toggleShelfStatus(channelId, statusKey, add) {
  hapticFeedback('impact');

  // Update in profile state
  Object.values(profileShelves).forEach(shelfList => {
    const item = shelfList.find(m => m.channel_id === channelId);
    if (item) {
      if (statusKey === 'favorite') item.is_favorite = add;
      if (statusKey === 'read') item.is_read = add;
    }
  });

  renderActiveShelf();

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
    console.error('Failed to update shelf status:', err);
  }
}

async function removeShelfItem(channelId, shelfKey) {
  hapticFeedback('impact');
  profileShelves[shelfKey] = (profileShelves[shelfKey] || []).filter(m => m.channel_id !== channelId);
  updateShelfTabCounters();
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
// 🔔 Helper Utilities & Native Telegram Link Opener
// =========================================================
function openTgLink(url, e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  if (!url) return;

  hapticFeedback('selection');

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
