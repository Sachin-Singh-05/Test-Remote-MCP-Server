from fastmcp import FastMCP
from pathlib import Path
import os
import tempfile
import aiosqlite


# ============================================================
# PATHS
# ============================================================

TEMP_DIR = Path(tempfile.gettempdir())

# Writable location for remote/container environments
DB_PATH = TEMP_DIR / "expenses.db"

CATEGORIES_PATH = Path(__file__).resolve().parent / "categories.json"

print("=" * 60)
print("Expense Tracker MCP Server")
print("=" * 60)
print(f"Database path      : {DB_PATH}")
print(f"Database exists    : {DB_PATH.exists()}")
print(f"Database writable  : {os.access(DB_PATH, os.W_OK)}")
print(f"Directory writable : {os.access(DB_PATH.parent, os.W_OK)}")
print("=" * 60)


# ============================================================
# MCP SERVER
# ============================================================

mcp = FastMCP("ExpenseTracker")


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """
    Initialize SQLite database and create required tables.
    Uses synchronous sqlite3 only during startup.
    """

    import sqlite3

    try:
        with sqlite3.connect(DB_PATH) as conn:

            conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS income (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    source TEXT NOT NULL,
                    note TEXT DEFAULT ''
                )
            """)

            conn.commit()

        print("Database initialized successfully.")
        print(f"Database location: {DB_PATH}")

    except Exception as e:
        print(f"Database initialization failed: {e}")
        raise


init_db()


# ============================================================
# ADD EXPENSE
# ============================================================

@mcp.tool()
async def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = ""
):
    """Add a new expense entry."""

    if amount <= 0:
        return {
            "status": "error",
            "message": "Expense amount must be greater than 0."
        }

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(
                """
                INSERT INTO expenses
                (date, amount, category, subcategory, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (date, amount, category, subcategory, note)
            )

            await conn.commit()

            return {
                "status": "success",
                "message": "Expense added successfully.",
                "id": cursor.lastrowid
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }


# ============================================================
# EDIT EXPENSE
# ============================================================

@mcp.tool()
async def edit_expense(
    expense_id: int,
    date: str | None = None,
    amount: float | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    note: str | None = None
):
    """Edit an existing expense. Only supplied fields are updated."""

    if amount is not None and amount <= 0:
        return {
            "status": "error",
            "message": "Expense amount must be greater than 0."
        }

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(
                "SELECT * FROM expenses WHERE id = ?",
                (expense_id,)
            )

            existing = await cursor.fetchone()

            if existing is None:
                return {
                    "status": "error",
                    "message": f"Expense with ID {expense_id} was not found."
                }

            existing_date = existing[1]
            existing_amount = existing[2]
            existing_category = existing[3]
            existing_subcategory = existing[4]
            existing_note = existing[5]

            new_date = date if date is not None else existing_date
            new_amount = amount if amount is not None else existing_amount
            new_category = category if category is not None else existing_category
            new_subcategory = (
                subcategory
                if subcategory is not None
                else existing_subcategory
            )
            new_note = note if note is not None else existing_note

            await conn.execute(
                """
                UPDATE expenses
                SET
                    date = ?,
                    amount = ?,
                    category = ?,
                    subcategory = ?,
                    note = ?
                WHERE id = ?
                """,
                (
                    new_date,
                    new_amount,
                    new_category,
                    new_subcategory,
                    new_note,
                    expense_id
                )
            )

            await conn.commit()

            return {
                "status": "success",
                "message": "Expense updated successfully.",
                "id": expense_id
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }


# ============================================================
# DELETE EXPENSE
# ============================================================

@mcp.tool()
async def delete_expense(expense_id: int):
    """Delete an expense using its ID."""

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(
                "SELECT id FROM expenses WHERE id = ?",
                (expense_id,)
            )

            expense = await cursor.fetchone()

            if expense is None:
                return {
                    "status": "error",
                    "message": f"Expense with ID {expense_id} was not found."
                }

            await conn.execute(
                "DELETE FROM expenses WHERE id = ?",
                (expense_id,)
            )

            await conn.commit()

            return {
                "status": "success",
                "message": "Expense deleted successfully.",
                "id": expense_id
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }


# ============================================================
# LIST EXPENSES
# ============================================================

@mcp.tool()
async def list_expenses(
    start_date: str,
    end_date: str
):
    """List expenses within an inclusive date range."""

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(
                """
                SELECT
                    id,
                    date,
                    amount,
                    category,
                    subcategory,
                    note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date ASC, id ASC
                """,
                (start_date, end_date)
            )

            rows = await cursor.fetchall()
            columns = [column[0] for column in cursor.description]

            return [
                dict(zip(columns, row))
                for row in rows
            ]

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }


