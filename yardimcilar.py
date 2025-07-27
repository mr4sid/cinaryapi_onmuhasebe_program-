# yardimcilar.py dosyasının içeriği 
import locale
from datetime import datetime
import calendar

# PySide6 tabanlı UI bileşenleri için gerekli import'lar
from PySide6.QtWidgets import QDialog, QVBoxLayout, QCalendarWidget, QPushButton, QLineEdit
from PySide6.QtCore import QDate, Signal, Slot, Qt
from PySide6.QtGui import QDoubleValidator # Sayısal giriş doğrulaması için

# Locale ayarını uygulamanın en başında bir kez yapıyoruz.
def setup_locale():
    """Sistem dil ayarını Türkçe olarak ayarlar."""
    try:
        locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.1254')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'tr_TR')
            except locale.Error:
                try:
                    locale.setlocale(locale.LC_ALL, 'tr_TR.utf8')
                except locale.Error:
                    print("UYARI: Türkçe locale (tr_TR) bulunamadı. Varsayılan formatlama kullanılacak.")

# Uygulama başladığında locale ayarını yap
setup_locale()

# NOT: sort_treeview_column fonksiyonu PySide6'da QTreeWidget'ın kendi sıralama özelliği (setSortingEnabled)
# ve sortByColumn metodu kullanılacağı için artık bu dosyada tutulmayacaktır.
# Benzer şekilde, Tkinter'a özgü numeric_input ve date_entry fonksiyonları da kaldırılmıştır.

def normalize_turkish_chars(text):
    """
    Metindeki Türkçe özel karakterleri İngilizce karşılıklarına dönüştürür.
    Örn: 'ŞİMŞEK' -> 'SIMSEK', 'çınar' -> 'cinar'
    """
    if not isinstance(text, str):
        return text # String değilse olduğu gibi döndür (None, int, float vb.)
    
    text = text.lower() # Aramayı küçük harfe duyarsız hale getirmek için
    replacements = {
        'ş': 's',
        'ı': 'i',
        'ç': 'c',
        'ğ': 'g',
        'ö': 'o',
        'ü': 'u',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def safe_float(value):
    """
    Verilen değeri güvenli bir şekilde float'a dönüştürür.
    Geçersiz girişlerde 0.0 döndürür.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            # Türkçe ondalık ayracı (virgül) kullanarak dönüştürme
            return float(value.replace('.', '').replace(',', '.'))
        except ValueError:
            return 0.0
    return 0.0

def format_numeric_text(value, decimals=2):
    """
    Sayısal değeri Türkçe para birimi formatına dönüştürür.
    Örnek: 1234.56 -> 1.234,56
    """
    if not isinstance(value, (int, float)):
        # float'a güvenli dönüşüm yapalım
        value = safe_float(value)

    # locale.format_string kullanmak daha iyi ama bazı sistemlerde locale sorunu yaratıyor.
    # Alternatif olarak f-string ile formatlayıp virgül/nokta değişimi yapabiliriz.
    try:
        # Önce İngiliz formatında float olarak al, sonra ondalık basamakları ayarla
        formatted_value = f"{value:,.{decimals}f}"
        # İngilizce formatı (nokta ondalık, virgül binlik) Türkçeye çevir
        formatted_value = formatted_value.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted_value
    except (ValueError, TypeError):
        return "0,00"

class DatePickerDialog(QDialog):
    # Seçilen tarihi dışarıya bildirmek için bir sinyal tanımlıyoruz.
    # Bu sinyal, PySide6'daki QLineEdit'e veya başka bir widget'a bağlanabilir.
    date_selected = Signal(str)

    def __init__(self, parent=None, initial_date_str=None):
        super().__init__(parent)
        self.setWindowTitle("Tarih Seç")
        self.setModal(True) # Diyaloğu modal yapar (ana pencereyi engeller)
        self.setFixedSize(300, 300) # Diyalog penceresinin sabit boyutu

        self.layout = QVBoxLayout(self) # Ana layout

        self.calendar = QCalendarWidget(self) # PySide6 takvim widget'ı
        self.layout.addWidget(self.calendar)

        # Başlangıç tarihini ayarla
        if initial_date_str:
            try:
                dt_obj = datetime.strptime(initial_date_str, '%Y-%m-%d')
                self.calendar.setSelectedDate(QDate(dt_obj.year, dt_obj.month, dt_obj.day))
            except ValueError:
                # Geçersiz format ise varsayılan bugünün tarihi veya kalendarın varsayılanı kalır.
                pass

        # Takvimde bir tarih tıklandığında (clicked sinyali) veya "Seç" butonuna basıldığında
        # tarihi yakalamak için bir slot bağlıyoruz.
        self.calendar.clicked.connect(self._on_date_clicked)

        self.select_button = QPushButton("Seç", self) # Seç butonu
        self.layout.addWidget(self.select_button)
        # Seç butonuna tıklandığında diyalogu kabul ederek kapat (accept() metoduyla)
        self.select_button.clicked.connect(self.accept)

        self.selected_final_date_str = None # Seçilen nihai tarihi tutacak değişken

        # Diyalog başlatıldığında, halihazırda seçili olan tarihi al.
        self.selected_final_date_str = self.calendar.selectedDate().toString("yyyy-MM-dd")

    @Slot(QDate) # Bir QDate objesi alacağını belirtir
    def _on_date_clicked(self, date_obj):
        """Takvimde bir tarihe tıklandığında çağrılır."""
        self.selected_final_date_str = date_obj.toString("yyyy-MM-dd")

    def accept(self):
        """Diyalog "Kabul Et" (Accept) ile kapatıldığında çağrılır."""
        if self.selected_final_date_str:
            # Seçilen tarihi bir sinyal olarak dışarıya yay.
            # Bu sinyal, çağıran PySide6 penceresindeki QLineEdit'e bağlanacaktır.
            self.date_selected.emit(self.selected_final_date_str)
        super().accept() # QDialog'un kendi accept metodunu çağırır.

    def reject(self):
        """Diyalog "İptal" (Reject) ile kapatıldığında çağrılır."""
        self.selected_final_date_str = None # İptal edilirse tarihi sıfırla
        super().reject() # QDialog'un kendi reject metodunu çağırır