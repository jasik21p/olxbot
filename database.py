import json
import logging
from typing import Optional, List, Dict, Any, Tuple
import aiosqlite
from config import DB_PATH, SUPER_ADMIN_ID, DEFAULT_PASSWORD, POLL_INTERVAL

logger = logging.getLogger(__name__)

async def init_db() -> None:
    """Initialize database tables and initial configuration."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                language TEXT DEFAULT 'ru',
                is_authenticated INTEGER DEFAULT 0,
                auth_password_version INTEGER DEFAULT 0,
                is_monitoring_active INTEGER DEFAULT 1,
                min_price REAL DEFAULT NULL,
                max_price REAL DEFAULT NULL,
                price_currency TEXT DEFAULT 'USD',
                min_mileage INTEGER DEFAULT NULL,
                max_mileage INTEGER DEFAULT NULL,
                fuel_types TEXT DEFAULT '[]',
                region TEXT DEFAULT NULL,
                city TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Migration checks
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "region" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN region TEXT DEFAULT NULL;")
        if "city" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN city TEXT DEFAULT NULL;")
        if "language" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru';")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS seen_ads (
                ad_id INTEGER PRIMARY KEY,
                title TEXT,
                created_time TEXT,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Default password and version
        await db.execute("""
            INSERT INTO config (key, value) VALUES ('access_password', ?)
            ON CONFLICT(key) DO NOTHING;
        """, (DEFAULT_PASSWORD,))

        await db.execute("""
            INSERT INTO config (key, value) VALUES ('password_version', '1')
            ON CONFLICT(key) DO NOTHING;
        """)

        await db.execute("""
            INSERT INTO config (key, value) VALUES ('poll_interval', ?)
            ON CONFLICT(key) DO NOTHING;
        """, (str(POLL_INTERVAL),))

        # Ensure Super Admin exists in admins table and users table
        await db.execute("""
            INSERT INTO admins (user_id, username, first_name, added_by)
            VALUES (?, 'super_admin', 'Главный Админ', NULL)
            ON CONFLICT(user_id) DO NOTHING;
        """, (SUPER_ADMIN_ID,))

        await db.execute("""
            INSERT INTO users (user_id, username, first_name, is_authenticated, auth_password_version, language)
            VALUES (?, 'super_admin', 'Главный Админ', 1, 1, 'ru')
            ON CONFLICT(user_id) DO UPDATE SET is_authenticated = 1;
        """, (SUPER_ADMIN_ID,))

        await db.commit()
    logger.info("Database initialized successfully.")

# ==================== CONFIG ====================

async def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_config(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO config (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value;
        """, (key, value))
        await db.commit()

async def get_poll_interval() -> float:
    raw = await get_config("poll_interval", str(POLL_INTERVAL))
    try:
        val = float(raw)
        return max(0.5, val)
    except Exception:
        return 1.0

async def set_poll_interval(interval: float) -> None:
    safe_interval = max(0.5, float(interval))
    await set_config("poll_interval", str(safe_interval))

# ==================== LANGUAGE ====================

async def get_user_language(user_id: int) -> str:
    """Gets user language code ('ru' or 'uz'), defaults to 'ru'."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT language FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return str(row[0])
            return "ru"

async def set_user_language(user_id: int, language: str) -> None:
    """Sets user's language code ('ru' or 'uz')."""
    lang = "uz" if language == "uz" else "ru"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
        await db.commit()

# ==================== ADMINS MANAGEMENT ====================

def is_super_admin(user_id: int) -> bool:
    return int(user_id) == SUPER_ADMIN_ID

async def is_admin(user_id: int) -> bool:
    if is_super_admin(user_id):
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return (await cursor.fetchone()) is not None

