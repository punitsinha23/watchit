// Shared behaviour for every page extending base.html.
// Page-specific values come from the #watchit-config JSON block in base.html.
const WATCHIT = JSON.parse(document.getElementById('watchit-config').textContent);

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
}

/* ================= PRIVACY MODAL ================= */

let currentImdbId = null;
function openPrivacyModal(imdbId) {
    currentImdbId = imdbId;
    const modal = new bootstrap.Modal(document.getElementById('privacyModal'));
    modal.show();
}

function selectPrivacy(isPrivate) {
    if (currentImdbId) {
        window.location.href = `/party/create/${encodeURIComponent(currentImdbId)}/?is_private=${isPrivate}`;
    }
}

/* ================= SEARCH ================= */

const searchIcon = document.querySelector(".search-icon");
const searchBox = document.querySelector(".search-box");

if (searchIcon) {
    searchIcon.addEventListener("click", () => {
        searchBox.classList.toggle("active");
        if (searchBox.classList.contains("active")) {
            document.querySelector(".search-input").focus();
        }
    });
}

/* ================= FREE TRIAL ================= */

// The server owns the trial clock (it also enforces it on the detail page),
// so the modal just reflects what /api/trial-status/ reports.
if (WATCHIT.trialEnabled) {
    let trialTimer = null;

    const showTrialModal = () => {
        const modal = document.getElementById('trialModal');
        if (modal) {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden'; // Prevent scrolling
        }
    };

    const checkTrialStatus = async () => {
        try {
            const res = await fetch(WATCHIT.trialStatusUrl, { credentials: 'same-origin' });
            const data = await res.json();
            if (data.unlimited) return;
            if (data.expired) {
                showTrialModal();
                return;
            }
            // Check again right when the trial runs out
            clearTimeout(trialTimer);
            trialTimer = setTimeout(checkTrialStatus, (data.remaining_seconds + 1) * 1000);
        } catch (e) {
            trialTimer = setTimeout(checkTrialStatus, 60000);
        }
    };

    checkTrialStatus();
}

/* ================= LAZY LOADING & CACHING ================= */

document.addEventListener("DOMContentLoaded", function () {
    const containers = document.querySelectorAll('.carousel-container');

    containers.forEach(container => {
        const scrollContainer = container.querySelector('.carousel-scroll');
        let isLoading = false;
        let hasNext = true;

        scrollContainer.addEventListener('scroll', () => {
            if (isLoading || !hasNext) return;

            // Check if scrolled near end (within 300px)
            if (scrollContainer.scrollLeft + scrollContainer.clientWidth >= scrollContainer.scrollWidth - 300) {
                loadMore(container);
            }
        }, { passive: true });

        async function loadMore(container) {
            if (isLoading || !hasNext) return;
            isLoading = true;
            startLoading(20);

            const category = container.getAttribute('data-category');
            let page = parseInt(container.getAttribute('data-page')) + 1;

            // Cache Key Strategy: watchit_cache_{category}_{page}
            const cacheKey = `watchit_cache_${category}_${page}`;
            const cachedData = getCachedData(cacheKey);

            if (cachedData) {
                appendItems(scrollContainer, cachedData);
                container.setAttribute('data-page', page);
                isLoading = false;
                finishLoading();
                return;
            }

            try {
                const response = await fetch(`/fetch-more/?category=${encodeURIComponent(category)}&page=${page}`);
                if (response.ok) {
                    const data = await response.json();
                    if (data.items.length > 0) {
                        appendItems(scrollContainer, data.items);
                        container.setAttribute('data-page', page);
                        setCachedData(cacheKey, data.items);
                        hasNext = data.has_next;
                    } else {
                        hasNext = false;
                    }
                } else {
                    console.error('Fetch error:', response.status);
                    hasNext = false;
                }
            } catch (error) {
                console.error('Network error:', error);
            } finally {
                isLoading = false;
                finishLoading();
            }
        }

        function appendItems(container, items) {
            const csrfTokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
            const csrfToken = csrfTokenInput ? csrfTokenInput.value : '';

            items.forEach(item => {
                const id = escapeHtml(item.imdbID);
                const title = escapeHtml(item.Title);
                const year = escapeHtml(item.Year);
                const poster = escapeHtml(item.Poster);

                const div = document.createElement('div');
                div.className = 'movie-unit fade-in visible';
                div.innerHTML = `
                    <div class="premium-card">
                        <img src="${poster}" alt="${title}" loading="lazy"
                             onerror="this.onerror=null; this.src='${WATCHIT.posterPlaceholder}'">
                        <div class="premium-overlay">
                            <a href="/watch/${id}/" class="premium-btn premium-btn-play">
                                <i class="fas fa-play me-2"></i>Play
                            </a>
                            <a href="javascript:void(0);" data-imdb-id="${id}" class="premium-btn premium-btn-play js-open-party"
                               style="background: linear-gradient(45deg, #ff00cc, #333399);">
                                <i class="fas fa-users me-2"></i>Party
                            </a>
                            <form method="POST" action="${WATCHIT.addToWatchlistUrl}" class="d-inline w-100 no-loading">
                                <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}">
                                <input type="hidden" name="imdb_id" value="${id}">
                                <input type="hidden" name="title" value="${title}">
                                <input type="hidden" name="year" value="${year}">
                                <input type="hidden" name="poster" value="${poster}">
                                <button type="submit" class="premium-btn premium-btn-list">
                                    <i class="fas fa-plus me-2"></i>My List
                                </button>
                            </form>
                        </div>
                    </div>
                    <div class="media-info text-center">
                        <div class="media-title">${title}</div>
                        <div class="media-meta">${year}</div>
                    </div>
                `;
                div.querySelector('.js-open-party').addEventListener('click', () => openPrivacyModal(item.imdbID));
                container.appendChild(div);
            });
        }
    });
});

