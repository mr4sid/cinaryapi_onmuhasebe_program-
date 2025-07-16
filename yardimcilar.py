# yardimcilar.py dosyasının içeriği
import locale
import tkinter as tk
from tkinter import ttk, messagebox  
from tkinter import messagebox 
from datetime import datetime 
import re
import calendar
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

def sort_treeview_column(tree, col, reverse):
    l = [(tree.set(k, col), k) for k in tree.get_children('')]
    try:
        # Sayısal sütunlar için sayısal sıralama
        l.sort(key=lambda t: float(t[0].replace('.', '').replace(',', '.')), reverse=reverse)
    except ValueError:
        # Metin sütunları için alfabetik sıralama
        l.sort(key=lambda t: t[0].lower(), reverse=reverse)

    for index, (val, k) in enumerate(l):
        tree.move(k, '', index)
    tree.heading(col, command=lambda: sort_treeview_column(tree, col, not reverse))

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

def validate_numeric_input(new_value_if_allowed, inserted_char, allow_negative, decimal_places, max_value=None):
    """
    Sayısal giriş alanları için karakter bazında doğrulama yapar.
    - P (new_value_if_allowed): Girişin yeni değeri (string).
    - S (inserted_char): Yeni girilen karakter (silme tuşu için boş string olabilir).
    - allow_negative: Negatif değerlere izin verilip verilmediği (boolean).
    - decimal_places: Ondalık basamak sayısı (integer).
    - max_value: Maksimum izin verilen sayısal değer (örneğin yüzde için 100). None ise sınırsız.
    """
    # print(f"DEBUG_VALIDATE: P='{new_value_if_allowed}', S='{inserted_char}'") # Debugging için

    # 1. Eğer yeni değer boşsa (tüm metin silindi veya seçili metin silindi)
    if not new_value_if_allowed.strip():
        # print("DEBUG_VALIDATE: Empty value, returning True")
        return True

    # 2. Eğer S boş stringse (genellikle silme veya yapıştırma)
    if inserted_char == '':
        try:
            # Yeni değerin float'a çevrilebilir olduğunu kontrol et
            float(new_value_if_allowed.replace(',', '.'))
            # print("DEBUG_VALIDATE: Backspace/Paste - Value is convertible, returning True")
            return True
        except ValueError:
            # Eğer silme sonrası geçersiz bir sayı kalıyorsa (örn: "12,," gibi)
            # print("DEBUG_VALIDATE: Backspace/Paste - Value is NOT convertible, returning False")
            return False
        except Exception as e:
            # print(f"DEBUG_VALIDATE: Backspace/Paste - Unexpected error: {e}, returning False")
            return False

    # 3. Eğer sadece eksi işaretiyse ve negatif sayılara izin veriliyorsa
    if new_value_if_allowed == '-' and allow_negative:
        # print("DEBUG_VALIDATE: Only '-' allowed, returning True")
        return True

    # 4. Rakam kontrolü
    if inserted_char.isdigit():
        # Eğer değer eksi işaretiyle başlıyor ve birden fazla eksi işareti varsa engelle
        if new_value_if_allowed.startswith('-') and new_value_if_allowed.count('-') > 1:
            # print("DEBUG_VALIDATE: Multiple '-' returning False")
            return False 
        
        # Eğer virgülden sonra maksimum ondalık basamak aşıldıysa engelle
        if ',' in new_value_if_allowed:
            if len(new_value_if_allowed.split(',')[-1]) > decimal_places:
                # print("DEBUG_VALIDATE: Decimal places exceeded, returning False")
                return False
        
        # Değerin maksimum sınırı (max_value) kontrolü (sadece yüzde için anlamlı olabilir)
        if max_value is not None:
            try:
                temp_float_value = float(new_value_if_allowed.replace(',', '.'))
                if temp_float_value > max_value:
                    # Bu durumda kullanıcının 101 girmesini engellemek için False dönebiliriz.
                    # Ancak bu, 100 girmesine de izin vermeyebilir (1'i engeller).
                    # Bu nedenle, validatecommand'da kesinlikle engellemek yerine FocusOut'ta mesaj vermek daha iyi.
                    pass 
            except ValueError:
                pass # Geçici olarak float'a çevrilemezse hata yok
        
        # print("DEBUG_VALIDATE: Digit entered, returning True")
        return True

    # 5. Virgül (ondalık ayıracı) kontrolü
    elif inserted_char == ',':
        # Yeni değerde zaten başka bir virgül varsa VEYA
        # Virgülden sonra ondalık basamaklara izin verilmiyorsa (decimal_places == 0) VEYA
        # Boşken virgül giriliyorsa (örn: ',123') VEYA
        # Sadece eksi varken virgül ekleniyorsa (örn: '-,')
        if new_value_if_allowed.count(',') > 1 or \
           (decimal_places == 0) or \
           new_value_if_allowed.strip() == ',' or \
           new_value_if_allowed == '-,' :
            # print("DEBUG_VALIDATE: Invalid ',' usage, returning False")
            return False # Geçersiz virgül kullanımı
        # print("DEBUG_VALIDATE: ',' entered, returning True")
        return True

    # 6. Eksi işareti kontrolü (Sadece başta ve bir kez)
    elif inserted_char == '-':
        if allow_negative and new_value_if_allowed.startswith('-') and new_value_if_allowed.count('-') <= 1:
            # print("DEBUG_VALIDATE: Valid '-' usage, returning True")
            return True
        # print("DEBUG_VALIDATE: Invalid '-' usage, returning False")
        return False

    # 7. Nokta girişi doğrudan reddedilir (Türkçe ondalık için virgül kullanıyoruz)
    elif inserted_char == '.':
        # print("DEBUG_VALIDATE: '.' is rejected, returning False")
        return False

    # 8. Diğer tüm karakterleri engelle (Örn: harf, sembol)
    else:
        # print(f"DEBUG_VALIDATE: Other char '{inserted_char}', returning False")
        return False


