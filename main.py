import functions

MENU = """
========================================
         📚 STUDYFLOW - MENU 📚
========================================
 [dodajprzedmiot] - Dodaj nowy przedmiot
 [dodajzadanie]   - Dodaj nowe zadanie
 [pokaz]          - Wyświetl wszystkie zadania
 [wykonano]       - Oznacz zadanie jako zrobione
 [wyjdz]          - Zamknij program
========================================
"""


def main():
    while True:
        wybor = input("\nWybierz opcję > ").lower().strip().replace(" ", "")

        if wybor == 'dodajprzedmiot':
            functions.add_subject()
        elif wybor == 'pokaz':
            functions.show_tasks()
        elif wybor == 'dodajzadanie':
            functions.add_tasks()
        elif wybor == 'wykonano':
            functions.complete_task()
        elif wybor == 'wyjdz':
            print("\nMiłej nauki! Do zobaczenia!")
            break
        else:
            print(" Niepoprawna komenda! Spróbuj ponownie.")
            continue


if __name__ == "__main__":
    print(MENU)
    main()