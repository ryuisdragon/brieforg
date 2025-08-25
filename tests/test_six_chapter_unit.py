import pytest

# Placeholder utility demonstrating how a six chapter unit might use category and brand
# In real tests, this would interact with the application code.
def build_unit_payload(category: str, brand: str) -> dict:
    return {
        "category": category,
        "brand": brand,
    }


@pytest.mark.parametrize(
    "category,brand",
    [
        ("熱水器", "喜特麗"),
        ("洗衣機", "三洋"),
        ("電冰箱", "東元"),
    ],
)
def test_six_chapter_unit_payload_contains_inputs(category, brand):
    payload = build_unit_payload(category, brand)
    assert payload["category"] == category
    assert payload["brand"] == brand