def format_on_focus_out(sv_variable, decimal_places):
    """
    Sayısal giriş alanlarındaki değeri odak kaybedildiğinde formatlar.
    Geçersiz değerler 0,00 olarak ayarlanır.
    Bu fonksiyon, StringVar'a bağlı Entry'ler için kullanılır.
    """
    value_str = sv_variable.get().strip()

    # Eğer değer boş, sadece '-', ',', '-,', ',-' gibi geçersiz başlangıç değerleriyse,
    # doğrudan varsayılan sıfır formatına ayarla ve çık.
    if not value_str or value_str in ['-', ',', '-,', ',-']:
        sv_variable.set(f"0,{str('0' * decimal_places)}" if decimal_places > 0 else "0")
        return

    try:
        # Önce binlik ayıracı olabilecek noktaları kaldır, sonra virgülü ondalık noktaya çevir
        cleaned_value_str = value_str.replace('.', '').replace(',', '.')
        
        # Eğer temizlenmiş string float'a çevrilemiyorsa ValueError fırlatır.
        float_value = float(cleaned_value_str)

        # Ondalık basamak sayısına göre formatla
        formatted_value_raw = f"{{:.{decimal_places}f}}".format(float_value)

        # Türkçe format için noktayı virgüle çevir
        formatted_value_final = formatted_value_raw.replace('.', ',')
        
        sv_variable.set(formatted_value_final)
    except ValueError:
        # Eğer float'a çevirme hatası olursa (yani sayısal olmayan bir girişse),
        # alanı 0.00 olarak sıfırla.
        sv_variable.set(f"0,{str('0' * decimal_places)}" if decimal_places > 0 else "0")
    except Exception as e:
        # Diğer beklenmeyen hatalar için
        print(f"Formatlama sırasında beklenmeyen hata: {e}")
        sv_variable.set(f"0,{str('0' * decimal_places)}" if decimal_places > 0 else "0")

