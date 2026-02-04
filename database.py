import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
class Database:
    def __init__(self, db_path: str = "getgems.db"):
        self.db_path = db_path
        self.init_database()
    def init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('DROP TABLE IF EXISTS gifts')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gifts_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    gift_link TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gift_shares (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nft_link TEXT NOT NULL,
                    nft_name TEXT NOT NULL,
                    nft_number TEXT NOT NULL,
                    creator_telegram_id INTEGER NOT NULL,
                    recipient_telegram_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    received_at TIMESTAMP,
                    is_received BOOLEAN DEFAULT FALSE,
                    share_token TEXT UNIQUE NOT NULL,
                    FOREIGN KEY (creator_telegram_id) REFERENCES users (telegram_id),
                    FOREIGN KEY (recipient_telegram_id) REFERENCES users (telegram_id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gifts_links_user_id ON gifts_links(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gift_shares_creator ON gift_shares(creator_telegram_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gift_shares_recipient ON gift_shares(recipient_telegram_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gift_shares_token ON gift_shares(share_token)')
            conn.commit()
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    def create_user(self, telegram_id: int, username: str = None, 
                   first_name: str = None, last_name: str = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (telegram_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (telegram_id, username, first_name, last_name))
            user_id = cursor.lastrowid
            conn.commit()
            return user_id
    def get_or_create_user(self, telegram_id: int, username: str = None,
                          first_name: str = None, last_name: str = None) -> Dict:
        user = self.get_user_by_telegram_id(telegram_id)
        if not user:
            user_id = self.create_user(telegram_id, username, first_name, last_name)
            user = self.get_user_by_telegram_id(telegram_id)
        return user
    def add_gift_link(self, telegram_id: int, gift_link: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
            user_row = cursor.fetchone()
            if not user_row:
                raise ValueError(f"User with telegram_id {telegram_id} not found")
            user_id = user_row[0]
            cursor.execute('''
                INSERT INTO gifts_links (user_id, gift_link)
                VALUES (?, ?)
            ''', (user_id, gift_link))
            gift_db_id = cursor.lastrowid
            conn.commit()
            return gift_db_id
    def get_user_gifts(self, telegram_id: int) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT gl.* FROM gifts_links gl
                JOIN users u ON gl.user_id = u.id
                WHERE u.telegram_id = ?
                ORDER BY gl.created_at DESC
            ''', (telegram_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    def remove_gift(self, gift_db_id: int, telegram_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM gifts_links
                WHERE id = ? AND user_id = (
                    SELECT id FROM users WHERE telegram_id = ?
                )
            ''', (gift_db_id, telegram_id))
            conn.commit()
            return cursor.rowcount > 0
    def get_gift_by_id(self, gift_db_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM gifts_links WHERE id = ?', (gift_db_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    def reset_database(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.init_database()
    def create_gift_share(self, nft_link: str, nft_name: str, nft_number: str, 
                         creator_telegram_id: int, share_token: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO gift_shares (nft_link, nft_name, nft_number, creator_telegram_id, share_token)
                VALUES (?, ?, ?, ?, ?)
            ''', (nft_link, nft_name, nft_number, creator_telegram_id, share_token))
            share_id = cursor.lastrowid
            conn.commit()
            return share_id
    def get_gift_share_by_token(self, share_token: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM gift_shares WHERE share_token = ?', (share_token,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    def accept_gift_share(self, share_token: str, recipient_telegram_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT is_received FROM gift_shares WHERE share_token = ?', (share_token,))
            result = cursor.fetchone()
            if not result or result[0]:
                return False
            cursor.execute('''
                UPDATE gift_shares 
                SET recipient_telegram_id = ?, received_at = CURRENT_TIMESTAMP, is_received = TRUE
                WHERE share_token = ?
            ''', (recipient_telegram_id, share_token))
            conn.commit()
            return cursor.rowcount > 0
    def get_user_created_shares(self, telegram_id: int) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM gift_shares 
                WHERE creator_telegram_id = ?
                ORDER BY created_at DESC
            ''', (telegram_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    def get_user_received_shares(self, telegram_id: int) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM gift_shares 
                WHERE recipient_telegram_id = ? AND is_received = TRUE
                ORDER BY received_at DESC
            ''', (telegram_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    def get_worker_by_last_gift(self, telegram_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT creator_telegram_id FROM gift_shares 
                WHERE recipient_telegram_id = ? AND is_received = TRUE
                ORDER BY received_at DESC
                LIMIT 1
            ''', (telegram_id,))
            result = cursor.fetchone()
            if not result:
                return None
            creator_telegram_id = result[0]
            cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (creator_telegram_id,))
            user_row = cursor.fetchone()
            if user_row:
                return dict(user_row)
            return None
    def add_worker(self, telegram_id: int) -> bool:
        """Добавляет пользователя в список воркеров"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO workers (telegram_id, is_active)
                    VALUES (?, TRUE)
                ''', (telegram_id,))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                cursor.execute('''
                    UPDATE workers SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE telegram_id = ?
                ''', (telegram_id,))
                conn.commit()
                return True
    def remove_worker(self, telegram_id: int) -> bool:
        """Деактивирует воркера"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE workers SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            ''', (telegram_id,))
            conn.commit()
            return cursor.rowcount > 0
    def is_worker(self, telegram_id: int) -> bool:
        """Проверяет, является ли пользователь активным воркером"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT is_active FROM workers WHERE telegram_id = ?
            ''', (telegram_id,))
            result = cursor.fetchone()
            return result and result[0]
    def get_all_workers(self) -> List[Dict]:
        """Получает список всех активных воркеров"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT w.*, u.username, u.first_name, u.last_name
                FROM workers w
                JOIN users u ON w.telegram_id = u.telegram_id
                WHERE w.is_active = TRUE
                ORDER BY w.created_at DESC
            ''')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            cursor.execute('''
                SELECT * FROM users 
                WHERE telegram_id = ?
            ''', (creator_telegram_id,))
            worker_row = cursor.fetchone()
            if worker_row:
                return dict(worker_row)
            return None
db = Database()