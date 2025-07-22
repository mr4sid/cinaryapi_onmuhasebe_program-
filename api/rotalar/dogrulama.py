from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from .. import semalar # semalar.py'den SQLAlchemy modellerini içe aktarıyoruz
from .. import modeller # Pydantic modellerini içe aktarıyoruz
from ..veritabani import get_db # veritabani.py'den get_db bağımlılığını içe aktarıyoruz

router = APIRouter(
    prefix="/dogrulama",
    tags=["Kimlik Doğrulama"]
)

def authenticate_user(db: Session, user_login_data: modeller.KullaniciLogin):
    """
    Kullanıcı adı ve şifreyi doğrular.
    Gerçek uygulamada, bu fonksiyonun daha karmaşık bir doğrulama (örn: şifre hash'leme, veritabanı sorgusu) içermesi gerekir.
    """
    # Örnek Kullanıcı Doğrulama (GEÇİCİ VE GÜVENLİ DEĞİL!)
    # Gerçek uygulamada:
    # 1. Kullanıcıyı veritabanından kullanıcı adına göre çek.
    # 2. Çekilen kullanıcının hash'lenmiş şifresi ile girilen şifreyi doğrula.
    #    (örn: bcrypt.checkpw(password.encode('utf-8'), hashed_password))

    user_db = db.query(semalar.Kullanici).filter(semalar.Kullanici.kullanici_adi == user_login_data.username).first()

    if not user_db:
        return None # Kullanıcı bulunamadı

    # Şifre kontrolü (GEÇİCİ: gerçek uygulamada hash kontrolü olmalı)
    if user_login_data.password == user_db.sifre: # Varsayılan olarak semalar.py'de sifre alanı düz metin olarak tutuluyorsa
        # Kullanıcı bilgilerini bir dict olarak döndürüyoruz (UI tarafından beklendiği gibi)
        return {"id": user_db.id, "username": user_db.kullanici_adi, "rol": user_db.rol}

    return None # Şifre yanlış

@router.post("/login", response_model=modeller.KullaniciBilgileri) # response_model eklendi
def login_for_access_token(user_login_data: modeller.KullaniciLogin, db: Session = Depends(get_db)):
    """
    Kullanıcı adı ve şifre ile giriş yapar ve kullanıcı bilgilerini döndürür.
    """
    authenticated_user_info = authenticate_user(db, user_login_data)
    if not authenticated_user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Gerçek uygulamada burada JWT token oluşturulur ve döndürülür.
    # Şu an için UI'dan beklendiği gibi doğrudan kullanıcı bilgilerini döndürüyoruz.
    return authenticated_user_info