def setup_numeric_entry(app, entry_widget, allow_negative=False, decimal_places=0, initial_value_string="0", max_value=None):
    """
    Sayısal giriş alanları için karakter bazında doğrulama ve varsayılan değer ataması yapar.
    FocusOut olayına bağlama YAPMAZ.
    """
    # Varsayılan değeri ayarla
    if not entry_widget.get().strip() and initial_value_string is not None:
        entry_widget.insert(0, initial_value_string.replace('.', ',')) # Virgül ile insert et

    vcmd = (entry_widget.register(lambda P, S: validate_numeric_input_generic(P, S, allow_negative, max_value)), '%P', '%S')
    entry_widget.config(validate="key", validatecommand=vcmd)

def validate_numeric_input_generic(new_value_if_allowed, inserted_char, allow_negative=False, max_value=None): # accepted_chars kaldırıldı
    """
    Sayısal girişler için genel doğrulama fonksiyonu.
    Girişin geçerli bir sayı (tam sayı veya ondalıklı) olup olmadığını kontrol eder.
    Virgül (,) ondalık ayıracı olarak kabul edilir.
    max_value: Maksimum izin verilen sayısal değer (örn. yüzde için 100). None ise sınırsız.
    """
    if not new_value_if_allowed.strip():
        return True # Boş girişe izin ver

    # Eğer özel bir karakter deseni belirtilmişse, onu kullan
    # Bu özellik artık bu fonksiyonda kullanılmıyor, çünkü sayısal doğrulama için genel kuralı uyguluyoruz.
    # if accepted_chars:
    #     import re
    #     if not re.match(accepted_chars, new_value_if_allowed):
    #         return False

    # Eksi işareti kontrolü
    if inserted_char == '-':
        if allow_negative and new_value_if_allowed == '-' and new_value_if_allowed.count('-') <= 1:
            return True
        return False # Geçersiz eksi işareti

    # Virgül kontrolü
    if inserted_char == ',':
        # Zaten bir virgül varsa veya boşken virgül giriliyorsa izin verme
        if ',' in new_value_if_allowed[:-1] or new_value_if_allowed == ',':
            return False
        return True # Virgül kabul

    # Rakam veya silme işlemiyse kabul
    if inserted_char.isdigit() or inserted_char == '': 
        try:
            # Geçerli bir sayıya dönüşüp dönüşmediğini kontrol et
            test_value = float(new_value_if_allowed.replace(',', '.'))

            if max_value is not None and test_value > max_value:
                return False 

            return True
        except ValueError:
            return False # Geçersiz sayı formatı
    
    # Diğer tüm karakterleri engelle
    return False

def format_on_focus_out_numeric_generic(entry_widget, decimal_places=0):
    """
    Sayısal giriş alanının içeriğini, odak kaybedildiğinde (FocusOut) temizler ve formatlar.
    StringVar'lar ile çalışacak şekilde güncellendi.
    """
    current_value_str = entry_widget.get().strip()

    if not current_value_str or current_value_str == '-' or current_value_str == ',':
        formatted_value = f"0,{str('0' * decimal_places)}" if decimal_places > 0 else "0"
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, formatted_value)
        return

    try:
        # Virgülü noktaya çevirerek float'a dönüştür
        value_float = float(current_value_str.replace(',', '.'))
        # İstenen ondalık basamak sayısına göre formatla
        formatted_value_str = f"{{:.{decimal_places}f}}".format(value_float)
        # Noktayı tekrar virgüle çevir
        final_display_value = formatted_value_str.replace('.', ',')

        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, final_display_value)
    except ValueError:
        # Geçersiz bir değer girildiyse sıfırla
        formatted_value = f"0,{str('0' * decimal_places)}" if decimal_places > 0 else "0"
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, formatted_value)
    except Exception as e:
        print(f"Hata: format_on_focus_out_numeric_generic - {e}")
        # Beklenmeyen hata durumunda da sıfırla
        formatted_value = f"0,{str('0' * decimal_places)}" if decimal_places > 0 else "0"
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, formatted_value)


