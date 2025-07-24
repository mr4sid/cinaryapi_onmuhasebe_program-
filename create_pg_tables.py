# create_pg_tables.py dosyasının TAMAMI
import psycopg2
# api.veritabani'ndan Base ve engine'i import ediyoruz
from api.veritabani import Base, engine 

# Adım 1'de oluşturduğunuz PostgreSQL bağlantı bilgilerinizi girin
# Bu bilgiler zaten api/veritabani.py içinde tanımlı, ancak PostgreSQL bağlantısı için tekrar tanımlanabilir
DB_NAME = "on_muhasebe_prod"
DB_USER = "muhasebe_user"
DB_PASS = "755397.mAmi"  # <-- Şifre Satırı
DB_HOST = "localhost"
DB_PORT = "5432"

def main():
    conn = None
    try:
        # PostgreSQL'e bağlan
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()
        print("PostgreSQL veritabanına başarıyla bağlanıldı.")

        # TÜM TABLOLARI SİL (ÖNEMLİ: Mevcut tüm veriler silinecektir!)
        Base.metadata.drop_all(bind=engine)
        print("Mevcut tüm tablolar silindi.")

        # TÜM TABLOLARI YENİDEN OLUŞTUR
        Base.metadata.create_all(bind=engine)
        print("Tüm tablolar PostgreSQL veritabanında başarıyla oluşturuldu!")

        # Değişiklikleri kaydet (bu örnekte gerekmez ama alışkanlık olarak kalsın)
        # conn.commit() 

    except psycopg2.Error as e:
        print(f"Veritabanı hatası: {e}")
        if conn:
            conn.rollback() # Hata durumunda işlemi geri al
    except Exception as e:
        print(f"Genel hata: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()
            print("PostgreSQL bağlantısı kapatıldı.")

if __name__ == "__main__":
    main()