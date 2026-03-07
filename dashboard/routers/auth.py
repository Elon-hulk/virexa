from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.future import select
from database.connection import get_db
from database.models import User, Session
import httpx
import uuid
from config.settings import DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# ── In-memory OAuth state store (short-lived, only for CSRF validation) ───────
# Sessions are now in the DB; only the ephemeral state tokens live here.
valid_states: set[str] = set()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def get_current_user(request: Request, db: AsyncSession = None):
    """Return User ORM object if session cookie maps to a valid DB session."""
    session_id = request.cookies.get("session_id")
    if not session_id or not db:
        return None
    # Look up the session in the database
    sess_result = await db.execute(select(Session).where(Session.session_id == session_id))
    sess_row = sess_result.scalar_one_or_none()
    if not sess_row:
        return None
    # Fetch the user
    result = await db.execute(select(User).where(User.discord_id == sess_row.discord_id))
    return result.scalar_one_or_none()


async def fetch_admin_guilds(access_token: str) -> list[dict]:
    """Return guilds where the user has the ADMINISTRATOR (0x8) bit."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://discord.com/api/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
    if r.status_code == 200:
        return [g for g in r.json() if (int(g.get("permissions", 0)) & 0x8) == 0x8]
    return []


# ── Auth routes ────────────────────────────────────────────────────────────────

@router.get("/auth/discord/url")
async def discord_auth_url():
    """
    Generate a Discord OAuth2 authorization URL with a server-side state token.
    State is stored in an in-memory set for CSRF validation only.
    """
    state = str(uuid.uuid4())
    valid_states.add(state)
    url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
        f"&state={state}"
    )
    return JSONResponse({"url": url})


@router.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Discord redirects here after the user authorizes.
    Runs inside the popup window.
    Steps:
      1. Validate state (CSRF check)
      2. Exchange code for access token
      3. Fetch Discord user info
      4. Upsert user in DB
      5. Create/replace session row in DB
      6. Set session cookie via HTTP Set-Cookie header
      7. Return HTML that postMessages to parent then closes
    """

    # 1. CSRF state check
    if state not in valid_states:
        return _popup_error("Invalid or expired state. Please try again.")
    valid_states.discard(state)

    # 2. Exchange code → access token
    async with httpx.AsyncClient() as client:
        token_r = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
    if token_r.status_code != 200:
        return _popup_error(f"Token exchange failed: {token_r.text}")

    token_data    = token_r.json()
    access_token  = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token", "")

    # 3. Fetch Discord user info
    async with httpx.AsyncClient() as client:
        user_r = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
    if user_r.status_code != 200:
        return _popup_error("Failed to fetch Discord user info.")

    info       = user_r.json()
    discord_id = str(info["id"])
    username   = info.get("username", "Unknown")
    avatar     = info.get("avatar") or ""

    # 4. Upsert user in database
    result = await db.execute(select(User).where(User.discord_id == discord_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            discord_id=discord_id, username=username,
            avatar=avatar, access_token=access_token, refresh_token=refresh_token,
        )
        db.add(user)
    else:
        user.username = username
        user.avatar = avatar
        user.access_token = access_token
        user.refresh_token = refresh_token or user.refresh_token

    # 5. Create/replace session row in DB
    session_id = str(uuid.uuid4())
    # Remove any old sessions for this user (clean up)
    old_sessions = await db.execute(select(Session).where(Session.discord_id == discord_id))
    for old in old_sessions.scalars().all():
        await db.delete(old)
    new_session = Session(session_id=session_id, discord_id=discord_id)
    db.add(new_session)
    await db.commit()

    # 6. Build avatar URL
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar}.png"
        if avatar else
        f"https://cdn.discordapp.com/embed/avatars/0.png"
    )

    # 7. Return popup HTML — cookie is set via HTTP Set-Cookie header (reliable!)
    html = f"""<!DOCTYPE html>
<html>
<head><title>Authenticating…</title>
<style>
  body {{ margin:0; display:flex; align-items:center; justify-content:center;
         height:100vh; font-family:sans-serif; background:#0B1120; color:#fff; }}
  .box {{ text-align:center; }}
  .spinner {{ width:40px; height:40px; border:4px solid #1E293B; border-top-color:#38BDF8;
              border-radius:50%; animation:spin .6s linear infinite; margin:0 auto 1rem; }}
  @keyframes spin {{ to {{ transform:rotate(360deg) }} }}
</style>
</head>
<body>
<div class="box">
  <div class="spinner"></div>
  <p>Authenticated! Closing…</p>
</div>
<script>
  if (window.opener && !window.opener.closed) {{
    window.opener.postMessage({{
      type: "VIREXA_AUTH_SUCCESS",
      status: "success",
      user: {{
        discord_id: "{discord_id}",
        username:   "{username}",
        avatar_url: "{avatar_url}"
      }}
    }}, window.location.origin);
  }}
  setTimeout(() => window.close(), 800);
</script>
</body>
</html>"""

    resp = HTMLResponse(content=html)
    # Set cookie via HTTP header — much more reliable than document.cookie in a popup
    resp.set_cookie(
        key="session_id",
        value=session_id,
        path="/",
        samesite="lax",
        httponly=False,   # needs to be readable by JS for postMessage
        max_age=60 * 60 * 24 * 30,  # 30 days
    )
    return resp


@router.get("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if session_id:
        sess = await db.execute(select(Session).where(Session.session_id == session_id))
        sess_row = sess.scalar_one_or_none()
        if sess_row:
            await db.delete(sess_row)
            await db.commit()
    resp = RedirectResponse(url="/", status_code=302)
    resp.delete_cookie("session_id", path="/")
    return resp


# ── JSON API endpoints (used by frontend JS after popup login) ─────────────────

@router.get("/api/me")
async def api_me(request: Request, db: AsyncSession = Depends(get_db)):
    """Return current user as JSON, or 401."""
    user = await get_current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{user.discord_id}/{user.avatar}.png"
        if user.avatar else
        f"https://cdn.discordapp.com/embed/avatars/0.png"
    )
    return JSONResponse({
        "discord_id": user.discord_id,
        "username": user.username,
        "avatar_url": avatar_url,
    })


@router.get("/api/guilds")
async def api_guilds(request: Request, db: AsyncSession = Depends(get_db)):
    """Return admin guilds for the current user as JSON."""
    user = await get_current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    guilds = await fetch_admin_guilds(user.access_token)
    return JSONResponse(guilds)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _popup_error(msg: str) -> HTMLResponse:
    """Return a styled error page that runs inside the popup."""
    return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head><title>Error</title>
<style>body{{font-family:sans-serif;background:#0B1120;color:#FB7185;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}</style>
</head>
<body><div style="text-align:center"><h2>❌ {msg}</h2>
<p style="color:#94A3B8">Close this window and try again.</p></div></body>
</html>""", status_code=400)
