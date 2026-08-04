"""Admin web UI: review queue + published posts, behind a session cookie.

Runs on the host (rebuilds shell out to `docker compose run --rm builder`);
nginx proxies /admin from the blog origin to this app.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import quote_plus

import frontmatter
import httpx
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from insightpulse import topics
from insightpulse.admin import auth, posts
from insightpulse.enrich.arxiv import arxiv_id_from_url, fetch_meta
from insightpulse.models import Kind, RawPost, Source
from insightpulse.paths import DATA_DIR, QUEUE_PENDING, ROOT, RUN_LOCK
from insightpulse.publish import accept_draft, rebuild_site
from insightpulse.queue import list_drafts, move_draft
from insightpulse.state import State, new_run_id

log = logging.getLogger(__name__)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# set on every content mutation, cleared by a rebuild; the UI shows a
# "site out of date" banner while it is set
_dirty = {"flag": False}

# RUN_LOCK is created by the spawned child, not at Popen time, so between
# spawn and lock creation a second click would pass an exists() check. Track
# the child and serialize check-and-spawn to close that window.
_writer = {"proc": None}
_writer_mutex = threading.Lock()


def _writer_running() -> bool:
    proc = _writer["proc"]
    return (proc is not None and proc.poll() is None) or RUN_LOCK.exists()


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
        with State() as state:
            needs_link = len(state.items_by_status("needs_link"))
        return _render("dashboard.html", request,
                       pending=len(list_drafts("pending")),
                       published=len(posts.list_published()),
                       needs_link=needs_link)

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

    # -- missing paper links -----------------------------------------------

    def _links_page(request: Request, msg: str = "", error: str = "") -> HTMLResponse:
        with State() as state:
            items = [dict(r) for r in state.items_by_status("needs_link")]
        return _render("links_list.html", request, items=items,
                       running=_writer_running(), msg=msg, error=error)

    def _links_redirect(msg: str) -> RedirectResponse:
        return RedirectResponse(f"/admin/links?msg={quote_plus(msg)}",
                                status_code=303)

    @app.get("/admin/links", response_class=HTMLResponse, **guarded)
    def links_list(request: Request, msg: str = ""):
        return _links_page(request, msg=msg)

    @app.post("/admin/links/process", **guarded)
    def links_process(request: Request):
        with _writer_mutex:
            if _writer_running():
                return _links_page(request,
                                   error="A pipeline run is already in progress.")
            with open(DATA_DIR / "admin_process.log", "ab") as logf:
                _writer["proc"] = subprocess.Popen(
                    ["uv", "run", "insightpulse", "process", "--kind", "paper"],
                    cwd=ROOT, stdout=logf, stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        return _links_redirect("Writer run started in the background — follow "
                               "data/admin_process.log")

    @app.post("/admin/links/{item_id}", **guarded)
    def link_fill(request: Request, item_id: str, url: str = Form(...)):
        arxiv_id = arxiv_id_from_url(url.strip())
        if not arxiv_id:
            return _links_page(request, error=f"Link not set on {item_id}: not an "
                               "arXiv URL (paste https://arxiv.org/abs/…, or Skip "
                               "the item).")
        with State() as state:
            if not state.get_item(item_id):
                return _links_page(request, error=f"No such item {item_id}.")
            if state.arxiv_seen(arxiv_id, exclude_item=item_id):
                state.set_status(item_id, "skipped")
                return _links_redirect(f"{item_id} skipped: arXiv {arxiv_id} is "
                                       "already covered by another post")
            state.resolve_link(item_id, arxiv_id)
        return _links_redirect(f"{item_id} → arXiv {arxiv_id}; it will be written "
                               "by the next run (or hit Write now)")

    @app.post("/admin/links/{item_id}/skip", **guarded)
    def link_skip(item_id: str):
        with State() as state:
            if state.get_item(item_id):
                state.set_status(item_id, "skipped")
        return RedirectResponse("/admin/links", status_code=303)

    # -- add paper by arXiv URL ----------------------------------------------

    def _papers_page(request: Request, msg: str = "", error: str = "") -> HTMLResponse:
        with State() as state:
            queued = [dict(r)
                      for status in ("triaged", "enriched")
                      for r in state.items_by_status(status)
                      if r["source"] == Source.manual.value]
        return _render("paper_new.html", request, queued=queued,
                       running=_writer_running(), msg=msg, error=error)

    @app.get("/admin/papers/new", response_class=HTMLResponse, **guarded)
    def paper_new_form(request: Request, msg: str = ""):
        return _papers_page(request, msg=msg)

    @app.post("/admin/papers/new", **guarded)
    def paper_new(request: Request, url: str = Form(...)):
        arxiv_id = arxiv_id_from_url(url.strip())
        if not arxiv_id:
            return _papers_page(request, error="Not an arXiv URL — paste "
                                "https://arxiv.org/abs/… (abs, pdf or html).")
        with State() as state:
            if state.arxiv_seen(arxiv_id):
                return _papers_page(request, error=f"arXiv {arxiv_id} is already "
                                    "covered by another item.")
            try:
                meta = fetch_meta(arxiv_id)
            except (ValueError, httpx.HTTPError) as exc:
                return _papers_page(request, error="Could not fetch arXiv "
                                    f"metadata for {arxiv_id}: {exc}")
            post = RawPost(source=Source.manual, kol="admin",
                           external_id=f"arxiv:{arxiv_id}", text="",
                           urls=[meta.abs_url], paper_name=meta.title)
            item_id = state.insert_post(post, new_run_id())
            if item_id is None:
                return _papers_page(request, error=f"arXiv {arxiv_id} was "
                                    "already added.")
            state.set_triage(item_id, Kind.paper, [meta.abs_url], meta.title,
                             arxiv_id, meta.title)
        return RedirectResponse(
            f"/admin/papers/new?msg={quote_plus(f'Added “{meta.title}” ({arxiv_id}) — it will be written on the next run, or hit Write now.')}",
            status_code=303)

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
    def post_edit(request: Request, bundle: str, error: str = ""):
        try:
            data = posts.read_bundle(bundle)
        except (ValueError, FileNotFoundError):
            return RedirectResponse("/admin/posts", status_code=303)
        meta = frontmatter.loads(data["en"]).metadata
        reliability = meta.get("reliability") or {}
        return _render("post_edit.html", request, post=data, error=error,
                       missing_link=bool(meta.get("missing_link")),
                       paper_name=meta.get("paper_name", ""),
                       topic="/".join(posts.bundle_topic_path(meta)),
                       code_url=str(reliability.get("code_url") or ""))

    @app.post("/admin/posts/{bundle}/link", **guarded)
    def post_link(request: Request, bundle: str, url: str = Form(...)):
        try:
            posts.fill_bundle_link(bundle, url)
        except Exception as exc:
            return post_edit(request, bundle, error=f"Link not set: {exc}")
        _dirty["flag"] = True
        return RedirectResponse(f"/admin/posts/{bundle}", status_code=303)

    @app.post("/admin/posts/{bundle}/topic", **guarded)
    def post_topic(request: Request, bundle: str, topic: str = Form(...)):
        path = topic.strip().strip("/").split("/")
        valid, err, _ = topics.validate_path(path)
        if not valid:
            return post_edit(request, bundle, error=f"Topic invalid: {err}")
        try:
            posts.set_bundle_topic(bundle, path)
        except (ValueError, FileNotFoundError) as exc:
            return post_edit(request, bundle, error=f"Topic not set: {exc}")
        topics.merge_path(path)
        _dirty["flag"] = True
        return RedirectResponse(f"/admin/posts/{bundle}", status_code=303)

    @app.post("/admin/posts/{bundle}/code", **guarded)
    def post_code(request: Request, bundle: str, code_url: str = Form("")):
        url = code_url.strip()
        if url and not url.startswith(("http://", "https://")):
            return post_edit(request, bundle,
                             error="Code URL must start with http(s)://")
        try:
            posts.set_bundle_code(bundle, url)
        except (ValueError, FileNotFoundError) as exc:
            return post_edit(request, bundle, error=f"Code link not set: {exc}")
        _dirty["flag"] = True
        return RedirectResponse(f"/admin/posts/{bundle}", status_code=303)

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