// LocalStorage wrapper with expiry (storage can be unavailable, e.g. private mode)
function setCachedData(key, data) {
    try {
        localStorage.setItem(key, JSON.stringify({ value: data, expiry: Date.now() + 86400000 }));
    } catch (e) { /* ignore */ }
}

function getCachedData(key) {
    try {
        const item = JSON.parse(localStorage.getItem(key));
        if (!item) return null;
        if (Date.now() > item.expiry) {
            localStorage.removeItem(key);
            return null;
        }
        return item.value;
    } catch (e) {
        return null;
    }
}

/* ================= LOADING BAR ================= */

const bar = document.getElementById('loading-bar');
let loadingInterval;

window.startLoading = function (initialWidth = 10) {
    if (loadingInterval) clearInterval(loadingInterval);
    bar.style.opacity = '1';
    bar.style.width = initialWidth + '%';

    let currentWidth = initialWidth;
    loadingInterval = setInterval(() => {
        if (currentWidth < 90) {
            currentWidth += (90 - currentWidth) * 0.02;
        } else {
            currentWidth += 0.05;
        }
        bar.style.width = Math.min(currentWidth, 99) + '%';
    }, 100);
};

window.finishLoading = function () {
    if (loadingInterval) clearInterval(loadingInterval);
    bar.style.width = '100%';

    setTimeout(() => {
        bar.style.opacity = '0';
        setTimeout(() => {
            bar.style.width = '0%';
            bar.style.opacity = '1';
        }, 300);
    }, 100);
};

(function () {
    // Universal click listener for all links and buttons
    document.addEventListener('click', (e) => {
        const target = e.target.closest('a, button');
        if (!target) return;

        if (target.classList.contains('no-loading') || target.closest('.no-loading')) return;

        if (target.tagName === 'A') {
            const href = target.getAttribute('href');
            const isSamePage = href && (href.startsWith('#') || href.startsWith('javascript:'));
            const isNewTab = target.target === '_blank';

            if (href && !isSamePage && !isNewTab && !e.ctrlKey && !e.metaKey) {
                startLoading(15);
            }
        } else if (target.tagName === 'BUTTON') {
            if (target.type === 'submit' || target.closest('form')) {
                startLoading(20);
            }
        }
    });

    document.addEventListener('submit', (e) => {
        if (e.target.classList.contains('no-loading') || e.target.closest('.no-loading')) return;
        startLoading(25);
    });

    if (document.readyState === 'complete') {
        finishLoading();
    } else {
        window.addEventListener('load', finishLoading);
    }

    // Reset on back/forward cache restores
    window.addEventListener('pageshow', (event) => {
        if (event.persisted) {
            finishLoading();
        }
    });
})();
