# Справочные данные

- `categories.txt` — категории деталей, по одной на строку. Загружаются миграцией `0003_load_categories`.
- `cars.json` — марки и модели легковых автомобилей. Загружаются миграцией `0005_load_brands_models`.
  Источник: бесплатная база [cars-base.ru](https://github.com/blanzh/carsBase) (по каталогу Auto.ru),
  выгрузка от 2026-10-09. Названия моделей очищены от приписок поколения
  («Focus, III Рестайлинг» → «Focus»), поколения в бесплатной базе нет.

Формат `cars.json`: список марок
`{"name", "name_ru", "country", "popular", "models": [[name, name_ru, year_from, year_to], ...]}`.
