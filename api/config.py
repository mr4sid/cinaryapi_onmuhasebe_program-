import os
from dotenv import load_dotenv
from datetime import timedelta

# Projenin kök dizininde .env dosyasını yükleyin
load_dotenv()

# JWT için gizli anahtar
# Ortam değişkeninden alın, yoksa varsayılan bir değer kullanın.
SECRET_KEY = os.getenv("SECRET_KEY", "gizli-anahtar-cok-gizli-kimse-bilmesin")

# Token için kullanılacak algoritma
ALGORITHM = "HS256"

# Token'ın geçerlilik süresi
ACCESS_TOKEN_EXPIRE_MINUTES = 30