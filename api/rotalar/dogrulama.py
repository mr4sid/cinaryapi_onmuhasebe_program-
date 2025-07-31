from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import modeller, semalar
from ..veritabani import get_db
from passlib.context import CryptContext # Yeni import

router = APIRouter(prefix="/dogrulama", tags=["Kimlik Doğrulama"])

# Şifre hash'leme bağlamını tanımla
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Şifreyi hash'lemek için yardımcı fonksiyon
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# Şifreyi doğrulamak için yardımcı fonksiyon
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

@router.post("/login", response_model=modeller.Token)
def authenticate_user(user_login: modeller.KullaniciLogin, db: Session = Depends(get_db)): # <-- BURASI DÜZELTİLDİ: modeller.UserLogin -> modeller.KullaniciLogin
    # Kullanıcı adı ile veritabanında kullanıcıyı bul
    user = db.query(semalar.Kullanici).filter(semalar.Kullanici.kullanici_adi == user_login.kullanici_adi).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Girilen şifreyi hash'lenmiş şifre ile doğrula
    if not verify_password(user_login.sifre, user.hashed_sifre):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Başarılı olursa basit bir token (şimdilik kullanıcı adını döndürelim)
    # Gerçek bir uygulamada burada JWT (JSON Web Token) oluşturulur
    return {"access_token": user.kullanici_adi, "token_type": "bearer"}

# Geçici kullanıcı oluşturma (GELİŞTİRME AMAÇLI, ÜRETİMDE KULLANILMAMALI!)
@router.post("/register_temp", response_model=modeller.KullaniciRead) # <-- modeller.UserRead -> modeller.KullaniciRead
def register_temporary_user(user_create: modeller.KullaniciCreate, db: Session = Depends(get_db)): # <-- modeller.UserCreate -> modeller.KullaniciCreate
    db_user = db.query(semalar.Kullanici).filter(semalar.Kullanici.kullanici_adi == user_create.kullanici_adi).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kullanıcı adı zaten mevcut")
    
    hashed_password = hash_password(user_create.sifre)
    db_user = semalar.Kullanici(
        kullanici_adi=user_create.kullanici_adi,
        hashed_sifre=hashed_password,
        aktif=True # Yeni kullanıcılar varsayılan olarak aktif
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user