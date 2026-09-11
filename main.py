from fastmcp import FastMCP
from pathlib import Path
import sqlite3
import os

# =========================
# Paths
# =========================

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "expenses.db"
CATEGORIES_PATH = BASE_DIR / "categories.json"


# =========================
# Database Debug Information
# =========================

print("Database path:", DB_PATH)
print("Database exists:", DB_PATH.exists())
print("Database writable:", os.access(DB_PATH, os.W_OK))
print("Directory writable:", os.access(DB_PATH.parent, os.W_OK))


# =========================
# MCP Server
# =========================

mcp = FastMCP("ExpenseTracker")


# =========================
# Database Initialization
# =========================

def init_db():
    with sqlite3.connect(DB_PATH) as conn:

        # Expenses table
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

        # Income / salary table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                source TEXT NOT NULL,
                note TEXT DEFAULT ''
            )
        """)


init_db()


# ============================================================
# ADD EXPENSE
# ============================================================

@mcp.tool()
def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = ""
):
    """Add a new expense entry to the database."""

    if amount <= 0:
        return {
            "status": "error",
            "message": "Expense amount must be greater than 0."
        }

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute(
            """
            INSERT INTO expenses
            (date, amount, category, subcategory, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (date, amount, category, subcategory, note)
        )

        return {
            "status": "ok",
            "message": "Expense added successfully.",
            "id": cursor.lastrowid
        }


# ============================================================
# EDIT EXPENSE
# ============================================================

@mcp.tool()
def edit_expense(
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

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute(
            "SELECT * FROM expenses WHERE id = ?",
            (expense_id,)
        )

        existing = cursor.fetchone()

        if existing is None:
            return {
                "status": "error",
                "message": f"Expense with ID {expense_id} was not found."
            }

        # Existing values
        existing_date = existing[1]
        existing_amount = existing[2]
        existing_category = existing[3]
        existing_subcategory = existing[4]
        existing_note = existing[5]

        # Use old value if new value wasn't supplied
        new_date = date if date is not None else existing_date
        new_amount = amount if amount is not None else existing_amount
        new_category = category if category is not None else existing_category
        new_subcategory = (
            subcategory
            if subcategory is not None
            else existing_subcategory
        )
        new_note = note if note is not None else existing_note

        conn.execute(
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

        return {
            "status": "ok",
            "message": "Expense updated successfully.",
            "id": expense_id
        }


# ============================================================
# DELETE EXPENSE
# ============================================================

@mcp.tool()
def delete_expense(expense_id: int):
    """Delete an expense using its ID."""

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute(
            "SELECT id FROM expenses WHERE id = ?",
            (expense_id,)
        )

        expense = cursor.fetchone()

        if expense is None:
            return {
                "status": "error",
                "message": f"Expense with ID {expense_id} was not found."
            }

        conn.execute(
            "DELETE FROM expenses WHERE id = ?",
            (expense_id,)
        )

        return {
            "status": "ok",
            "message": "Expense deleted successfully.",
            "id": expense_id
        }


# ============================================================
# LIST EXPENSES
# ============================================================

@mcp.tool()
def list_expenses(
    start_date: str,
    end_date: str
):
    """List expense entries within an inclusive date range."""

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute(
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

        columns = [column[0] for column in cursor.description]

        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]


# ============================================================
# SUMMARIZE EXPENSES
# ============================================================

@mcp.tool()
def summarize(
    start_date: str,
    end_date: str,
    category: str | None = None
):
    """Summarize expenses by category within an inclusive date range."""

    query = """
        SELECT
            category,
            SUM(amount) AS total_amount
        FROM expenses
        WHERE date BETWEEN ? AND ?
    """

    params = [start_date, end_date]

    if category:
        query += " AND category = ?"
        params.append(category)

    query += """
        GROUP BY category
        ORDER BY category ASC
    """

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute(query, params)

        columns = [column[0] for column in cursor.description]

        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]


# ============================================================
# CREDIT SALARY / INCOME
# ============================================================

@mcp.tool()
def credit_salary(
    date: str,
    amount: float,
    source: str = "Salary",
    note: str = ""
):
    """Record a salary or other income credit."""

    if amount <= 0:
        return {
            "status": "error",
            "message": "Income amount must be greater than 0."
        }

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute(
            """
            INSERT INTO income
            (date, amount, source, note)
            VALUES (?, ?, ?, ?)
            """,
            (date, amount, source, note)
        )

        return {
            "status": "ok",
            "message": "Salary/income credited successfully.",
            "id": cursor.lastrowid
        }


# ============================================================
# LIST INCOME
# ============================================================

@mcp.tool()
def list_income(
    start_date: str,
    end_date: str
):
    """List salary and other income within an inclusive date range."""

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute(
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

        columns = [column[0] for column in cursor.description]

        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]


# ============================================================
# DELETE INCOME
# ============================================================

@mcp.tool()
def delete_income(income_id: int):
    """Delete a salary or income record using its ID."""

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute(
            "SELECT id FROM income WHERE id = ?",
            (income_id,)
        )

        income = cursor.fetchone()

        if income is None:
            return {
                "status": "error",
                "message": f"Income with ID {income_id} was not found."
            }

        conn.execute(
            "DELETE FROM income WHERE id = ?",
            (income_id,)
        )

        return {
            "status": "ok",
            "message": "Income deleted successfully.",
            "id": income_id
        }


# ============================================================
# BALANCE
# ============================================================

@mcp.tool()
def get_balance(
    start_date: str,
    end_date: str
):
    """Calculate total income, total expenses and remaining balance."""

    with sqlite3.connect(DB_PATH) as conn:

        income_cursor = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM income
            WHERE date BETWEEN ? AND ?
            """,
            (start_date, end_date)
        )

        expense_cursor = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """,
            (start_date, end_date)
        )

        total_income = income_cursor.fetchone()[0]
        total_expenses = expense_cursor.fetchone()[0]

        balance = total_income - total_expenses

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "balance": balance
        }


# ============================================================
# CATEGORIES RESOURCE
# ============================================================

@mcp.resource(
    "expense://categories",
    mime_type="application/json"
)
def categories():
    """Return available expense categories."""

    with open(CATEGORIES_PATH, "r", encoding="utf-8") as file:
        return file.read()


# ============================================================
# RUN REMOTE MCP SERVER
# ============================================================

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000,
    )