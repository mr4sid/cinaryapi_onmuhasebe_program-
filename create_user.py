import requests
import json
import logging
import os
from config import API_BASE_URL

# Logger kurulumu
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def create_initial_user():
    """
    API üzerinden başlangıç admin kullanıcısını oluşturur.
    """
    api_url = f"{API_BASE_URL}/dogrulama/register_temp"
    
    # Oluşturulacak kullanıcı bilgileri
    user_data = {
        "kullanici_adi": "admin3",
        "sifre": "755397",
        "yetki": "ADMIN"
    }

    try:
        response = requests.post(api_url, json=user_data)
        response.raise_for_status()  # HTTP hataları için istisna fırlatır
        
        response_data = response.json()
        if response_data.get("message") == "User created successfully":
            logger.info("Başlangıç admin kullanıcısı başarıyla oluşturuldu: admin/password")
            print("Başlangıç admin kullanıcısı başarıyla oluşturuldu: admin/password")
        else:
            logger.warning(f"Kullanıcı oluşturma isteği gönderildi, ancak beklenmeyen bir yanıt alındı: {response_data}")
            print(f"Uyarı: Kullanıcı oluşturma isteği gönderildi, ancak beklenmeyen bir yanıt alındı: {response_data}")

    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 409:
            logger.warning("Kullanıcı zaten mevcut. Admin hesabı oluşturulamadı.")
            print("Uyarı: Kullanıcı zaten mevcut. Admin hesabı oluşturulamadı.")
        else:
            logger.error(f"HTTP hatası oluştu: {http_err}")
            print(f"Hata: HTTP hatası oluştu: {http_err}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"API'ye bağlanılamadı. Lütfen sunucunun çalıştığından emin olun. Hata: {req_err}")
        print(f"Hata: API'ye bağlanılamadı. Lütfen sunucunun çalıştığından emin olun. Hata: {req_err}")
    except Exception as e:
        logger.error(f"Beklenmeyen bir hata oluştu: {e}")
        print(f"Hata: Beklenmeyen bir hata oluştu: {e}")

if __name__ == "__main__":
    create_initial_user()