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

/* ================= INVITE LINKS ================= */

// Any .js-copy-invite button with data-room-code copies a join link for that room
document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.js-copy-invite');
    if (!btn) return;
    e.preventDefault();

    const url = `${location.origin}/party/join/?code=${encodeURIComponent(btn.dataset.roomCode)}`;
    let copied = false;
    try {
        await navigator.clipboard.writeText(url);
        copied = true;
    } catch (err) {
        window.prompt('Copy this invite link:', url);
    }

    const label = btn.querySelector('span') || btn;
    const original = label.textContent;
    label.textContent = copied ? 'Link copied!' : original;
    setTimeout(() => { label.textContent = original; }, 2000);
});

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

        // Builds the same markup as templates/partials/media_card.html
        function appendItems(container, items) {
            const csrfTokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
            const csrfToken = csrfTokenInput ? csrfTokenInput.value : '';
            const has = (v) => v && v !== 'N/A';

            items.forEach(item => {
                const id = escapeHtml(item.imdbID);
                const title = escapeHtml(item.Title);
                const year = has(item.Year) ? escapeHtml(item.Year) : '';
                const poster = has(item.Poster) ? escapeHtml(item.Poster) : WATCHIT.posterPlaceholder;
                const type = item.Type === 'series' ? 'Series' : item.Type === 'movie' ? 'Movie' : '';

                const card = document.createElement('article');
                card.className = 'mcard';
                card.innerHTML = `
                    <a href="/watch/${id}/" class="mcard-poster" aria-label="${title}">
                        <img src="${poster}" alt="" loading="lazy"
                             onerror="this.onerror=null; this.src='${WATCHIT.posterPlaceholder}'">
                        ${has(item.imdbRating) ? `<span class="mcard-rating"><i class="fas fa-star"></i>${escapeHtml(item.imdbRating)}</span>` : ''}
                        <span class="mcard-play" aria-hidden="true"><i class="fas fa-play"></i></span>
                    </a>
                    <div class="mcard-actions">
                        <button type="button" class="mcard-icon no-loading js-open-party" title="Start a watch party"
                                aria-label="Start a watch party for ${title}">
                            <i class="fas fa-users"></i>
                        </button>
                        ${WATCHIT.authenticated ? `
                        <form method="POST" action="${WATCHIT.addToWatchlistUrl}" class="no-loading">
                            <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}">
                            <input type="hidden" name="imdb_id" value="${id}">
                            <input type="hidden" name="title" value="${title}">
                            <input type="hidden" name="year" value="${year}">
                            <input type="hidden" name="poster" value="${has(item.Poster) ? escapeHtml(item.Poster) : ''}">
                            <button type="submit" class="mcard-icon" title="Add to My List" aria-label="Add ${title} to My List">
                                <i class="fas fa-plus"></i>
                            </button>
                        </form>` : ''}
                    </div>
                    <div class="mcard-info">
                        <h3 class="mcard-title" title="${title}">${title}</h3>
                        <div class="mcard-meta">${year ? `<span>${year}</span>` : ''}${type ? `<span>${type}</span>` : ''}</div>
                    </div>
                `;
                card.querySelector('.js-open-party').addEventListener('click', () => openPrivacyModal(item.imdbID));
                container.appendChild(card);
            });
        }
    });
});

/* ================= FEATURED HERO ================= */

