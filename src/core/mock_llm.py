"""Mock LLM for demo/dry-run mode — simulates the full pipeline without an API key."""

import json
import time
import random


# ──────────────────────────────────────────────
# Mock Responses (realistic sample outputs)
# ──────────────────────────────────────────────

MOCK_PLAN = {
    "project_name": "todo_api",
    "description": "A RESTful Todo API with CRUD operations, user authentication, and SQLite storage.",
    "tech_stack": ["Python", "FastAPI", "SQLite", "Pydantic", "uvicorn"],
    "file_structure": [
        "app/__init__.py",
        "app/main.py",
        "app/models.py",
        "app/database.py",
        "app/routers/todos.py",
        "app/routers/auth.py",
        "requirements.txt",
    ],
    "modules": ["app", "app.routers"],
    "endpoints": [
        {"method": "GET", "path": "/todos", "description": "List all todos"},
        {"method": "POST", "path": "/todos", "description": "Create a new todo"},
        {"method": "GET", "path": "/todos/{id}", "description": "Get a specific todo"},
        {"method": "PUT", "path": "/todos/{id}", "description": "Update a todo"},
        {"method": "DELETE", "path": "/todos/{id}", "description": "Delete a todo"},
        {"method": "POST", "path": "/auth/register", "description": "Register a new user"},
        {"method": "POST", "path": "/auth/login", "description": "Login and get JWT token"},
    ],
    "additional_notes": "Uses SQLite for simplicity. JWT-based auth with bcrypt password hashing.",
}

MOCK_CODE_FILES = [
    {
        "file_path": "app/__init__.py",
        "content": '"""Todo API Application."""\n',
        "language": "python",
    },
    {
        "file_path": "app/main.py",
        "content": '''"""FastAPI application entry point."""

from fastapi import FastAPI
from app.routers import todos, auth
from app.database import create_tables

app = FastAPI(title="Todo API", version="1.0.0")

app.include_router(todos.router, prefix="/todos", tags=["todos"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    create_tables()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
''',
        "language": "python",
    },
    {
        "file_path": "app/models.py",
        "content": '''"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TodoCreate(BaseModel):
    """Schema for creating a todo."""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    completed: bool = False


class TodoResponse(BaseModel):
    """Schema for todo response."""
    id: int
    title: str
    description: Optional[str]
    completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """Schema for user registration."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
''',
        "language": "python",
    },
    {
        "file_path": "app/database.py",
        "content": '''"""SQLite database setup and connection management."""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/todos.db")


def get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    """Create database tables if they don\'t exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN DEFAULT 0,
            user_id INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.close()
''',
        "language": "python",
    },
    {
        "file_path": "app/routers/todos.py",
        "content": '''"""Todo CRUD endpoints."""

from fastapi import APIRouter, HTTPException
from app.models import TodoCreate, TodoResponse
from app.database import get_connection

router = APIRouter()


@router.get("/", response_model=list[TodoResponse])
async def list_todos():
    """List all todos."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM todos ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@router.post("/", response_model=TodoResponse, status_code=201)
async def create_todo(todo: TodoCreate):
    """Create a new todo."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO todos (title, description, completed) VALUES (?, ?, ?)",
        (todo.title, todo.description, todo.completed),
    )
    conn.commit()
    todo_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    conn.close()
    return dict(row)


@router.delete("/{todo_id}", status_code=204)
async def delete_todo(todo_id: int):
    """Delete a todo."""
    conn = get_connection()
    result = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Todo not found")
    conn.close()
''',
        "language": "python",
    },
    {
        "file_path": "requirements.txt",
        "content": "fastapi==0.115.0\\nuvicorn==0.30.0\\npydantic==2.9.0\\nbcrypt==4.2.0\\npython-jose==3.3.0\\n",
        "language": "text",
    },
]

MOCK_REVIEW = {
    "comments": [
        {
            "file_path": "app/routers/todos.py",
            "severity": "warning",
            "category": "resource_management",
            "description": "Database connections are not using context managers. Use 'with' statements to ensure connections are properly closed.",
            "suggestion": "Wrap database calls in 'with get_connection() as conn:' blocks.",
        },
        {
            "file_path": "app/database.py",
            "severity": "info",
            "category": "security",
            "description": "Consider adding connection pooling for better performance under load.",
            "suggestion": "Use a connection pool or async database library like databases.",
        },
    ],
    "overall_quality": "good",
    "summary": "Code is well-structured and follows FastAPI best practices. Minor improvements suggested for resource management.",
}

MOCK_TEST_FILES = [
    {
        "file_path": "tests/test_todos.py",
        "content": '''"""Tests for the Todo API endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_create_todo():
    """Test creating a new todo."""
    response = client.post("/todos/", json={"title": "Test todo"})
    assert response.status_code == 201
    assert response.json()["title"] == "Test todo"


def test_list_todos():
    """Test listing all todos."""
    response = client.get("/todos/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
''',
        "language": "python",
    },
]

MOCK_TEST_RESULT = {
    "passed": True,
    "total_tests": 3,
    "passed_tests": 3,
    "failed_tests": 0,
    "failure_analysis": "All tests passed successfully.",
}

MOCK_DEPLOYMENT = {
    "files": [
        {
            "file_path": "Dockerfile",
            "content": """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
            "language": "dockerfile",
        },
        {
            "file_path": "docker-compose.yml",
            "content": """version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
""",
            "language": "yaml",
        },
    ],
    "instructions": "# Deployment\\n\\n## Docker\\n```bash\\ndocker-compose up -d\\n```\\n\\nAPI will be available at http://localhost:8000\\nDocs at http://localhost:8000/docs",
}


# ──────────────────────────────────────────────
# Mock LLM class
# ──────────────────────────────────────────────

class MockLLM:
    """A fake LLM that returns pre-built responses for demo mode."""

    def __init__(self):
        self._call_count = 0
        self._responses = [
            json.dumps(MOCK_PLAN),
            json.dumps({"files": MOCK_CODE_FILES}),
            json.dumps(MOCK_REVIEW),
            json.dumps({"files": MOCK_CODE_FILES}),  # improved code
            json.dumps({"files": MOCK_TEST_FILES}),
            json.dumps(MOCK_TEST_RESULT),
            json.dumps(MOCK_DEPLOYMENT),
        ]

    def call(self, *args, **kwargs):
        """Simulate an LLM call with a short delay."""
        delay = random.uniform(1.0, 3.0)
        time.sleep(delay)

        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return self._responses[idx]