async def add_admin(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None, added_by: int = SUPER_ADMIN_ID) -> bool:
    """Adds a new regular admin (Super Admin only)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO admins (user_id, username, first_name, added_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                username = COALESCE(excluded.username, admins.username),
                first_name = COALESCE(excluded.first_name, admins.first_name);
        """, (user_id, username, first_name, added_by))

        _, version = await get_auth_info()
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, is_authenticated, auth_password_version, language)
            VALUES (?, ?, ?, 1, ?, 'ru')
            ON CONFLICT(user_id) DO UPDATE SET is_authenticated = 1, auth_password_version = ?;
        """, (user_id, username, first_name, version, version))

        await db.commit()
    logger.info(f"Admin {user_id} added by {added_by}.")
    return True

async def remove_admin(user_id: int) -> bool:
    """Removes a regular admin (Super Admin cannot be removed)."""
    if is_super_admin(user_id):
        logger.warning("Attempted to remove Super Admin!")
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.execute("UPDATE users SET is_authenticated = 0 WHERE user_id = ?", (user_id,))
        await db.commit()
    logger.info(f"Admin rights revoked from {user_id}.")
    return True

async def get_all_admins() -> List[Dict[str, Any]]:
    """Returns list of all administrators with details."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT a.user_id, a.username, a.first_name, a.added_by, a.added_at,
                   u.username as user_uname, u.first_name as user_fname
            FROM admins a
            LEFT JOIN users u ON a.user_id = u.user_id
            ORDER BY (a.user_id = ?) DESC, a.added_at ASC;
        """, (SUPER_ADMIN_ID,)) as cursor:
            rows = await cursor.fetchall()
            admins = []
            for r in rows:
                item = dict(r)
                item["display_name"] = item.get("user_fname") or item.get("user_uname") or item.get("first_name") or item.get("username") or f"ID {item['user_id']}"
                item["is_super"] = (item["user_id"] == SUPER_ADMIN_ID)
                admins.append(item)
            return admins

# ==================== AUTH & USERS ====================

async def get_auth_info() -> Tuple[str, int]:
    """Returns (current_password, password_version)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT key, value FROM config WHERE key IN ('access_password', 'password_version')") as cursor:
            rows = await cursor.fetchall()
            data = {r['key']: r['value'] for r in rows}
            password = data.get('access_password', DEFAULT_PASSWORD)
            version = int(data.get('password_version', '1'))
            return password, version

async def update_password(new_password: str) -> int:
    """
    Updates the password, increments password_version,
    and de-authenticates all regular (non-admin) users.
    Admins are NEVER de-authenticated.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM config WHERE key = 'password_version'")
        row = await cursor.fetchone()
        current_version = int(row[0]) if row else 1
        new_version = current_version + 1

        await db.execute("""
            INSERT INTO config (key, value) VALUES ('access_password', ?) 
            ON CONFLICT(key) DO UPDATE SET value = excluded.value;
        """, (new_password,))
        await db.execute("""
            INSERT INTO config (key, value) VALUES ('password_version', ?) 
            ON CONFLICT(key) DO UPDATE SET value = excluded.value;
        """, (str(new_version),))

        # Revoke sessions for all non-admin users
        await db.execute("""
            UPDATE users 
            SET is_authenticated = 0 
            WHERE user_id != ? 
              AND user_id NOT IN (SELECT user_id FROM admins);
        """, (SUPER_ADMIN_ID,))

        # Keep all admins authenticated with the new version
        await db.execute("""
            UPDATE users 
            SET is_authenticated = 1, auth_password_version = ?
            WHERE user_id = ? OR user_id IN (SELECT user_id FROM admins);
        """, (new_version, SUPER_ADMIN_ID))

        await db.commit()
    logger.info(f"Password updated to version {new_version}. Non-admin sessions revoked.")
    return new_version

async def get_or_create_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> Dict[str, Any]:
    user_is_adm = await is_admin(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute("""
                    UPDATE users 
                    SET last_seen = CURRENT_TIMESTAMP, 
                        username = COALESCE(?, username), 
                        first_name = COALESCE(?, first_name)
                    WHERE user_id = ?;
                """, (username, first_name, user_id))
                await db.commit()
                return dict(row)

        _, version = await get_auth_info()
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, is_authenticated, auth_password_version, language)
            VALUES (?, ?, ?, ?, ?, 'ru');
        """, (user_id, username, first_name, 1 if user_is_adm else 0, version if user_is_adm else 0))
        await db.commit()

        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            new_row = await cursor.fetchone()
            return dict(new_row)

async def is_user_authorized(user_id: int) -> bool:
    """Checks if user has active authorized session. ALL ADMINS ARE ALWAYS AUTHORIZED WITHOUT PASSWORD."""
    if await is_admin(user_id):
        return True
    
    _, current_version = await get_auth_info()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT is_authenticated, auth_password_version FROM users WHERE user_id = ?", 
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            is_auth, auth_version = row
            return bool(is_auth and auth_version == current_version)

