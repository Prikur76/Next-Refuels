#!/usr/bin/env python
import os
import socket
import sys
import time


def wait_for_db(host, port, timeout=60):
    """Ожидание доступности базы данных"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                if result == 0:
                    print(f"✅ Database {host}:{port} is available")
                    return True
        except Exception:
            pass

        print("⏳ Waiting for database...")
        time.sleep(2)

    print(f"❌ Database not available after {timeout} seconds")
    return False


if __name__ == "__main__":
    db_host = os.getenv("POSTGRES_HOST", "postgres")
    db_port = int(os.getenv("POSTGRES_PORT", "5432"))

    if not wait_for_db(db_host, db_port):
        sys.exit(1)
