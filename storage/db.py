import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS project_versions (
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                tool TEXT NOT NULL,
                version TEXT NOT NULL,
                PRIMARY KEY (project_id, tool)
            );
        """)
        self.conn.commit()

    def add_project(self, name: str, path: str) -> int:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO projects (name, path) VALUES (?, ?)",
            (name, path)
        )
        self.conn.commit()
        return cur.lastrowid

    def remove_project(self, project_id: int):
        self.conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.conn.commit()

    def list_projects(self) -> list[dict]:
        rows = self.conn.execute("""
            SELECT p.id, p.name, p.path,
                   GROUP_CONCAT(pv.tool || ':' || pv.version) as versions
            FROM projects p
            LEFT JOIN project_versions pv ON pv.project_id = p.id
            GROUP BY p.id
        """).fetchall()

        result = []
        for row in rows:
            versions = {}
            if row["versions"]:
                for pair in row["versions"].split(","):
                    tool, ver = pair.split(":", 1)
                    versions[tool] = ver
            result.append({
                "id": row["id"],
                "name": row["name"],
                "path": row["path"],
                "versions": versions,
            })
        return result

    def set_project_version(self, project_id: int, tool: str, version: str):
        self.conn.execute("""
            INSERT INTO project_versions (project_id, tool, version)
            VALUES (?, ?, ?)
            ON CONFLICT(project_id, tool) DO UPDATE SET version = excluded.version
        """, (project_id, tool, version))
        self.conn.commit()