# ============================================================
# SUMMARIZE EXPENSES
# ============================================================

@mcp.tool()
async def summarize(
    start_date: str,
    end_date: str,
    category: str | None = None
):
    """Summarize expenses by category."""

    try:
        query = """
            SELECT
                category,
                SUM(amount) AS total_amount,
                COUNT(*) AS count
            FROM expenses
            WHERE date BETWEEN ? AND ?
        """

        params = [start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += """
            GROUP BY category
            ORDER BY total_amount DESC
        """

        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(query, params)

            rows = await cursor.fetchall()
            columns = [column[0] for column in cursor.description]

            return [
                dict(zip(columns, row))
                for row in rows
            ]

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }


# ============================================================
# CREDIT SALARY / INCOME
# ============================================================

@mcp.tool()
async def credit_salary(
    date: str,
    amount: float,
    source: str = "Salary",
    note: str = ""
):
    """Record salary or other income."""

    if amount <= 0:
        return {
            "status": "error",
            "message": "Income amount must be greater than 0."
        }

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(
                """
                INSERT INTO income
                (date, amount, source, note)
                VALUES (?, ?, ?, ?)
                """,
                (date, amount, source, note)
            )

            await conn.commit()

            return {
                "status": "success",
                "message": "Income credited successfully.",
                "id": cursor.lastrowid
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }


# ============================================================
# LIST INCOME
# ============================================================

@mcp.tool()
async def list_income(
    start_date: str,
    end_date: str
):
    """List income within an inclusive date range."""

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(
                """
                SELECT
                    id,
                    date,
                    amount,
                    source,
                    note
                FROM income
                WHERE date BETWEEN ? AND ?
                ORDER BY date ASC, id ASC
                """,
                (start_date, end_date)
            )

            rows = await cursor.fetchall()
            columns = [column[0] for column in cursor.description]

            return [
                dict(zip(columns, row))
                for row in rows
            ]

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }


# ============================================================
# DELETE INCOME
# ============================================================

@mcp.tool()
async def delete_income(income_id: int):
    """Delete an income record."""

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(
                "SELECT id FROM income WHERE id = ?",
                (income_id,)
            )

            income = await cursor.fetchone()

            if income is None:
                return {
                    "status": "error",
                    "message": f"Income with ID {income_id} was not found."
                }

            await conn.execute(
                "DELETE FROM income WHERE id = ?",
                (income_id,)
            )

            await conn.commit()

            return {
                "status": "success",
                "message": "Income deleted successfully.",
                "id": income_id
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }


# ============================================================
# BALANCE
# ============================================================

@mcp.tool()
async def get_balance(
    start_date: str,
    end_date: str
):
    """Calculate income, expenses and remaining balance."""

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            income_cursor = await conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM income
                WHERE date BETWEEN ? AND ?
                """,
                (start_date, end_date)
            )

            expense_cursor = await conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM expenses
                WHERE date BETWEEN ? AND ?
                """,
                (start_date, end_date)
            )

            total_income = (await income_cursor.fetchone())[0]
            total_expenses = (await expense_cursor.fetchone())[0]

            return {
                "start_date": start_date,
                "end_date": end_date,
                "total_income": total_income,
                "total_expenses": total_expenses,
                "balance": total_income - total_expenses
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }


# ============================================================
# DATABASE STATUS - DEBUG TOOL
# ============================================================

@mcp.tool()
async def database_status():
    """Check database location and write access."""

    return {
        "database_path": str(DB_PATH),
        "database_exists": DB_PATH.exists(),
        "database_writable": os.access(DB_PATH, os.W_OK),
        "directory_writable": os.access(DB_PATH.parent, os.W_OK)
    }


# ============================================================
# CATEGORIES RESOURCE
# ============================================================

@mcp.resource(
    "expense:///categories",
    mime_type="application/json"
)
def categories():
    """Return available expense categories."""

    default_categories = {
        "categories": [
            "Food & Dining",
            "Transportation",
            "Shopping",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Travel",
            "Education",
            "Business",
            "Other"
        ]
    }

    try:
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as file:
            return file.read()

    except FileNotFoundError:
        import json
        return json.dumps(default_categories, indent=2)

    except Exception as e:
        return f'{{"error": "{str(e)}"}}'


# ============================================================
# REMOTE MCP SERVER
# ============================================================

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000
    )