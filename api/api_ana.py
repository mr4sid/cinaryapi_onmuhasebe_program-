from fastapi import FastAPI
from .veritabani import engine, Base
# Tüm rotaları import ediyoruz
from .rotalar import musteriler, tedarikciler, stoklar, nitelikler, faturalar, siparisler, kasalar_bankalar, cari_hareketler, gelir_gider
# Veritabanı tablolarını (eğer yoksa) oluşturur. Bu satır önemlidir.
Base.metadata.create_all(bind=engine)

# FastAPI uygulamasını başlat
app = FastAPI(title="Ön Muhasebe API")

# Tüm rotaları uygulamaya dahil et
app.include_router(musteriler.router)
app.include_router(tedarikciler.router)
app.include_router(stoklar.router)
app.include_router(nitelikler.router)
app.include_router(faturalar.router)
app.include_router(siparisler.router)
app.include_router(kasalar_bankalar.router) 
app.include_router(cari_hareketler.router)
app.include_router(gelir_gider.router)
# Ana ("/") adrese bir istek geldiğinde bu fonksiyon çalışacak
@app.get("/")
def read_root():
    return {"message": "Ön Muhasebe API'sine hoş geldiniz!"}