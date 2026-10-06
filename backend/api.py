import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from jose import JWTError, jwt
from passlib.context import CryptContext

from claimer import start as start_claimer
from models import Base, ConvergenceLog, Section, SessionLocal, engine, row_dict, section_dict

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
            for chainage, x, y in (
                ("K12+180", 20.0, 30.0),
                ("K18+040", 50.0, 55.0),
                ("K25+300", 78.0, 32.0),
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


def require_writer(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"detail": "未登录"}), 401
        if user["role"] != "writer":
            return jsonify({"detail": "仅测量员可提交收敛读数"}), 403
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


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
        if db.get(Section, chainage) is None:
            n = db.query(Section).count()
            db.add(Section(chainage=chainage, x=10.0 + (n * 17) % 75, y=15.0 + (n * 23) % 65))
        db.commit()
        db.refresh(row)
        return jsonify(row_dict(row)), 201
    finally:
        db.close()


@app.get("/api/sections")
@require_login
def list_sections():
    """色块墙数据源：每个断面取已办结中编号最大的一笔结论；从未办结为 null。"""
    db = SessionLocal()
    try:
        sections = db.query(Section).order_by(Section.chainage).all()
        latest: dict[str, ConvergenceLog] = {}
        done_rows = (
            db.query(ConvergenceLog)
            .filter(ConvergenceLog.status == "done")
            .order_by(ConvergenceLog.id.desc())
            .all()
        )
        for r in done_rows:
            if r.chainage not in latest:
                latest[r.chainage] = r
        return jsonify([section_dict(s, latest.get(s.chainage)) for s in sections])
    finally:
        db.close()


@app.patch("/api/sections/<path:chainage>")
@require_writer
def move_section(chainage):
    body = request.get_json(silent=True) or {}
    try:
        x = float(body.get("x"))
        y = float(body.get("y"))
    except (TypeError, ValueError):
        return jsonify({"detail": "坐标必须是数字"}), 400
    db = SessionLocal()
    try:
        section = db.get(Section, chainage)
        if section is None:
            return jsonify({"detail": "断面不存在"}), 404
        section.x = min(100.0, max(0.0, x))
        section.y = min(100.0, max(0.0, y))
        db.commit()
        return jsonify({"chainage": section.chainage, "x": section.x, "y": section.y})
    finally:
        db.close()
