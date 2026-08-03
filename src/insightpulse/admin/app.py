"""Admin web UI: review queue + published posts, behind a session cookie.

Runs on the host (rebuilds shell out to `docker compose run --rm builder`);
nginx proxies /admin from the blog origin to this app.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import frontmatter
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from insightpulse import topics
from insightpulse.admin import auth, posts
from insightpulse.paths import QUEUE_PENDING
from insightpulse.publish import accept_draft, rebuild_site
from insightpulse.queue import list_drafts, move_draft
from insightpulse.state import State

log = logging.getLogger(__name__)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# set on every content mutation, cleared by a rebuild; the UI shows a
# "site out of date" banner while it is set
_dirty = {"flag": False}


def _render(template_name: str, request: Request, **ctx) -> HTMLResponse:
    ctx.update(request=request, dirty=_dirty["flag"])
    return templates.TemplateResponse(request, template_name, ctx)


def _pending_draft_path(draft_id: str) -> Path:
    return posts.check_name(f"{draft_id}.md", base=QUEUE_PENDING)


def create_app() -> FastAPI:
    app = FastAPI(title="InsightPulse Admin", docs_url=None, redoc_url=None)
    guarded = {"dependencies": [Depends(auth.require_session)]}

    # only hit when the app is accessed directly on its own port;
    # via nginx, / serves the static blog
    @app.get("/")
    def root():
        return RedirectResponse("/admin/", status_code=303)

    # -- auth ------------------------------------------------------------

    @app.get("/admin/login", response_class=HTMLResponse)
    def login_form(request: Request):
        return _render("login.html", request, error="")

    @app.post("/admin/login")
    def login(request: Request, password: str = Form(...)):
        if not auth.verify_password(password, auth.load_auth()["password_hash"]):
            time.sleep(0.5)  # brute-force damper
            return _render("login.html", request, error="Wrong password.")
        resp = RedirectResponse("/admin/", status_code=303)
        resp.set_cookie(
            auth.SESSION_COOKIE, auth.make_session_token(),
            max_age=auth.SESSION_MAX_AGE, httponly=True, samesite="lax",
            path="/admin",
        )
        return resp

    @app.post("/admin/logout", **guarded)
    def logout():
        resp = RedirectResponse("/admin/login", status_code=303)
        resp.delete_cookie(auth.SESSION_COOKIE, path="/admin")
        return resp

    # -- dashboard ---------------------------------------------------------

    @app.get("/admin/", response_class=HTMLResponse, **guarded)
    def dashboard(request: Request):
        return _render("dashboard.html", request,
                       pending=len(list_drafts("pending")),
                       published=len(posts.list_published()))

    # -- review queue ------------------------------------------------------

    @app.get("/admin/queue", response_class=HTMLResponse, **guarded)
    def queue_list(request: Request):
        return _render("queue_list.html", request, drafts=list_drafts("pending"))

    @app.get("/admin/queue/{draft_id}", response_class=HTMLResponse, **guarded)
    def draft_edit(request: Request, draft_id: str, error: str = ""):
        path = _pending_draft_path(draft_id)
        if not path.is_file():
            return RedirectResponse("/admin/queue", status_code=303)
        return _render("draft_edit.html", request, draft_id=draft_id,
                       content=path.read_text(), error=error)

    @app.post("/admin/queue/{draft_id}/save", **guarded)
    def draft_save(request: Request, draft_id: str, content: str = Form(...)):
        path = _pending_draft_path(draft_id)
        try:
            frontmatter.loads(content)
        except Exception as exc:
            return _render("draft_edit.html", request, draft_id=draft_id,
                           content=content, error=f"Not saved — bad frontmatter: {exc}")
        path.write_text(content)
        return RedirectResponse(f"/admin/queue/{draft_id}", status_code=303)

    @app.post("/admin/queue/{draft_id}/accept", **guarded)
    def draft_accept(request: Request, draft_id: str, topic: str = Form("")):
        _pending_draft_path(draft_id)  # name guard
        topic_override = None
        if topic.strip():
            topic_override = topic.strip().strip("/").split("/")
            valid, err, _ = topics.validate_path(topic_override)
            if not valid:
                path = _pending_draft_path(draft_id)
                return _render("draft_edit.html", request, draft_id=draft_id,
                               content=path.read_text(), error=f"Topic invalid: {err}")
        accept_draft(draft_id, topic_override=topic_override)
        _dirty["flag"] = True
        return RedirectResponse("/admin/queue", status_code=303)

    @app.post("/admin/queue/{draft_id}/reject", **guarded)
    def draft_reject(draft_id: str, reason: str = Form("")):
        _pending_draft_path(draft_id)  # name guard
        move_draft(draft_id, "rejected", {"reject_reason": reason} if reason else {})
        with State() as state:
            if state.get_item(draft_id):
                state.set_status(draft_id, "rejected")
        return RedirectResponse("/admin/queue", status_code=303)

    # -- published posts -----------------------------------------------------

    @app.get("/admin/posts", response_class=HTMLResponse, **guarded)
    def posts_list(request: Request):
        return _render("posts_list.html", request, posts=posts.list_published())

    @app.get("/admin/posts/new", response_class=HTMLResponse, **guarded)
    def post_new_form(request: Request):
        return _render("post_new.html", request,
                       template=posts.new_post_template(), error="")

    @app.post("/admin/posts/new", **guarded)
    def post_new(request: Request, name: str = Form(...), en: str = Form(...),
                 vi: str = Form("")):
        try:
            posts.create_bundle(name.strip(), en, vi)
        except (ValueError, FileExistsError) as exc:
            return _render("post_new.html", request, template=en, error=str(exc))
        _dirty["flag"] = True
        return RedirectResponse(f"/admin/posts/{name.strip()}", status_code=303)

    @app.get("/admin/posts/{bundle}", response_class=HTMLResponse, **guarded)
    def post_edit(request: Request, bundle: str):
        try:
            data = posts.read_bundle(bundle)
        except (ValueError, FileNotFoundError):
            return RedirectResponse("/admin/posts", status_code=303)
        return _render("post_edit.html", request, post=data, error="")

    @app.post("/admin/posts/{bundle}/save", **guarded)
    def post_save(request: Request, bundle: str, en: str = Form(...),
                  vi: str = Form("")):
        try:
            posts.write_bundle(bundle, en, vi)
        except ValueError as exc:
            return _render("post_edit.html", request,
                           post={"name": bundle, "en": en, "vi": vi}, error=str(exc))
        _dirty["flag"] = True
        return RedirectResponse(f"/admin/posts/{bundle}", status_code=303)

    @app.post("/admin/posts/{bundle}/delete", **guarded)
    def post_delete(bundle: str):
        posts.delete_bundle(bundle)
        _dirty["flag"] = True
        return RedirectResponse("/admin/posts", status_code=303)

    # -- rebuild ---------------------------------------------------------

    @app.post("/admin/rebuild", **guarded)
    def rebuild(request: Request):
        rebuild_site()
        _dirty["flag"] = False
        referer = request.headers.get("referer", "/admin/")
        return RedirectResponse(referer, status_code=303)

    return app
