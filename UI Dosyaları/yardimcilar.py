import locale
from datetime import datetime
import calendar

# PySide6 tabanlı UI bileşenleri için gerekli import'lar
from PySide6.QtWidgets import QDialog, QVBoxLayout, QCalendarWidget, QPushButton, QLineEdit, QMessageBox
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

def normalize_turkish_chars(text):
    """Türkçe karakterleri İngilizce eşdeğerlerine dönüştürür."""
    if not isinstance(text, str):
        return text
    text = text.replace('ı', 'i').replace('İ', 'I')
    text = text.replace('ş', 's').replace('Ş', 'S')
    text = text.replace('ğ', 'g').replace('Ğ', 'G')
    text = text.replace('ç', 'c').replace('Ç', 'C')
    text = text.replace('ö', 'o').replace('Ö', 'O')
    text = text.replace('ü', 'u').replace('Ü', 'U')
    return text

class DatePickerDialog(QDialog):
    date_selected = Signal(str) # Seçilen tarihi string olarak yayacak sinyal

    def __init__(self, parent=None, initial_date=None):
        super().__init__(parent)
        self.setWindowTitle("Tarih Seç")
        self.setGeometry(100, 100, 300, 250)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint) # Yardım butonunu kaldır

        self.layout = QVBoxLayout(self)

        self.calendar = QCalendarWidget(self)
        self.layout.addWidget(self.calendar)

        if initial_date:
            try:
                # 'yyyy-MM-dd' formatında gelen string'i QDate objesine çevir
                qdate_initial = QDate.fromString(initial_date, "yyyy-MM-dd")
                self.calendar.setSelectedDate(qdate_initial)
            except Exception as e:
                print(f"Hata: Geçersiz başlangıç tarihi formatı. {initial_date} - {e}")
                # Varsayılan olarak bugünün tarihini ayarla
                self.calendar.setSelectedDate(QDate.currentDate())
        else:
            self.calendar.setSelectedDate(QDate.currentDate()) # Başlangıç tarihi yoksa bugünü seç

        # Takvimde bir tarihe tıklamak için bir slot bağlıyoruz.
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
        super().accept() # QDialog'un kabul metodu çağrılır.

# Yeni ve merkezi sayısal giriş formatlama/doğrulama fonksiyonu
def format_and_validate_numeric_input(line_edit, app_instance=None):
    """
    QLineEdit içindeki sayısal değeri formatlar (örn. 1.000,00) ve doğrular.
    app_instance: QMessageBox için ana uygulama objesi, hata mesajı göstermek için.
    """
    current_text = line_edit.text().strip()
    if not current_text:
        line_edit.setText("0,00")
        return

    # Türkçe formatı İngilizce formata çevir (virgülü noktaya, binlik ayıracı kaldır)
    processed_text = current_text.replace(".", "").replace(",", ".")

    try:
        value = float(processed_text)
        # Locale ayarları kullanarak formatla
        formatted_value = locale.format_string("%.2f", value, grouping=True)
        line_edit.setText(formatted_value)
    except ValueError:
        # Geçersiz giriş durumunda uyarı ve varsayılan değer
        if app_instance:
            QMessageBox.warning(app_instance, "Geçersiz Giriş", "Lütfen geçerli bir sayısal değer girin.")
        else:
            print(f"UYARI: Geçersiz sayısal giriş algılandı: '{current_text}'")
        line_edit.setText("0,00")
