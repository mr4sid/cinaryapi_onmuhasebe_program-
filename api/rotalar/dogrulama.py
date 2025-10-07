# api/rotalar/dogrulama.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

# Model Tutarlılığı: semalar artık sorgularda kullanılmadığı için kaldırıldı.
from .. import modeller
from ..veritabani import get_db
from ..guvenlik import create_access_token, verify_password, get_password_hash
from ..config import ACCESS_TOKEN_EXPIRE_MINUTES
from ..api_servisler import create_initial_data

router = APIRouter(prefix="/dogrulama", tags=["Kimlik Doğrulama"])

@router.post("/login", response_model=modeller.Token)
def authenticate_user(user_login: modeller.KullaniciLogin, db: Session = Depends(get_db)):
    # --- Hata Ayıklama Kodları Başlangıcı ---
    print(f"\n--- GİRİŞ DENEMESİ ---")
    print(f"Gelen kullanıcı adı: '{user_login.kullanici_adi}'")
    print(f"Gelen şifre: '{user_login.sifre}'")
    
    # DÜZELTİLDİ: Model Tutarlılığı - Sorgularda semalar.Kullanici yerine modeller.Kullanici kullanıldı.
    user = db.query(modeller.Kullanici).filter(modeller.Kullanici.kullanici_adi == user_login.kullanici_adi).first()

    if not user:
        print(">>> HATA: Veritabanında bu kullanıcı adı bulunamadı!")
        print("------------------------\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    print(f"Veritabanında bulunan kullanıcı: '{user.kullanici_adi}'")
    print(f"Veritabanındaki şifre hash'i: '{user.sifre_hash}'")
    
    is_password_correct = verify_password(user_login.sifre, user.sifre_hash)
    print(f">>> Şifre doğrulama sonucu: {is_password_correct}")

    if not is_password_correct:
        print(">>> HATA: Şifreler EŞLEŞMEDİ!")
        print("------------------------\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    print(">>> KİMLİK DOĞRULAMA BAŞARILI!")
    print("------------------------\n")
    # --- Hata Ayıklama Kodları Sonu ---
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.kullanici_adi}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer", "kullanici_id": user.id}

@router.post("/register", response_model=modeller.KullaniciRead)
def register_user(user_create: modeller.KullaniciCreate, db: Session = Depends(get_db)):
    # DÜZELTİLDİ: Model Tutarlılığı - Sorgularda semalar.Kullanici yerine modeller.Kullanici kullanıldı.
    db_user = db.query(modeller.Kullanici).filter(modeller.Kullanici.kullanici_adi == user_create.kullanici_adi).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kullanıcı adı zaten mevcut.")
    
    hashed_password = get_password_hash(user_create.sifre)
    
    # DÜZELTİLDİ: Model Tutarlılığı - Nesne oluşturmada semalar.Kullanici yerine modeller.Kullanici kullanıldı.
    db_user = modeller.Kullanici(
        kullanici_adi=user_create.kullanici_adi,
        sifre_hash=hashed_password,
        ad=user_create.ad,
        soyad=user_create.soyad,
        email=user_create.email,
        telefon=user_create.telefon,
        rol=user_create.rol
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # create_initial_data fonksiyonu, yeni kullanıcı için başlangıç verilerini oluşturuyor.
    create_initial_data(db=db, kullanici_id=db_user.id)
    
    return modeller.KullaniciRead.model_validate(db_user, from_attributes=True)