def setup_date_entry(parent_app, entry_widget):
    """
    Tarih giriş alanı için otomatik tamamlama ve tarih seçici butonu bağlar.
    """
    # Otomatik tarih tamamlama (YYYY-MM-DD formatında)
    def auto_format_date(event):
        current_text = entry_widget.get()
        if event.keysym == "BackSpace" or event.keysym == "Delete":
            return # Silme işlemlerinde formatlamayı atla

        # Rakam girildikçe otomatik olarak tire ekle
        if current_text and current_text[-1].isdigit():
            if len(current_text) == 4 or len(current_text) == 7:
                entry_widget.insert(tk.END, '-')

    entry_widget.bind("<KeyRelease>", auto_format_date)
    
    # Geçersiz tarih formatı girildiğinde uyarı ve düzeltme
    def validate_date_on_focus_out(event):
        date_str = entry_widget.get()
        if date_str:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                messagebox.showwarning("Tarih Hatası", "Geçersiz tarih formatı. Lütfen YYYY-AA-GG olarak giriniz (örn: 2023-12-31).", parent=parent_app)
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, datetime.now().strftime('%Y-%m-%d')) # Hatalıysa bugünü varsayılan yap
    
    entry_widget.bind("<FocusOut>", validate_date_on_focus_out)

class DatePickerDialog(tk.Toplevel):
    def __init__(self, parent, entry_widget):
        super().__init__(parent)
        self.entry_widget = entry_widget
        self.title("Tarih Seç")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.update_idletasks()
        x = parent.winfo_x() + entry_widget.winfo_x()
        y = parent.winfo_y() + entry_widget.winfo_y() + entry_widget.winfo_height() + 5
        self.geometry(f"+{x}+{y}")

        self.selected_date = None
        self.year = datetime.now().year
        self.month = datetime.now().month

        # Türkçe ay isimleri listesi ekle
        self.turkish_month_names = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                                    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

        self._create_widgets()
        self._show_calendar()

    def _create_widgets(self):
        # Ay ve Yıl Navigasyon Çerçevesi
        nav_frame = ttk.Frame(self)
        nav_frame.pack(pady=5)

        ttk.Button(nav_frame, text="<", command=self._prev_month).pack(side=tk.LEFT, padx=2)
        self.month_year_label = ttk.Label(nav_frame, text="", font=("Segoe UI", 10, "bold"))
        self.month_year_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(nav_frame, text=">", command=self._next_month).pack(side=tk.LEFT, padx=2)

        # Takvim Grid Çerçevesi
        self.calendar_frame = ttk.Frame(self)
        self.calendar_frame.pack(padx=10, pady=5)

        # Haftanın günleri başlıkları (Türkçe)
        weekdays = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        for i, day in enumerate(weekdays):
            ttk.Label(self.calendar_frame, text=day, font=("Segoe UI", 8, "bold"), anchor=tk.CENTER).grid(row=0, column=i, padx=5, pady=2)

    def _show_calendar(self):
        # Önceki günleri temizle
        for widget in self.calendar_frame.winfo_children():
            if widget.grid_info()['row'] > 0: # Başlık satırını koru
                widget.destroy()

        # Ay ismini Türkçe listeden al
        self.month_year_label.config(text=f"{self.turkish_month_names[self.month - 1]} {self.year}")

        cal = calendar.Calendar()
        month_days = cal.monthdayscalendar(self.year, self.month)

        row = 1
        for week in month_days:
            for col, day_num in enumerate(week):
                if day_num != 0:
                    day_button = ttk.Button(self.calendar_frame, text=str(day_num), width=4, command=lambda d=day_num: self._select_date(d))
                    day_button.grid(row=row, column=col, padx=2, pady=2)
                    # Bugünün tarihini vurgulama
                    if day_num == datetime.now().day and self.month == datetime.now().month and self.year == datetime.now().year:
                        day_button.config(style="Accent.TButton")
            row += 1

    def _prev_month(self):
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        self._show_calendar()

    def _next_month(self):
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self._show_calendar()

    def _select_date(self, day):
        self.selected_date = datetime(self.year, self.month, day)
        self.entry_widget.delete(0, tk.END)
        self.entry_widget.insert(0, self.selected_date.strftime('%Y-%m-%d'))
        self.destroy() # Tarih seçildikten sonra pop-up'ı kapat