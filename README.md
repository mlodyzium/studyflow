# StudyFlow 🎓

**StudyFlow** to lekka, modularna aplikacja konsolowa napisana w języku Python, służąca do organizacji nauki poprzez zarządzanie przedmiotami i przypisanymi do nich zadaniami. Wszystkie wprowadzane zmiany są automatycznie zapisywane w lokalnym pliku JSON (`data.json`), co zapewnia trwałość danych między uruchomieniami.

---

## 📁 Opis modułów programu

Projekt został podzielony na dwa osobne pliki w celu zachowania czystości kodu i podziału odpowiedzialności (zgodnie z dobrą praktyką rozdzielania interfejsu od logiki):

* **`main.py` (Interfejs i Nawigacja)**
  * Odpowiada za uruchomienie aplikacji i prezentację głównego menu tekstowego.
  * Działa w nieskończonej pętli `while True`, przechwytując polecenia użytkownika.
  * Czyści i formatuje wprowadzany tekst (usuwa spacje i ignoruje wielkość liter), zapobiegając błędnym komendom.
  * Przekazuje sterowanie do odpowiednich funkcji w module `functions.py`.

* **`functions.py` (Logika Biznesowa i Pliki)**
  * **Obsługa danych:** Wczytuje i zapisuje strukturę danych z/do pliku `data.json` ze wsparciem dla kodowania `UTF-8` oraz obsługuje uszkodzony lub pusty plik.
  * **Zarządzanie przedmiotami:** Pozwala na dodawanie nowych przedmiotów i pilnuje, aby ich nazwy się nie dublowały.
  * **Zarządzanie zadaniami:** Umożliwia dodawanie zadań do konkretnych przedmiotów oraz zmianę ich stanu na wykonane.
  * **Wyświetlanie:** Formatowanie i przejrzyste renderowanie listy przedmiotów oraz zadań wraz z ich statusami (`[ ]` / `[Wykonane]`).
  * **Walidacja liczbowa:** Zawiera funkcję pomocniczą `get_user_int()`, która zabezpiecza program przed awarią (crashem), gdy użytkownik zamiast cyfry wpisze litery.

---

## 🚀 Jak uruchomić program?

Do uruchomienia aplikacji wymagane jest wyłącznie zainstalowane środowisko **Python w wersji 3.x**. Aplikacja korzysta z bibliotek standardowych (`json`, `os`), więc **nie trzeba instalować żadnych dodatkowych pakietów za pomocą `pip`**.

### Krok 1: Pobranie kodu
Pobierz pliki projektu i upewnij się, że `main.py` oraz `functions.py` znajdują się w tym samym folderze.

### Krok 2: Uruchomienie w terminalu

1. Otwórz Terminal / Wiersz poleceń / PowerShell i przejdź do folderu z projektem:
   ```bash
   cd sciezka/do/folderu/studyflow
   python main.py
   ```