"""
Слой работы с базой данных (SQLite через aiosqlite).
Файл базы (barbershop.db) создаётся автоматически при первом запуске.
"""
import aiosqlite

DB_PATH = "barbershop.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_name TEXT,
    user_phone TEXT,
    service_name TEXT NOT NULL,
    service_price INTEGER NOT NULL,
    master_name TEXT NOT NULL,
    booking_date TEXT NOT NULL,   -- YYYY-MM-DD
    booking_time TEXT NOT NULL,   -- HH:MM
    status TEXT NOT NULL DEFAULT 'active',  -- active / cancelled
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


async def add_booking(user_id: int, user_name: str, service_name: str,
                       service_price: int, master_name: str,
                       booking_date: str, booking_time: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO bookings
               (user_id, user_name, service_name, service_price, master_name, booking_date, booking_time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, user_name, service_name, service_price, master_name, booking_date, booking_time),
        )
        await db.commit()
        return cursor.lastrowid


async def get_booked_times(master_name: str, booking_date: str) -> list[str]:
    """Список уже занятых (активных) слотов времени на дату у мастера."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT booking_time FROM bookings
               WHERE master_name = ? AND booking_date = ? AND status = 'active'""",
            (master_name, booking_date),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_user_bookings(user_id: int) -> list[tuple]:
    """Активные будущие записи пользователя, отсортированные по дате/времени."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, service_name, service_price, master_name, booking_date, booking_time
               FROM bookings
               WHERE user_id = ? AND status = 'active'
               ORDER BY booking_date, booking_time""",
            (user_id,),
        )
        return await cursor.fetchall()


async def get_booking_by_id(booking_id: int) -> tuple | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, user_id, user_name, service_name, service_price,
                      master_name, booking_date, booking_time, status
               FROM bookings WHERE id = ?""",
            (booking_id,),
        )
        return await cursor.fetchone()


async def cancel_booking(booking_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = ?",
            (booking_id,),
        )
        await db.commit()
