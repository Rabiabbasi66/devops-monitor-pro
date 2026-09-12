import asyncio
import os, sys
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("DATABASE_NAME", "devops_monitor_pro_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

# ── A. app.main import ──────────────────────────────────────────────────────
try:
    import app.main
    print("[OK]  app.main imports cleanly")
except Exception as e:
    print(f"[ERR] app.main: {type(e).__name__}: {e}")
    sys.exit(1)

# ── D. User.email query expression ──────────────────────────────────────────
# Beanie creates ExpressionField descriptors during init_beanie(), so the
# check must run after a real database initialisation.
async def _check_query_expressions() -> bool:
    from beanie import init_beanie
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.config import settings
    from app.models import MODELS

    client = AsyncIOMotorClient(settings.MONGODB_URI)
    try:
        db = client[settings.DATABASE_NAME]
        await init_beanie(database=db, document_models=MODELS)

        from app.models.user import User
        expr = User.email == "test@example.com"
        print(f"[OK]  User.email query expression works: {expr}")

        expr2 = User.username == "testuser"
        print(f"[OK]  User.username query expression works: {expr2}")
        return True
    except AttributeError as e:
        print(f"[ERR] query expression: AttributeError: {e}")
        return False
    finally:
        client.close()

if not asyncio.run(_check_query_expressions()):
    sys.exit(1)

# ── E. Refresh token type validation is wired ───────────────────────────────
import inspect
from app.routers.auth_router import refresh_token as rt_func
src = inspect.getsource(rt_func)
if 'payload.get("type") != "refresh"' in src or "payload.get('type') != 'refresh'" in src:
    print('[OK]  Refresh token type check present in auth_router.refresh_token')
else:
    print('[ERR] Refresh token type check NOT found in auth_router.refresh_token')
    print(src[:600])

# ── Fix 7: agent_version in MetricIngest ────────────────────────────────────
from app.schemas.metric import MetricIngest
fields = MetricIngest.model_fields
if "agent_version" in fields:
    print("[OK]  MetricIngest.agent_version field present")
else:
    print("[ERR] MetricIngest.agent_version field MISSING")

# ── Fix 5: WhatsApp messaging_product ───────────────────────────────────────
import inspect
from app.services.notifications.whatsapp_provider import WhatsAppProvider
wp_src = inspect.getsource(WhatsAppProvider)
if '"messaging_product": "whatsapp"' in wp_src:
    print('[OK]  WhatsApp messaging_product = "whatsapp"')
else:
    print('[ERR] WhatsApp messaging_product is WRONG')
    import re
    for line in wp_src.splitlines():
        if "messaging_product" in line:
            print(f"       found: {line.strip()}")

# ── Fix 6: serialize_server has new fields ───────────────────────────────────
from app.services.server_service import serialize_server
ss_src = inspect.getsource(serialize_server)
expected = ["environment", "agent_version", "agent_status", "os_version",
            "architecture", "description", "location", "owner", "monitoring_enabled"]
missing = [f for f in expected if f not in ss_src]
if not missing:
    print(f"[OK]  serialize_server includes all new fields: {expected}")
else:
    print(f"[ERR] serialize_server missing fields: {missing}")

# ── Fix 8: network_interfaces key in collectors ──────────────────────────────
coll_src = open(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "agent", "collectors", "__init__.py"),
    encoding="utf-8",
).read()
if '"network_interfaces"' in coll_src and '"interfaces"' not in coll_src.replace('"network_interfaces"', ''):
    print('[OK]  collectors uses "network_interfaces" key (no bare "interfaces" key)')
elif '"network_interfaces"' in coll_src:
    print('[OK]  collectors uses "network_interfaces" key')
else:
    print('[ERR] collectors still uses wrong "interfaces" key')

print("\n[DONE] All checks complete.")