// Auto-advances every SLIDE_MS. A JS timer drives it (so it also runs for
// reduced-motion users); the tab progress bar is a CSS animation kept in sync.
// It only stops for the pause button or while the browser tab is hidden.
(function () {
    const hero = document.getElementById('featureHero');
    if (!hero) return;

    const SLIDE_MS = 7000;
    const slides = [...hero.querySelectorAll('.fh-slide')];
    const tabs = [...hero.querySelectorAll('.fh-tab')];
    const toggle = hero.querySelector('.fh-toggle');
    let current = Math.max(0, slides.findIndex(s => s.classList.contains('is-active')));
    let timer = null;
    let startedAt = 0;
    let remaining = SLIDE_MS;
    let userPaused = false;

    hero.style.setProperty('--fh-duration', `${SLIDE_MS}ms`);
    if (slides.length < 2) {
        hero.querySelector('.fh-controls')?.remove();
        return;
    }

    function startTimer(ms) {
        clearTimeout(timer);
        startedAt = Date.now();
        remaining = ms;
        timer = setTimeout(() => show(current + 1), ms);
    }

    function stopTimer() {
        if (timer === null) return;
        clearTimeout(timer);
        timer = null;
        remaining = Math.max(0, remaining - (Date.now() - startedAt));
    }

    function running() {
        return !userPaused && !document.hidden;
    }

    function show(index) {
        clearTimeout(timer);  // a manual change replaces the pending auto-advance
        current = (index + slides.length) % slides.length;
        slides.forEach((slide, i) => {
            slide.classList.toggle('is-active', i === current);
            slide.setAttribute('aria-hidden', i === current ? 'false' : 'true');
        });
        tabs.forEach((tab, i) => {
            tab.classList.toggle('is-active', i === current);
            tab.setAttribute('aria-selected', i === current ? 'true' : 'false');
        });
        timer = null;
        remaining = SLIDE_MS;
        if (running()) startTimer(SLIDE_MS);
    }

    function setPaused(paused) {
        userPaused = paused;
        hero.classList.toggle('is-paused', paused);
        toggle.innerHTML = `<i class="fas fa-${paused ? 'play' : 'pause'}"></i>`;
        const label = paused ? 'Play slideshow' : 'Pause slideshow';
        toggle.setAttribute('aria-label', label);
        toggle.title = label;
        if (paused) stopTimer();
        else if (!document.hidden) startTimer(remaining);
    }

    tabs.forEach((tab, i) => tab.addEventListener('click', () => show(i)));
    toggle.addEventListener('click', () => setPaused(!userPaused));

    // Arrow keys move between tabs
    hero.querySelector('.fh-tabs').addEventListener('keydown', (e) => {
        if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
        e.preventDefault();
        show(current + (e.key === 'ArrowRight' ? 1 : -1));
        tabs[current].focus();
    });

    // Don't advance while the browser tab is in the background
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopTimer();
            hero.classList.add('is-paused');
        } else if (!userPaused) {
            hero.classList.remove('is-paused');
            startTimer(remaining);
        }
    });

    // Swipe on touch screens
    let touchX = null;
    hero.addEventListener('touchstart', (e) => { touchX = e.touches[0].clientX; }, { passive: true });
    hero.addEventListener('touchend', (e) => {
        if (touchX === null) return;
        const dx = e.changedTouches[0].clientX - touchX;
        touchX = null;
        if (Math.abs(dx) > 50) show(current + (dx < 0 ? 1 : -1));
    }, { passive: true });

    startTimer(SLIDE_MS);
})();

/* ================= ROW ARROWS ================= */

// Mouse users can't scroll horizontal rows without a trackpad, so add arrows
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll('.carousel-container').forEach(container => {
        const scroller = container.querySelector('.carousel-scroll');
        if (!scroller) return;

        const makeArrow = (dir) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = `row-arrow ${dir} no-loading`;
            btn.setAttribute('aria-label', dir === 'prev' ? 'Scroll left' : 'Scroll right');
            btn.innerHTML = `<i class="fas fa-chevron-${dir === 'prev' ? 'left' : 'right'}"></i>`;
            btn.addEventListener('click', () => {
                const step = scroller.clientWidth * 0.8;
                scroller.scrollBy({ left: dir === 'prev' ? -step : step, behavior: 'smooth' });
            });
            container.appendChild(btn);
            return btn;
        };
        const prev = makeArrow('prev');
        const next = makeArrow('next');

        const update = () => {
            prev.hidden = scroller.scrollLeft <= 5;
            next.hidden = scroller.scrollLeft + scroller.clientWidth >= scroller.scrollWidth - 5;
        };
        scroller.addEventListener('scroll', update, { passive: true });
        window.addEventListener('resize', update);
        new MutationObserver(update).observe(scroller, { childList: true });  // infinite scroll adds cards
        update();
    });
});

/* ================= TOUCH: TAP TO OPEN CARD ================= */

// On touch screens the poster buttons are hidden until the card is tapped once
if (window.matchMedia('(hover: none)').matches) {
    document.addEventListener('click', (e) => {
        const card = e.target.closest('.premium-card');
        document.querySelectorAll('.premium-card.touch-open').forEach(c => {
            if (c !== card) c.classList.remove('touch-open');
        });
        if (card && !card.classList.contains('touch-open')) {
            e.preventDefault();
            card.classList.add('touch-open');
        }
    }, true);
}

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
