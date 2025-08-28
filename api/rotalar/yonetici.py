# api/rotalar/yonetici.py
import os
import shutil
import subprocess
import logging
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from .. import semalar
from ..veritabani import get_db, Base

router = APIRouter(
    prefix="/admin",
    tags=["Yönetici İşlemleri"]
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BackupRequest(BaseModel):
    file_path: Optional[str] = None

class RestoreRequest(BaseModel):
    file_path: str

def run_backup_command(file_path: str) -> str:
    pg_bin_path = os.getenv("PG_BIN_PATH")
    pg_dump_command = None
    
    if pg_bin_path:
        logging.info(f"Ortam değişkeninden PG_BIN_PATH okundu: {pg_bin_path}")
        pg_dump_command = os.path.join(pg_bin_path, "pg_dump")
        # Değişiklik: Yolu tırnak içine al
        pg_dump_command = f'"{pg_dump_command}"'
        if not os.path.exists(os.path.join(pg_bin_path, "pg_dump.exe")):
            logging.warning(f"PG_BIN_PATH'de belirtilen yolda pg_dump bulunamadı: {pg_dump_command}")
            pg_dump_command = None
        else:
            logging.info(f"pg_dump komutu PG_BIN_PATH'de bulundu: {pg_dump_command}")
            
    if not pg_dump_command:
        logging.info("PG_BIN_PATH kullanılamadı. Sistem PATH'inde pg_dump aranıyor.")
        pg_dump_command = shutil.which("pg_dump")
        
    if not pg_dump_command:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Yedekleme komutu (pg_dump) bulunamadı. Lütfen PostgreSQL'in 'bin' dizinini "
                "sistem PATH'inize veya PG_BIN_PATH ortam değişkenine eklediğinizden emin olun."
            )
        )
        
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    
    # Değişiklik: Komutu string olarak birleştirip shell=True ile çalıştırın
    command_str = (
        f'"{pg_dump_command}" '
        f'--dbname=postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name} '
        f'--format=c '
        f'--file="{file_path}"'
    )
    
    try:
        result = subprocess.run(command_str, shell=True, check=True, capture_output=True, text=True)
        return f"Yedekleme başarıyla tamamlandı: {file_path}"
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Yedekleme komutu hatası: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Beklenmeyen bir hata oluştu: {e}")
    
def run_restore_command(file_path: str) -> str:
    pg_bin_path = os.getenv("PG_BIN_PATH")
    pg_restore_command = None
    psql_command_path = None
    
    if pg_bin_path:
        logging.info(f"Ortam değişkeninden PG_BIN_PATH okundu: {pg_bin_path}")
        pg_restore_command = os.path.join(pg_bin_path, "pg_restore")
        psql_command_path = os.path.join(pg_bin_path, "psql")
    
    if not pg_restore_command or not psql_command_path:
        logging.info("PG_BIN_PATH kullanılamadı. Sistem PATH'inde komutlar aranıyor.")
        pg_restore_command = shutil.which("pg_restore")
        psql_command_path = shutil.which("psql")

    if not pg_restore_command:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Geri yükleme komutu (pg_restore) bulunamadı. Lütfen PostgreSQL'in 'bin' dizinini "
                "sistem PATH'inize veya PG_BIN_PATH ortam değişkenine eklediğinizden emin olun."
            )
        )
    if not psql_command_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="psql komutu bulunamadı. Lütfen sistem PATH'inizi veya PG_BIN_PATH ortam değişkeninizi kontrol edin."
        )

    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")

    # Geçici olarak PGPASSWORD ortam değişkenini ayarlayın
    env_vars = os.environ.copy()
    env_vars["PGPASSWORD"] = db_password
    
    try:
        # Geri yükleme işlemi için DROP ve CREATE komutlarını çalıştırın.
        drop_db_command = [
            psql_command_path,
            f"--host={db_host}",
            f"--port={db_port}",
            f"--username={db_user}",
            "--dbname=postgres",
            f"--command=DROP DATABASE IF EXISTS \"{db_name}\" WITH (FORCE);"
        ]
        subprocess.run(drop_db_command, check=True, env=env_vars)

        create_db_command = [
            psql_command_path,
            f"--host={db_host}",
            f"--port={db_port}",
            f"--username={db_user}",
            "--dbname=postgres",
            f"--command=CREATE DATABASE \"{db_name}\";"
        ]
        subprocess.run(create_db_command, check=True, env=env_vars)

        # Geri yükleme komutunu çalıştırın.
        restore_command = [
            pg_restore_command,
            f"--dbname=postgresql://{db_user}@{db_host}:{db_port}/{db_name}",
            "--no-owner",
            file_path # <-- BU SATIR DÜZELTİLDİ: --clean parametresi kaldırıldı
        ]
        subprocess.run(restore_command, check=True, env=env_vars)

        return f"Veritabanı başarıyla geri yüklendi: {file_path}"
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Geri yükleme komutu hatası: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Beklenmeyen bir hata oluştu: {e}")

