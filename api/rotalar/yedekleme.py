import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from ..veritabani import get_db
from datetime import datetime
import subprocess # PostgreSQL komutlarını çalıştırmak için

router = APIRouter(prefix="/yedekleme", tags=["Veritabanı Yedekleme"])

# Ortam değişkenlerinden veritabanı bağlantı bilgilerini al
# Normalde bu bilgiler config dosyasından veya Docker secret/env'den gelmelidir.
# Güvenlik nedeniyle doğrudan kodda olmamalıdır.
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "admin")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "onmuhasebe_db")

# Yedeklemelerin saklanacağı dizin (uygulamanın kök dizininde 'backups' klasörü)
# Uygulamanın çalıştırıldığı dizine göre ayarlanmalıdır.
# Örneğin, projenin kök dizininde 'backups' adında bir klasör oluşturulabilir.
BACKUP_DIR = os.path.join(os.getcwd(), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True) # Dizin yoksa oluştur

@router.post("/backup", summary="Veritabanını Yedekle", status_code=status.HTTP_200_OK)
def create_db_backup(db: Session = Depends(get_db)):
    """
    Uygulamanın PostgreSQL veritabanını yedekler.
    Yedek dosyası sunucu tarafında belirlenen bir dizine kaydedilir.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{DB_NAME}_backup_{timestamp}.sql"
    backup_filepath = os.path.join(BACKUP_DIR, backup_filename)

    try:
        # pg_dump komutu ile yedekleme yap
        # Güvenlik Notu: Şifreyi doğrudan komutta geçmek yerine PGPASSWORD ortam değişkeni kullanılmalıdır.
        os.environ['PGPASSWORD'] = DB_PASSWORD
        command = [
            "pg_dump",
            "-h", DB_HOST,
            "-p", DB_PORT,
            "-U", DB_USER,
            "-F", "p", # Plain text format
            "-d", DB_NAME,
            "-f", backup_filepath
        ]
        
        # subprocess.run ile komutu çalıştır
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        # Hata kontrolü
        if result.stderr:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Yedekleme sırasında hata oluştu: {result.stderr}")

        return {"message": f"Veritabanı başarıyla yedeklendi: {backup_filename}", "filepath": backup_filepath}
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="pg_dump komutu bulunamadı. PostgreSQL client tools kurulu olduğundan ve PATH'inizde olduğundan emin olun.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Yedekleme komutu hatası: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Beklenmedik bir hata oluştu: {e}")
    finally:
        # PGPASSWORD ortam değişkenini temizle
        if 'PGPASSWORD' in os.environ:
            del os.environ['PGPASSWORD']


@router.post("/restore", summary="Veritabanını Geri Yükle", status_code=status.HTTP_200_OK)
def restore_db_backup(backup_file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Yüklenen yedek dosyasını kullanarak PostgreSQL veritabanını geri yükler.
    UYARI: Bu işlem mevcut veritabanı içeriğini SİLECEKTİR!
    """
    if not backup_file.filename.endswith(".sql"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sadece .sql uzantılı dosyalar kabul edilir.")

    # Yüklenen dosyayı geçici bir konuma kaydet
    temp_filepath = os.path.join(BACKUP_DIR, f"restore_temp_{backup_file.filename}")
    try:
        with open(temp_filepath, "wb") as buffer:
            buffer.write(backup_file.file.read())

        # pg_restore veya psql komutu ile geri yükleme yap
        # Not: psql -f ile SQL dosyası çalıştırıyoruz.
        # Güvenlik Notu: Şifreyi doğrudan komutta geçmek yerine PGPASSWORD ortam değişkeni kullanılmalıdır.
        os.environ['PGPASSWORD'] = DB_PASSWORD
        command = [
            "psql",
            "-h", DB_HOST,
            "-p", DB_PORT,
            "-U", DB_USER,
            "-d", DB_NAME,
            "-f", temp_filepath
        ]

        # subprocess.run ile komutu çalıştır
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        if result.stderr and "SET" not in result.stderr: # SET komutları normalde stderr'a yazılır, onları yoksay
             # Sadece gerçek hata mesajlarını döndür
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Geri yükleme sırasında hata oluştu: {result.stderr}")

        return {"message": f"Veritabanı başarıyla geri yüklendi: {backup_file.filename}"}
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="psql komutu bulunamadı. PostgreSQL client tools kurulu olduğundan ve PATH'inizde olduğundan emin olun.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Geri yükleme komutu hatası: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Beklenmedik bir hata oluştu: {e}")
    finally:
        # Geçici dosyayı ve ortam değişkenini temizle
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        if 'PGPASSWORD' in os.environ:
            del os.environ['PGPASSWORD']