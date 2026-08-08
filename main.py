from functions import Subject, Task

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

    subject = Subject()
    task = Task()

    while True:
        wybor = input("\nWybierz opcję > ").lower().strip().replace(" ", "")

        if wybor == 'dodajprzedmiot':
           subject.add()
        elif wybor == 'pokaz':
            task.show()
        elif wybor == 'dodajzadanie':
            task.add()
        elif wybor == 'wykonano':
            task.complete()
        elif wybor == 'wyjdz':
            print("\nMiłej nauki! Do zobaczenia!")
            break
        else:
            print(" Niepoprawna komenda! Spróbuj ponownie.")
            continue


if __name__ == "__main__":
    print(MENU)
    main()