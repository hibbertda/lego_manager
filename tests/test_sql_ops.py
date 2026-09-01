import json


SAMPLE_SET = {
    "setID": 111,
    "number": "75386",
    "numberVariant": 1,
    "name": "Test Set",
    "year": 2024,
    "theme": "Star Wars",
    "pieces": 500,
    "launchDate": "2024-01-01T00:00:00Z",
    "instructions": [{"URL": "https://www.lego.com/cdn/product-assets/product.bi.core.pdf/1234.pdf"}],
    "local_images": ["sets/75386/images/75386-1.jpg"],
    "local_instructions": ["sets/75386/instructions/1234.pdf"],
}


def test_insert_and_get_set_by_id_strips_sets_prefix(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)

    result = db_ops.get_set_by_id(111)

    assert result is not None
    assert result["name"] == "Test Set"
    assert result["local_images"] == ["75386/images/75386-1.jpg"]
    assert result["local_instructions"] == ["75386/instructions/1234.pdf"]
    assert result["build_page"] == 0
    assert result["build_status"] == "not_started"


def test_update_and_persist_build_progress(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)

    db_ops.update_build_progress(111, build_page=42, build_status="in_progress")
    result = db_ops.get_set_by_id(111)

    assert result["build_page"] == 42
    assert result["build_status"] == "in_progress"


def test_build_progress_survives_reinsert(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)
    db_ops.update_build_progress(111, build_page=17, build_status="in_progress")

    # Simulate a refresh (re-adding the same set), which uses INSERT OR REPLACE.
    db_ops.insert_set_data(SAMPLE_SET)

    result = db_ops.get_set_by_id(111)
    assert result["build_page"] == 17
    assert result["build_status"] == "in_progress"


def test_update_build_progress_rejects_invalid_status(db_ops):
    import pytest

    db_ops.insert_set_data(SAMPLE_SET)
    with pytest.raises(ValueError):
        db_ops.update_build_progress(111, build_page=1, build_status="bogus")


def test_get_set_by_id_returns_none_for_missing_set(db_ops):
    assert db_ops.get_set_by_id(999) is None


def test_favorite_defaults_false_and_can_be_toggled(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)
    assert db_ops.get_set_by_id(111)["favorite"] is False

    assert db_ops.toggle_favorite(111) is True
    assert db_ops.get_set_by_id(111)["favorite"] is True

    assert db_ops.toggle_favorite(111) is False
    assert db_ops.get_set_by_id(111)["favorite"] is False


def test_favorite_survives_reinsert(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)
    db_ops.toggle_favorite(111)

    # Simulate a refresh (re-adding the same set), which uses INSERT OR REPLACE.
    db_ops.insert_set_data(SAMPLE_SET)

    assert db_ops.get_set_by_id(111)["favorite"] is True


def test_update_build_status_only_leaves_build_page_untouched(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)
    db_ops.update_build_progress(111, build_page=42, build_status="in_progress")

    db_ops.update_build_status_only(111, "storage")

    result = db_ops.get_set_by_id(111)
    assert result["build_status"] == "storage"
    assert result["build_page"] == 42


def test_update_build_status_only_rejects_invalid_status(db_ops):
    import pytest

    db_ops.insert_set_data(SAMPLE_SET)
    with pytest.raises(ValueError):
        db_ops.update_build_status_only(111, "bogus")


def test_list_sets_favorite_only_filter(db_ops):
    for i in range(3):
        set_data = dict(SAMPLE_SET)
        set_data["setID"] = i
        set_data["number"] = str(2000 + i)
        db_ops.insert_set_data(set_data)
    db_ops.toggle_favorite(1)

    sets_data, total = db_ops.list_sets(favorite_only=True)
    assert total == 1
    assert sets_data[0]["setID"] == 1


def test_list_sets_pagination(db_ops):
    for i in range(15):
        set_data = dict(SAMPLE_SET)
        set_data["setID"] = i
        set_data["number"] = str(1000 + i)
        set_data["name"] = f"Set {i}"
        db_ops.insert_set_data(set_data)

    page1, total = db_ops.list_sets(page=1, per_page=10)
    page2, _ = db_ops.list_sets(page=2, per_page=10)

    assert total == 15
    assert len(page1) == 10
    assert len(page2) == 5


def test_search_sets_filters_by_name(db_ops):
    set_a = dict(SAMPLE_SET, setID=1, name="Millennium Falcon")
    set_b = dict(SAMPLE_SET, setID=2, name="Death Star")
    db_ops.insert_set_data(set_a)
    db_ops.insert_set_data(set_b)

    results, total = db_ops.search_sets("Falcon")

    assert total == 1


def test_delete_set_removes_row(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)

    assert db_ops.delete_set(111) is True
    assert db_ops.get_set_by_id(111) is None


def test_delete_set_returns_false_for_missing_set(db_ops):
    assert db_ops.delete_set(999) is False


def test_get_distinct_themes_returns_sorted_unique_themes(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=1, theme="Star Wars"))
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=2, theme="Technic"))
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=3, theme="Star Wars"))

    assert db_ops.get_distinct_themes() == ["Star Wars", "Technic"]


def test_list_sets_filters_by_theme(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=1, theme="Star Wars"))
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=2, theme="Technic"))

    results, total = db_ops.list_sets(theme="Technic")

    assert total == 1
    assert results[0]["setID"] == 2


def test_normalizes_legacy_prefixed_paths_read_back_correctly(db_ops):
    # Simulate a row already containing the (buggy) 'sets/' prefix, as older
    # versions of the app wrote for local_instructions.
    conn = db_ops.create_connection()
    with conn:
        conn.execute(
            "INSERT INTO sets (setID, setNumber, name, local_images, local_instructions) "
            "VALUES (?, ?, ?, ?, ?)",
            (42, 75350, "Legacy Set", json.dumps(["sets/75350/images/x.jpg"]),
             json.dumps(["sets/75350/instructions/y.pdf"])),
        )
    conn.close()

    result = db_ops.get_set_by_id(42)

    assert result["local_images"] == ["75350/images/x.jpg"]
    assert result["local_instructions"] == ["75350/instructions/y.pdf"]
