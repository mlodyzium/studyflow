from legacy_cli.functions import Subject, Task

MENU = """
📚 STUDYFLOW - MENU 📚

Wybierz jedną z opcji:
- dodajprzedmiot
- pokaz
- dodajzadanie
- wykonano
- wyjdz
"""


def main():
    subject = Subject()
    task = Task()

    while True:
        wybor = (
            input("\nWybierz opcję > ")
            .lower()
            .strip()
            .replace(" ", "")
        )

        if wybor == "dodajprzedmiot":
            subject.add()
        elif wybor == "pokaz":
            task.show()
        elif wybor == "dodajzadanie":
            task.add()
        elif wybor == "wykonano":
            task.complete()
        elif wybor == "wyjdz":
            print("\nMiłej nauki! Do zobaczenia!")
            break
        else:
            print("Niepoprawna komenda! Spróbuj ponownie.")


if __name__ == "__main__":
    print(MENU)
    main()