@router.post("/yedekle")
def yedekle(request: BackupRequest):
    """Veritabanını yedekler."""
    if not request.file_path:
        # Varsayılan bir yedekleme yolu oluşturun
        backup_dir = os.path.join(os.getcwd(), 'yedekler')
        os.makedirs(backup_dir, exist_ok=True)
        file_name = f"yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        file_path = os.path.join(backup_dir, file_name)
    else:
        file_path = request.file_path
    
    try:
        message = run_backup_command(file_path)
        return {"message": message, "file_path": file_path}
    except HTTPException as e:
        raise e

@router.post("/geri_yukle")
def geri_yukle(request: RestoreRequest):
    """Veritabanını geri yükler."""
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Belirtilen dosya bulunamadı: {request.file_path}")
    
    try:
        message = run_restore_command(request.file_path)
        return {"message": message}
    except HTTPException as e:
        raise e

@router.delete("/clear_all_data", status_code=status.HTTP_200_OK, summary="Tüm verileri temizle (Kullanıcılar Hariç)")
def clear_all_data(db: Session = Depends(get_db)):
    """
    Sistemdeki tüm verileri (Kullanıcılar hariç) siler.
    Bu işlem geri alınamaz! Sadece test amaçlı kullanılmalıdır.
    """
    try:
        # Silinecek tabloları bağımlılık sırasına göre manuel olarak listele
        tables_to_clear = [
            "fatura_kalemleri",
            "siparis_kalemleri",
            "stok_hareketleri",
            "cari_hareketler",
            "kasa_banka_hareketleri",
            "gelir_gider", 
            "faturalar",
            "siparisler",
            "stoklar",
            "musteriler",
            "tedarikciler",
            "kasalar_bankalar",
            "urun_birimleri",
            "urun_markalari",
            "urun_kategorileri",
            "urun_gruplari",
            "ulkeler",
            "gelir_siniflandirmalari",
            "gider_siniflandirmalari"
        ]
        
        metadata = Base.metadata
        
        # Tüm tabloları sırasıyla boşalt (truncate).
        # Bu yöntem, Foreign Key (Yabancı Anahtar) hatalarını da önler.
        # SQLAlchemy'nin `sorted_tables` özelliğini kullanarak doğru sırayı yakalayabiliriz.
        for table in reversed(metadata.sorted_tables):
            if table.name in tables_to_clear:
                db.execute(table.delete())
        
        # İşlemi kesinleştir
        db.commit()

        # Temizleme işleminden sonra varsayılan verileri yeniden oluştur
        logger.info("Varsayılan veriler yeniden oluşturuluyor...")
        
        # Varsayılan perakende müşteriyi ve genel tedarikçiyi ekle
        perakende_musteri = semalar.Musteri(ad="Perakende Müşteri", kod="PERAKENDE_MUSTERI", aktif=True)
        genel_tedarikci = semalar.Tedarikci(ad="Genel Tedarikçi", kod="GENEL_TEDARIKCI", aktif=True)
        db.add(perakende_musteri)
        db.add(genel_tedarikci)
        db.commit()
        db.refresh(perakende_musteri)
        db.refresh(genel_tedarikci)
        logger.info("Varsayılan 'Perakende Müşteri' ve 'Genel Tedarikçi' başarıyla eklendi.")

        # Varsayılan nakit kasayı ekle
        nakit_kasa = semalar.KasaBanka(
            hesap_adi="Nakit Kasa",
            kod="NAKİT_KASA",
            tip="KASA",
            bakiye=0.0,
            para_birimi="TL",
            aktif=True,
            varsayilan_odeme_turu="NAKİT"
        )
        db.add(nakit_kasa)
        db.commit()
        db.refresh(nakit_kasa)
        logger.info("Varsayılan 'NAKİT KASA' hesabı başarıyla eklendi.")

        return {"message": "Tüm veriler temizlendi ve varsayılan veriler yeniden oluşturuldu."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Veri temizleme sırasında hata oluştu: {e}")