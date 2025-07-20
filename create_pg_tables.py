import psycopg2
from veritabani import OnMuhasebe # Güncellediğimiz veritabani.py dosyasını import ediyoruz

# Adım 1'de oluşturduğunuz PostgreSQL bağlantı bilgilerinizi girin
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

        # OnMuhasebe sınıfından bir örnek oluştur (sadece metotlarını kullanmak için)
        db_manager = OnMuhasebe()
        
        # create_tables metodunu çağırarak tabloları oluştur
        db_manager.create_tables(cursor)
        
        # Değişiklikleri kaydet
        conn.commit()
        print("Tüm tablolar PostgreSQL veritabanında başarıyla oluşturuldu!")

    except psycopg2.Error as e:
        print(f"Veritabanı hatası: {e}")
        if conn:
            conn.rollback() # Hata durumunda işlemi geri al
    finally:
        if conn:
            cursor.close()
            conn.close()
            print("PostgreSQL bağlantısı kapatıldı.")

if __name__ == "__main__":
    main()