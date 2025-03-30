import os
import subprocess
from datetime import datetime
from pathlib import Path
from config import settings
from utils.logger import logger

def create_backup():
    """Создание резервной копии базы данных"""
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"backup_{timestamp}.sql"
    
    try:
        # Создаем дамп базы данных
        cmd = [
            "pg_dump",
            "-h", settings.DB_HOST,
            "-p", str(settings.DB_PORT),
            "-U", settings.DB_USER,
            "-d", settings.DB_NAME,
            "-f", str(backup_file)
        ]
        
        # Устанавливаем переменную окружения для пароля
        env = os.environ.copy()
        env["PGPASSWORD"] = settings.DB_PASSWORD
        
        subprocess.run(cmd, env=env, check=True)
        logger.info(f"Backup created successfully: {backup_file}")
        
        # Сжимаем файл
        compressed_file = backup_file.with_suffix(".sql.gz")
        subprocess.run(["gzip", "-f", str(backup_file)], check=True)
        logger.info(f"Backup compressed: {compressed_file}")
        
        # Удаляем старые бэкапы (оставляем последние 7 дней)
        cleanup_old_backups(backup_dir)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error creating backup: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during backup: {e}")
        raise

def cleanup_old_backups(backup_dir):
    """Удаление старых резервных копий"""
    try:
        # Получаем список файлов бэкапов
        backup_files = list(backup_dir.glob("backup_*.sql.gz"))
        backup_files.sort(reverse=True)
        
        # Оставляем только последние 7 дней
        for old_file in backup_files[7:]:
            old_file.unlink()
            logger.info(f"Deleted old backup: {old_file}")
            
    except Exception as e:
        logger.error(f"Error cleaning up old backups: {e}")

if __name__ == "__main__":
    create_backup() 