from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from core.settings import settings

_lock = threading.Lock()


class BaseConhecimento:
    def __init__(self) -> None:
        self.arquivo = settings.data_dir / "memoria.db"
        self._inicializar()

    def _inicializar(self) -> None:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA encoding='UTF-8'")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS blocos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL UNIQUE,
                    descricao TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS topicos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bloco_id INTEGER REFERENCES blocos(id) ON DELETE CASCADE,
                    titulo TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    fonte TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_bloco_id ON topicos(bloco_id);
                CREATE INDEX IF NOT EXISTS idx_titulo ON topicos(titulo);
                CREATE INDEX IF NOT EXISTS idx_tags ON topicos(tags);
                CREATE VIRTUAL TABLE IF NOT EXISTS topicos_fts USING fts5(
                    titulo, conteudo, tags, content='topicos', content_rowid='id'
                );
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                );
            """)
            conn.commit()

    def criar_bloco(self, nome: str, descricao: str = "") -> int:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO blocos (nome, descricao) VALUES (?, ?)",
                (nome.strip(), descricao.strip()),
            )
            if cursor.lastrowid:
                return cursor.lastrowid
            row = conn.execute("SELECT id FROM blocos WHERE nome = ?", (nome.strip(),)).fetchone()
            return row[0] if row else 0

    def listar_blocos(self) -> list[dict]:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            rows = conn.execute(
                """SELECT b.id, b.nome, b.descricao, b.created_at,
                          COUNT(t.id) as topicos
                   FROM blocos b LEFT JOIN topicos t ON b.id = t.bloco_id
                   GROUP BY b.id ORDER BY b.nome"""
            ).fetchall()
            return [
                {"id": r[0], "nome": r[1], "descricao": r[2], "criado": r[3], "topicos": r[4]}
                for r in rows
            ]

    def obter_bloco(self, bloco_id: int) -> dict | None:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            row = conn.execute(
                """SELECT b.id, b.nome, b.descricao, b.created_at,
                          COUNT(t.id) as topicos
                   FROM blocos b LEFT JOIN topicos t ON b.id = t.bloco_id
                   WHERE b.id = ? GROUP BY b.id""",
                (bloco_id,),
            ).fetchone()
            if row:
                return {"id": row[0], "nome": row[1], "descricao": row[2], "criado": row[3], "topicos": row[4]}
            return None

    def remover_bloco(self, bloco_id: int) -> bool:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            conn.execute("DELETE FROM topicos_fts WHERE rowid IN (SELECT id FROM topicos WHERE bloco_id = ?)", (bloco_id,))
            conn.execute("DELETE FROM topicos WHERE bloco_id = ?", (bloco_id,))
            conn.execute("DELETE FROM blocos WHERE id = ?", (bloco_id,))
            conn.commit()
            return conn.total_changes > 0

    def adicionar(
        self,
        titulo: str,
        conteudo: str,
        bloco_nome: str = "Geral",
        tags: str = "",
        fonte: str = "",
    ) -> int:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            cursor = conn.execute("SELECT id FROM blocos WHERE nome = ?", (bloco_nome.strip(),))
            row = cursor.fetchone()
            if row:
                bloco_id = row[0]
            else:
                cursor = conn.execute("INSERT INTO blocos (nome) VALUES (?)", (bloco_nome.strip(),))
                bloco_id = cursor.lastrowid

            cursor = conn.execute(
                """INSERT INTO topicos (bloco_id, titulo, conteudo, tags, fonte)
                   VALUES (?, ?, ?, ?, ?)""",
                (bloco_id, titulo.strip(), conteudo.strip(), tags.strip(), fonte.strip()),
            )
            row_id = cursor.lastrowid
            if row_id:
                conn.execute(
                    "INSERT INTO topicos_fts (rowid, titulo, conteudo, tags) VALUES (?, ?, ?, ?)",
                    (row_id, titulo.strip(), conteudo.strip(), tags.strip()),
                )
            conn.commit()
            return row_id

    def buscar(self, termo: str, limite: int = 5) -> list[dict]:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            try:
                rows = conn.execute(
                    """SELECT t.id, t.titulo, t.conteudo, b.nome, t.tags,
                              t.fonte, t.created_at, t.access_count
                       FROM topicos_fts f
                       JOIN topicos t ON f.rowid = t.id
                       JOIN blocos b ON t.bloco_id = b.id
                       WHERE topicos_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (termo, limite),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    """SELECT t.id, t.titulo, t.conteudo, b.nome, t.tags,
                              t.fonte, t.created_at, t.access_count
                       FROM topicos t JOIN blocos b ON t.bloco_id = b.id
                       WHERE t.titulo LIKE ? OR t.conteudo LIKE ? OR t.tags LIKE ?
                       LIMIT ?""",
                    (f"%{termo}%", f"%{termo}%", f"%{termo}%", limite),
                ).fetchall()

            resultados = []
            for r in rows:
                conn.execute("UPDATE topicos SET access_count = access_count + 1 WHERE id = ?", (r[0],))
                resultados.append({
                    "id": r[0],
                    "titulo": r[1],
                    "conteudo": r[2],
                    "bloco": r[3],
                    "tags": r[4],
                    "fonte": r[5],
                    "criado": r[6],
                    "acessos": r[7] + 1,
                })
            conn.commit()
            return resultados

    def listar_por_bloco(self, bloco_nome: str) -> list[dict]:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            rows = conn.execute(
                """SELECT t.id, t.titulo, t.conteudo, b.nome, t.tags, t.fonte, t.created_at, t.access_count
                   FROM topicos t JOIN blocos b ON t.bloco_id = b.id
                   WHERE b.nome = ? ORDER BY t.access_count DESC""",
                (bloco_nome,),
            ).fetchall()
            return [
                {
                    "id": r[0],
                    "titulo": r[1],
                    "conteudo": r[2],
                    "bloco": r[3],
                    "tags": r[4],
                    "fonte": r[5],
                    "criado": r[6],
                    "acessos": r[7],
                }
                for r in rows
            ]

    def obter(self, id: int) -> dict | None:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            row = conn.execute(
                """SELECT t.id, t.titulo, t.conteudo, b.nome, t.tags, t.fonte, t.created_at, t.access_count
                   FROM topicos t JOIN blocos b ON t.bloco_id = b.id WHERE t.id = ?""",
                (id,),
            ).fetchone()
            if row:
                conn.execute("UPDATE topicos SET access_count = access_count + 1 WHERE id = ?", (id,))
                conn.commit()
                return {
                    "id": row[0],
                    "titulo": row[1],
                    "conteudo": row[2],
                    "bloco": row[3],
                    "tags": row[4],
                    "fonte": row[5],
                    "criado": row[6],
                    "acessos": row[7] + 1,
                }
            return None

    def remover(self, id: int) -> bool:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            conn.execute("DELETE FROM topicos_fts WHERE rowid = ?", (id,))
            conn.execute("DELETE FROM topicos WHERE id = ?", (id,))
            conn.commit()
            return conn.total_changes > 0

    def contar(self) -> int:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM topicos").fetchone()
            return row[0] if row else 0

    def reindexar_fts(self) -> None:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            conn.execute("INSERT INTO topicos_fts(topicos_fts) VALUES('rebuild')")
            conn.commit()

    def exportar_json(self) -> str:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            blocos_rows = conn.execute("SELECT id, nome, descricao FROM blocos ORDER BY nome").fetchall()
            saida = []
            for b in blocos_rows:
                topicos_rows = conn.execute(
                    "SELECT titulo, conteudo, tags, fonte, created_at, access_count FROM topicos WHERE bloco_id = ?",
                    (b[0],),
                ).fetchall()
                saida.append({
                    "bloco": b[1],
                    "descricao": b[2],
                    "topicos": [
                        {
                            "titulo": r[0],
                            "conteudo": r[1],
                            "tags": r[2],
                            "fonte": r[3],
                            "criado": r[4],
                            "acessos": r[5],
                        }
                        for r in topicos_rows
                    ],
                })
            return json.dumps(saida, ensure_ascii=False, indent=2, default=str)