async def authenticate_user(user_id: int) -> None:
    _, current_version = await get_auth_info()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users 
            SET is_authenticated = 1, auth_password_version = ?
            WHERE user_id = ?;
        """, (current_version, user_id))
        await db.commit()

async def toggle_monitoring(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_monitoring_active FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            current_state = row[0] if row else 1
            new_state = 0 if current_state == 1 else 1
        
        await db.execute("UPDATE users SET is_monitoring_active = ? WHERE user_id = ?", (new_state, user_id))
        await db.commit()
        return bool(new_state)

async def get_user_filters(user_id: int) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT min_price, max_price, price_currency, min_mileage, max_mileage, fuel_types, region, city, language, is_monitoring_active
            FROM users WHERE user_id = ?
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return {
                    "min_price": None,
                    "max_price": None,
                    "price_currency": "USD",
                    "min_mileage": None,
                    "max_mileage": None,
                    "fuel_types": [],
                    "region": None,
                    "city": None,
                    "language": "ru",
                    "is_monitoring_active": 1
                }
            res = dict(row)
            try:
                res["fuel_types"] = json.loads(res.get("fuel_types") or "[]")
            except Exception:
                res["fuel_types"] = []
            if not res.get("language"):
                res["language"] = "ru"
            return res

async def update_user_filters(user_id: int, **kwargs) -> None:
    allowed_fields = [
        "min_price", "max_price", "price_currency", 
        "min_mileage", "max_mileage", "fuel_types", 
        "region", "city", "language", "is_monitoring_active"
    ]
    updates = []
    values = []
    for k, v in kwargs.items():
        if k in allowed_fields:
            updates.append(f"{k} = ?")
            if k == "fuel_types" and isinstance(v, (list, set)):
                values.append(json.dumps(list(v), ensure_ascii=False))
            else:
                values.append(v)
    
    if updates:
        values.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(query, tuple(values))
            await db.commit()

async def reset_user_filters(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users 
            SET min_price = NULL, max_price = NULL, price_currency = 'USD',
                min_mileage = NULL, max_mileage = NULL, fuel_types = '[]',
                region = NULL, city = NULL
            WHERE user_id = ?
        """, (user_id,))
        await db.commit()

# ==================== SEEN ADS ====================

async def is_ad_seen(ad_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM seen_ads WHERE ad_id = ?", (ad_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

async def mark_ad_seen(ad_id: int, title: str, created_time: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO seen_ads (ad_id, title, created_time) 
            VALUES (?, ?, ?)
            ON CONFLICT(ad_id) DO NOTHING;
        """, (ad_id, title, created_time))
        await db.commit()

async def mark_multiple_ads_seen(ads: List[Tuple[int, str, str]]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany("""
            INSERT INTO seen_ads (ad_id, title, created_time) 
            VALUES (?, ?, ?)
            ON CONFLICT(ad_id) DO NOTHING;
        """, ads)
        await db.commit()

async def count_seen_ads() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM seen_ads") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_active_authorized_users() -> List[Dict[str, Any]]:
    """Returns all users who are currently authorized (or admins) and have monitoring active."""
    _, current_version = await get_auth_info()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM users 
            WHERE is_monitoring_active = 1 
              AND (
                  user_id = ? 
                  OR user_id IN (SELECT user_id FROM admins)
                  OR (is_authenticated = 1 AND auth_password_version = ?)
              );
        """, (SUPER_ADMIN_ID, current_version)) as cursor:
            rows = await cursor.fetchall()
            users = []
            for r in rows:
                u = dict(r)
                try:
                    u["fuel_types"] = json.loads(u.get("fuel_types") or "[]")
                except Exception:
                    u["fuel_types"] = []
                if not u.get("language"):
                    u["language"] = "ru"
                users.append(u)
            return users

async def get_stats() -> Dict[str, Any]:
    _, current_version = await get_auth_info()
    current_pass, _ = await get_auth_info()
    poll_int = await get_poll_interval()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c1:
            total_users = (await c1.fetchone())[0]
        
        async with db.execute("""
            SELECT COUNT(*) FROM users 
            WHERE user_id = ? 
               OR user_id IN (SELECT user_id FROM admins)
               OR (is_authenticated = 1 AND auth_password_version = ?)
        """, (SUPER_ADMIN_ID, current_version)) as c2:
            auth_users = (await c2.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM admins") as c3:
            total_admins = (await c3.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM seen_ads") as c4:
            total_ads = (await c4.fetchone())[0]

        return {
            "total_users": total_users,
            "authorized_users": auth_users,
            "total_admins": total_admins,
            "seen_ads": total_ads,
            "password_version": current_version,
            "current_password": current_pass,
            "poll_interval": poll_int
        }
