from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

# Kendi modüllerimiz
from .. import semalar # semalar.py'den modelleri içe aktarıyoruz
from .. import modeller # Pydantic modellerini içe aktarıyoruz
from ..veritabani import get_db # veritabani.py'den get_db bağımlılığını içe aktarıyoruz

# -- Varsayılan Değerler --
def get_perakende_musteri_id_from_db(db: Session):
    # Gerçek uygulamada, veritabanından ID'si veya kodu 'PERAKENDE' olan müşteriyi bulmalısınız.
    # Örneğin: musteri = db.query(semalar.Musteri).filter(semalar.Musteri.kod == "PERAKENDE").first()
    # Şu an için basitçe ID'si 1 olan müşteriyi varsayıyoruz.
    musteri = db.query(semalar.Musteri).filter(semalar.Musteri.id == 1).first() 
    if musteri:
        return {"id": musteri.id}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perakende musteri bulunamadi.")

def get_genel_tedarikci_id_from_db(db: Session):
    # Gerçek uygulamada, veritabanından ID'si veya kodu 'GENEL' olan tedarikçiyi bulmalısınız.
    tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.id == 1).first() 
    if tedarikci:
        return {"id": tedarikci.id}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Genel tedarikci bulunamadi.")

def get_varsayilan_kasa_banka_from_db(db: Session, odeme_turu: str):
    # Ödeme türüne göre varsayılan kasa/banka hesabını veritabanından çek.
    # Örneğin, NAKIT için 'KASA' tipi bir hesap
    # KART için 'BANKA' tipi bir POS hesabı vb.
    # Şu an için basit bir eşleşme yapalım
    hesap = None
    if odeme_turu == "NAKİT":
        hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.tip == "KASA").first()
    elif odeme_turu == "KART":
        hesap = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.tip == "BANKA", semalar.KasaBanka.hesap_adi.like("%POS%")).first()
    else: # Diğer ödeme türleri için herhangi bir ilk hesabı döndürebiliriz
        hesap = db.query(semalar.KasaBanka).first()

    if hesap:
        return {"id": hesap.id, "hesap_adi": hesap.hesap_adi, "tip": hesap.tip}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Varsayılan kasa/banka hesabı bulunamadı: {odeme_turu}")

# -- Şirket Bilgileri --
def get_sirket_bilgileri_from_db(db: Session):
    # Gerçek uygulamada, veritabanından şirket bilgilerini çekeceksiniz.
    # Varsayılan olarak sadece bir şirket kaydı olduğu varsayılabilir.
    sirket = db.query(semalar.Sirket).first() # semalar.py'de Sirket modeli olmalı
    if sirket:
        return modeller.SirketBilgileri.model_validate(sirket) # Pydantic modeline dönüştür
    # Eğer Sirket tablosu yoksa veya boşsa, varsayılan bir değer döndürebiliriz.
    return modeller.SirketBilgileri(sirket_adi="Varsayılan Şirket Adı", adres="", telefon="", email="")

def update_sirket_bilgileri_in_db(db: Session, bilgiler: modeller.SirketBilgileriUpdate):
    # Gerçek uygulamada, şirket bilgilerini güncelleyeceksiniz.
    sirket = db.query(semalar.Sirket).first()
    if not sirket:
        # Sirket bilgisi yoksa, yeni bir tane oluştur
        sirket = semalar.Sirket(**bilgiler.model_dump())
        db.add(sirket)
        db.commit()
        db.refresh(sirket)
        return True, "Şirket bilgileri oluşturuldu."

    # Bilgileri güncelle
    for key, value in bilgiler.model_dump(exclude_unset=True).items():
        setattr(sirket, key, value)
    db.commit()
    db.refresh(sirket)
    return True, "Şirket bilgileri başarıyla güncellendi."

# -- Kullanıcı Doğrulama --
def authenticate_user_from_db(db: Session, user: modeller.KullaniciLogin):
    # Gerçek uygulamada, kullanıcı adı ve şifreyi doğrulamalısınız.
    # Şifre hash'leme ve saltlama kullanılmalıdır!
    # Örneğin: user_db = db.query(semalar.Kullanici).filter(semalar.Kullanici.kullanici_adi == user.username).first()
    # if user_db and user_db.hashed_password == hash_password(user.password): return user_db
    # Şu an için basit bir kontrol:
    if user.username == "admin" and user.password == "admin":
        # Semalar.Kullanici modeli API'de olması gereken
        # Bu kısım API'deki User modeline göre ayarlanacak.
        # Şimdilik sadece bir dict dönüyoruz.
        return {"id": 1, "username": "admin", "rol": "ADMIN"}
    return None


# -- Router Tanımlamaları --
router = APIRouter(
    prefix="/sistem",
    tags=["Sistem ve Varsayılanlar"]
)

@router.get("/varsayilan_kasa_banka/{odeme_turu}")
def get_varsayilan_kasa_banka_endpoint(odeme_turu: str, db: Session = Depends(get_db)):
    return get_varsayilan_kasa_banka_from_db(db, odeme_turu)

@router.get("/sirket/bilgiler", response_model=modeller.SirketBilgileri)
def get_sirket_bilgileri_endpoint(db: Session = Depends(get_db)):
    return get_sirket_bilgileri_from_db(db)

@router.put("/sirket/bilgiler")
def update_sirket_bilgileri_endpoint(bilgiler: modeller.SirketBilgileriUpdate, db: Session = Depends(get_db)):
    success, message = update_sirket_bilgileri_in_db(db, bilgiler)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}

@router.post("/auth/login")
def login_for_access_token(user: modeller.KullaniciLogin, db: Session = Depends(get_db)):
    authenticated_user = authenticate_user_from_db(db, user)
    if not authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Gerçek uygulamada burada JWT token oluşturulur ve döndürülür
    return {"access_token": "fake-jwt-token", "token_type": "bearer", "user": authenticated_user}

