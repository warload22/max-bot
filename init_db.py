#!/usr/bin/env python3
from app.core.database import init_local_db

if __name__ == "__main__":
    init_local_db()
    print("Инициализация завершена.")
