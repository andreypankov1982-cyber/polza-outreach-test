import csv
import re
from pathlib import Path


INPUT_FILE = Path("polza_companies.csv")
OUTPUT_FILE = Path("companies_with_personalization.csv")


def clean_text(value: str) -> str:
    value = value or ""
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def make_personalization(company: str, niche: str, fact: str) -> str:
    company = clean_text(company)
    niche = clean_text(niche)
    fact = clean_text(fact)

    if fact:
        return (
            f"Увидел, что {company} работает в направлении: {niche}. "
            f"{fact} Для такой B2B-компании email-аутрич может быть полезен "
            f"как способ проверить новые сегменты, гипотезы и получить "
            f"целевые входящие ответы от ЛПР."
        )

    return (
        f"Увидел, что {company} работает в B2B-сегменте: {niche}. "
        f"Для таких компаний email-аутрич может быть полезен как отдельный канал "
        f"поиска новых клиентов и проверки коммерческих гипотез."
    )


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Не найден файл {INPUT_FILE}. "
            "Скачайте лист Google Таблицы в CSV и положите рядом со скриптом."
        )

    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    if not rows:
        raise ValueError("CSV-файл пустой.")

    output_rows = []

    for row in rows:
        company = row.get("Компания", "")
        niche = row.get("Ниша", "")
        fact = row.get("Краткий факт", "")

        # Не перетираем ручную персонализацию, если она уже заполнена.
        if not row.get("Персонализация"):
            row["Персонализация"] = make_personalization(company, niche, fact)

        output_rows.append(row)

    fieldnames = list(output_rows[0].keys())
    if "Персонализация" not in fieldnames:
        fieldnames.append("Персонализация")

    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Готово: создан файл {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
