from services.normalize import (
    normalize_condition_grade,
    normalize_jpy_price,
    normalize_price,
    normalize_store_result,
    normalize_usd_price,
)


def test_normalize_price_yen_formats():
    assert normalize_jpy_price("¥29,800") == 29800
    assert normalize_jpy_price("29800円") == 29800
    assert normalize_jpy_price("JPY 29800") == 29800


def test_normalize_price_usd_formats():
    assert normalize_usd_price("$12.34") == 1234
    assert normalize_usd_price("USD 1,234.56") == 123456
    assert normalize_usd_price("12") == 1200


def test_normalize_price_safely_handles_invalid_inputs():
    assert normalize_jpy_price(None) is None
    assert normalize_jpy_price("not a price") is None
    assert normalize_usd_price(None) is None
    assert normalize_usd_price("not a price") is None


def test_normalize_condition_grade_japanese_and_english_labels():
    assert normalize_condition_grade("状態A") == "A"
    assert normalize_condition_grade("状態A-") == "A-"
    assert normalize_condition_grade("〔状態B〕") == "B"
    assert normalize_condition_grade("[状態B-]XY") == "B-"
    assert normalize_condition_grade("※状態難") == "C"
    assert normalize_condition_grade("Near Mint") == "A"
    assert normalize_condition_grade("Light Played") == "B"
    assert normalize_condition_grade("Moderate Played") == "B-"
    assert normalize_condition_grade("Damaged") == "C"
    assert normalize_condition_grade("PSA10") is None


def test_normalize_store_result_uses_integer_price_and_currency():
    result = normalize_store_result(
        "example",
        {
            "name": "Pikachu Promo",
            "price_yen": "¥29,800",
            "in_stock": True,
            "url": "https://example.com/card",
        },
    )

    assert result == {
        "name": "Pikachu Promo",
        "price": 29800,
        "currency": "JPY",
        "in_stock": True,
        "url": "https://example.com/card",
    }
