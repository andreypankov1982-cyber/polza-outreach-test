import argparse
import csv
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_INPUT = "polza_companies.csv"
DEFAULT_OUTPUT = "companies_with_personalization.csv"
DEFAULT_REPORT = "validation_report.csv"
MIN_ROWS = 50

REQUIRED_COLUMNS = [
    "Компания",
    "Сайт",
    "Ниша",
    "Email",
    "Краткий факт",
    "Персонализация",
    "Источник факта",
]

EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)


def clean_text(value: str | None) -> str:
    value = value or ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(url: str) -> str:
    url = clean_text(url)
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(clean_text(email)))


def check_site(url: str, timeout: int = 8) -> tuple[bool, str, str]:
    url = normalize_url(url)
    if not url:
        return False, "empty_url", ""

    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120 Safari/537.36"
            )
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = response.getcode()
            final_url = response.geturl()
            return 200 <= status_code < 400, str(status_code), final_url
    except HTTPError as error:
        return False, f"http_error_{error.code}", url
    except URLError as error:
        return False, f"url_error_{error.reason}", url
    except Exception as error:
        return False, f"error_{error}", url


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


def read_companies(input_file: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not input_file.exists():
        raise FileNotFoundError(f"Не найден файл {input_file}. Положите CSV рядом со скриптом.")

    with input_file.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    if not rows:
        raise ValueError("CSV-файл пустой.")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing_columns:
        raise ValueError("В CSV не хватает обязательных колонок: " + ", ".join(missing_columns))

    return rows, fieldnames


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Personalization script for Polza Agency test task")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--check-sites", action="store_true", help="Optionally check website availability")
    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)
    report_file = Path(args.report)

    rows, fieldnames = read_companies(input_file)

    if "Персонализация" not in fieldnames:
        fieldnames.append("Персонализация")

    output_rows = []
    report_rows = []

    for row_number, row in enumerate(rows, start=2):
        company = clean_text(row.get("Компания"))
        site = clean_text(row.get("Сайт"))
        niche = clean_text(row.get("Ниша"))
        email = clean_text(row.get("Email"))
        fact = clean_text(row.get("Краткий факт"))
        source_fact = clean_text(row.get("Источник факта"))
        personalization = clean_text(row.get("Персонализация"))

        issues = []

        if not company:
            issues.append("empty_company")
        if not site:
            issues.append("empty_site")
        if not niche:
            issues.append("empty_niche")
        if not email:
            issues.append("empty_email")
        elif not is_valid_email(email):
            issues.append("bad_email_format")
        if not fact:
            issues.append("empty_fact")
        if not source_fact:
            issues.append("empty_source_fact")

        if not personalization:
            row["Персонализация"] = make_personalization(company, niche, fact)
            personalization_status = "generated"
        else:
            personalization_status = "kept_manual"

        site_ok = "not_checked"
        site_status = "not_checked"
        final_url = ""
        if args.check_sites:
            checked_ok, checked_status, checked_final_url = check_site(site)
            site_ok = str(checked_ok)
            site_status = checked_status
            final_url = checked_final_url
            if not checked_ok:
                issues.append(f"site_check_failed:{checked_status}")

        output_rows.append(row)
        report_rows.append(
            {
                "row_number": str(row_number),
                "company": company,
                "site": site,
                "final_url": final_url,
                "site_ok": site_ok,
                "site_status": site_status,
                "email": email,
                "email_ok": str(is_valid_email(email)),
                "personalization_status": personalization_status,
                "issues": "; ".join(issues),
            }
        )

    if len(output_rows) < MIN_ROWS:
        report_rows.append(
            {
                "row_number": "base_check",
                "company": "",
                "site": "",
                "final_url": "",
                "site_ok": "",
                "site_status": "",
                "email": "",
                "email_ok": "",
                "personalization_status": "",
                "issues": f"base_has_less_than_{MIN_ROWS}_rows",
            }
        )

    write_csv(output_file, output_rows, fieldnames)
    write_csv(
        report_file,
        report_rows,
        [
            "row_number",
            "company",
            "site",
            "final_url",
            "site_ok",
            "site_status",
            "email",
            "email_ok",
            "personalization_status",
            "issues",
        ],
    )

    bad_email_count = sum(row["email_ok"] == "False" for row in report_rows)
    rows_with_issues_count = sum(bool(row["issues"]) for row in report_rows)
    generated_count = sum(row["personalization_status"] == "generated" for row in report_rows)
    kept_manual_count = sum(row["personalization_status"] == "kept_manual" for row in report_rows)

    print(f"Готово: создан файл {output_file}")
    print(f"Готово: создан файл {report_file}")
    print(f"Строк обработано: {len(output_rows)}")
    print(f"Персонализация сгенерирована: {generated_count}")
    print(f"Ручная персонализация сохранена: {kept_manual_count}")
    print(f"Email с ошибкой формата: {bad_email_count}")
    print(f"Строк с замечаниями: {rows_with_issues_count}")


if __name__ == "__main__":
    main()
