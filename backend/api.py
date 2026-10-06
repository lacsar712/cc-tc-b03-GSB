import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import and_, func

from claimer import start as start_claimer
from models import (
    Base,
    ConvergenceLog,
    Section,
    SessionLocal,
    engine,
    row_dict,
    section_dict,
)

SECRET = os.environ.get("JWT_SECRET", "tunnelconv-dev-secret")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERS = {
    "surveyor": {"role": "writer", "password_hash": pwd.hash("surv123456")},
    "inspector": {"role": "reader", "password_hash": pwd.hash("insp123456")},
}

app = Flask(__name__)


def seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.query(ConvergenceLog).count() == 0:
            now = datetime.now(timezone.utc)
            for chainage, delta, expect in (("K12+180", 1.2, "合格"), ("K18+040", 5.6, "超限")):
                from rules import judge

                verdict, reason = judge(delta)
                assert verdict == expect
                db.add(
                    ConvergenceLog(
                        chainage=chainage,
                        delta_mm=delta,
                        status="done",
                        verdict=verdict,
                        reason=reason,
                        created_by="surveyor",
                        created_at=now,
                        processed_at=now,
                    )
                )
            db.commit()
        if db.query(Section).count() == 0:
            # K25+300 没有办结记录，用来演示色块墙上的灰色未办结断面
            for chainage, x, y in (
                ("K12+180", 60, 60),
                ("K18+040", 220, 60),
                ("K25+300", 380, 170),
            ):
                db.add(Section(chainage=chainage, x=x, y=y))
            db.commit()
    finally:
        db.close()


seed()
start_claimer()


def current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:].strip(), SECRET, algorithms=["HS256"])
    except JWTError:
        return None
    sub = payload.get("sub")
    if sub not in USERS:
        return None
    return {"username": sub, "role": payload.get("role")}


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"detail": "未登录"}), 401
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


def require_writer(fn=None, *, detail="仅测量员可提交收敛读数"):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({"detail": "未登录"}), 401
            if user["role"] != "writer":
                return jsonify({"detail": detail}), 403
            g.user = user
            return f(*args, **kwargs)

        return wrapper

    if fn is not None:
        return deco(fn)
    return deco


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "tunnel-convergence-desk"})


@app.post("/api/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    user = USERS.get(username)
    if not user or not pwd.verify(password, user["password_hash"]):
        return jsonify({"detail": "用户名或密码错误"}), 401
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode(
        {"sub": username, "role": user["role"], "exp": exp}, SECRET, algorithm="HS256"
    )
    return jsonify({"access_token": token, "username": username, "role": user["role"]})


@app.get("/api/logs")
@require_login
def list_logs():
    db = SessionLocal()
    try:
        rows = db.query(ConvergenceLog).order_by(ConvergenceLog.id.desc()).all()
        return jsonify([row_dict(r) for r in rows])
    finally:
        db.close()


@app.post("/api/logs")
@require_writer
def create_log():
    body = request.get_json(silent=True) or {}
    chainage = (body.get("chainage") or "").strip()
    if not chainage:
        return jsonify({"detail": "桩号不能为空"}), 400
    try:
        delta_mm = float(body.get("delta_mm"))
    except (TypeError, ValueError):
        return jsonify({"detail": "收敛值必须是数字"}), 400
    db = SessionLocal()
    try:
        row = ConvergenceLog(
            chainage=chainage,
            delta_mm=delta_mm,
            status="pending",
            created_by=g.user["username"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        if db.query(Section).filter_by(chainage=chainage).first() is None:
            db.add(Section(chainage=chainage, **next_slot(db)))
        db.commit()
        db.refresh(row)
        return jsonify(row_dict(row)), 201
    finally:
        db.close()


VERDICT_COLORS = {"合格": "green", "超限": "red"}


def next_slot(db) -> dict:
    """新断面自动落位：按现有数量在墙面上排网格。"""
    n = db.query(Section).count()
    return {"x": 60 + (n % 5) * 160, "y": 60 + (n // 5) * 110}


def latest_done_by_chainage(db) -> dict:
    """每个桩号只认已办结单据里编号最大的那一张。"""
    sub = (
        db.query(
            ConvergenceLog.chainage.label("chainage"),
            func.max(ConvergenceLog.id).label("max_id"),
        )
        .filter(ConvergenceLog.status == "done")
        .group_by(ConvergenceLog.chainage)
        .subquery()
    )
    rows = (
        db.query(ConvergenceLog)
        .join(
            sub,
            and_(
                ConvergenceLog.chainage == sub.c.chainage,
                ConvergenceLog.id == sub.c.max_id,
            ),
        )
        .all()
    )
    return {r.chainage: r for r in rows}


@app.get("/api/wall")
@require_login
def wall():
    db = SessionLocal()
    try:
        sections = db.query(Section).order_by(Section.id).all()
        latest = latest_done_by_chainage(db)
        out = []
        for s in sections:
            hit = latest.get(s.chainage)
            verdict = hit.verdict if hit else None
            out.append(
                {
                    **section_dict(s),
                    "verdict": verdict,
                    "color": VERDICT_COLORS.get(verdict, "gray"),
                    "last_log_id": hit.id if hit else None,
                    "processed_at": hit.processed_at.isoformat()
                    if hit and hit.processed_at
                    else None,
                }
            )
        return jsonify(out)
    finally:
        db.close()


@app.post("/api/sections")
@require_writer(detail="巡检岗只读，仅测量员可维护断面坐标")
def create_section():
    body = request.get_json(silent=True) or {}
    chainage = (body.get("chainage") or "").strip()
    if not chainage:
        return jsonify({"detail": "桩号不能为空"}), 400
    db = SessionLocal()
    try:
        if db.query(Section).filter_by(chainage=chainage).first() is not None:
            return jsonify({"detail": "该桩号断面已存在"}), 400
        slot = next_slot(db)
        try:
            x = float(body.get("x", slot["x"]))
            y = float(body.get("y", slot["y"]))
        except (TypeError, ValueError):
            return jsonify({"detail": "坐标必须是数字"}), 400
        row = Section(chainage=chainage, x=x, y=y)
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify(section_dict(row)), 201
    finally:
        db.close()


@app.patch("/api/sections/<int:sid>")
@require_writer(detail="巡检岗只读，仅测量员可维护断面坐标")
def update_section(sid: int):
    body = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        row = db.get(Section, sid)
        if row is None:
            return jsonify({"detail": "断面不存在"}), 404
        if "chainage" in body:
            chainage = (body.get("chainage") or "").strip()
            if not chainage:
                return jsonify({"detail": "桩号不能为空"}), 400
            clash = db.query(Section).filter_by(chainage=chainage).first()
            if clash is not None and clash.id != row.id:
                return jsonify({"detail": "该桩号断面已存在"}), 400
            row.chainage = chainage
        try:
            if "x" in body:
                row.x = float(body["x"])
            if "y" in body:
                row.y = float(body["y"])
        except (TypeError, ValueError):
            return jsonify({"detail": "坐标必须是数字"}), 400
        db.commit()
        db.refresh(row)
        return jsonify(section_dict(row))
    finally:
        db.close()
