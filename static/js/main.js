/* ============================================================
   main.js  –  Virexa Dashboard
   Handles: theme toggle, Discord OAuth popup, UI updates,
            user dropdown, WebSocket log stream
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

    /* ── Theme toggle ──────────────────────────────────────────── */
    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
        const saved = localStorage.getItem('virexa-theme') || 'dark';
        applyTheme(saved);

        themeBtn.addEventListener('click', () => {
            const cur = document.documentElement.getAttribute('data-theme');
            applyTheme(cur === 'dark' ? 'light' : 'dark');
        });
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('virexa-theme', theme);

        const darkIcon = document.getElementById('theme-toggle-dark-icon');
        const lightIcon = document.getElementById('theme-toggle-light-icon');

        if (darkIcon && lightIcon) {
            if (theme === 'dark') {
                darkIcon.style.display = 'none';
                lightIcon.style.display = 'block';
            } else {
                darkIcon.style.display = 'block';
                lightIcon.style.display = 'none';
            }
        }
    }

    /* ── User dropdown toggle ──────────────────────────────────── */
    const profileBtn = document.getElementById('user-profile-btn');
    const dropdownMenu = document.getElementById('user-dropdown-content');
    if (profileBtn && dropdownMenu) {
        profileBtn.addEventListener('click', e => {
            e.stopPropagation();
            dropdownMenu.classList.toggle('show');
        });
        document.addEventListener('click', () => dropdownMenu.classList.remove('show'));
    }

    /* ── Discord OAuth Popup flow ──────────────────────────────── */
    const loginBtn = document.getElementById('discord-login-btn');
    if (loginBtn) {
        loginBtn.addEventListener('click', openDiscordPopup);
    }

    function openDiscordPopup() {
        // 1. Ask backend for the Discord OAuth URL (with CSRF state baked in)
        fetch('/auth/discord/url')
            .then(r => r.json())
            .then(data => {
                const W = 500, H = 700;
                const left = Math.round(window.screen.width / 2 - W / 2);
                const top = Math.round(window.screen.height / 2 - H / 2);

                // 2. Open the popup
                const popup = window.open(
                    data.url,
                    'virexa_discord_auth',
                    `width=${W},height=${H},top=${top},left=${left},resizable=yes,scrollbars=yes`
                );

                // 3. Detect if popup was blocked
                if (!popup || popup.closed || typeof popup.closed === 'undefined') {
                    const msg = document.getElementById('popup-blocked-msg');
                    if (msg) msg.style.display = 'block';
                    return;
                }
            })
            .catch(err => console.error('Failed to get Discord URL:', err));
    }

    /* ── Listen for postMessage from popup ─────────────────────── */
    window.addEventListener('message', event => {
        // Security: only accept messages from same origin
        if (event.origin !== window.location.origin) return;
        if (!event.data || event.data.type !== 'VIREXA_AUTH_SUCCESS') return;

        // The cookie is already set by the server's Set-Cookie header.
        // Just redirect — the server will recognize the session.
        window.location.href = '/select_server';
    });

    /* ── Update navbar after popup login ──────────────────────── */
    function updateNavbar(user) {
        if (!user) {
            window.location.reload();
            return;
        }
        const navAvatar = document.getElementById('nav-avatar');
        const navUsername = document.getElementById('nav-username');
        const userDropdown = document.getElementById('user-dropdown');

        if (navAvatar) navAvatar.src = user.avatar_url;
        if (navUsername) navUsername.textContent = user.username;
        if (userDropdown) userDropdown.style.display = '';  // reveal dropdown
    }

    /* ── WebSocket live log stream (only on logs page) ─────────── */
    const logsBody = document.getElementById('logs-body');
    if (logsBody) {
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        let ws;

        function connectWS() {
            ws = new WebSocket(`${proto}://${location.host}/ws/logs`);

            ws.onmessage = event => {
                const log = JSON.parse(event.data);
                const row = document.createElement('tr');
                const dt = new Date(log.timestamp).toLocaleString();
                row.innerHTML = `
          <td><span class="badge badge-yellow">${escHtml(log.event_type)}</span></td>
          <td>${escHtml(log.description)}</td>
          <td><span class="badge badge-red">${escHtml(log.guild_id)}</span></td>
          <td>${dt}</td>`;
                logsBody.prepend(row);
                // Keep max 50 rows
                while (logsBody.children.length > 50) logsBody.lastChild.remove();
            };

            ws.onclose = () => {
                // Auto-reconnect after 3 seconds
                setTimeout(connectWS, 3000);
            };

            ws.onerror = () => ws.close();
        }

        connectWS();
    }

    /* ── Utility: escape HTML to prevent XSS ──────────────────── */
    function escHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

});
