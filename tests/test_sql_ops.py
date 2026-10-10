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
    "instructions": [
        {"URL": "https://www.lego.com/cdn/product-assets/product.bi.core.pdf/1234.pdf"}
    ],
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
    assert [item["name"] for item in page1] == sorted(item["name"] for item in page1)


def test_manual_set_ids_are_unique_and_negative(db_ops):
    ids = {db_ops.get_next_manual_set_id() for _ in range(3)}
    assert ids == {-1, -2, -3}


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


def test_list_sets_default_sort_is_name_ascending(db_ops):
    db_ops.insert_set_data(
        dict(SAMPLE_SET, setID=1, name="Zebra Set", year=2020, theme="A")
    )
    db_ops.insert_set_data(
        dict(SAMPLE_SET, setID=2, name="Apple Set", year=2022, theme="B")
    )

    results, _ = db_ops.list_sets()

    assert [r["setID"] for r in results] == [2, 1]


def test_list_sets_sort_by_year_is_newest_first(db_ops):
    db_ops.insert_set_data(
        dict(SAMPLE_SET, setID=1, name="A Set", year=2015, theme="A")
    )
    db_ops.insert_set_data(
        dict(SAMPLE_SET, setID=2, name="B Set", year=2023, theme="B")
    )

    results, _ = db_ops.list_sets(sort="year")

    assert [r["setID"] for r in results] == [2, 1]


def test_list_sets_sort_by_theme_ascending(db_ops):
    db_ops.insert_set_data(
        dict(SAMPLE_SET, setID=1, name="A Set", year=2020, theme="Technic")
    )
    db_ops.insert_set_data(
        dict(SAMPLE_SET, setID=2, name="B Set", year=2020, theme="Icons")
    )

    results, _ = db_ops.list_sets(sort="theme")

    assert [r["setID"] for r in results] == [2, 1]


def test_list_sets_invalid_sort_falls_back_to_default(db_ops):
    db_ops.insert_set_data(
        dict(SAMPLE_SET, setID=1, name="Zebra Set", year=2020, theme="A")
    )
    db_ops.insert_set_data(
        dict(SAMPLE_SET, setID=2, name="Apple Set", year=2022, theme="B")
    )

    results, _ = db_ops.list_sets(sort="not-a-real-option")

    assert [r["setID"] for r in results] == [2, 1]


def test_normalizes_legacy_prefixed_paths_read_back_correctly(db_ops):
    # Simulate a row already containing the (buggy) 'sets/' prefix, as older
    # versions of the app wrote for local_instructions.
    conn = db_ops.create_connection()
    with conn:
        conn.execute(
            "INSERT INTO sets (setID, setNumber, name, local_images, local_instructions) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                42,
                75350,
                "Legacy Set",
                json.dumps(["sets/75350/images/x.jpg"]),
                json.dumps(["sets/75350/instructions/y.pdf"]),
            ),
        )
    conn.close()

    result = db_ops.get_set_by_id(42)

    assert result["local_images"] == ["75350/images/x.jpg"]
    assert result["local_instructions"] == ["75350/instructions/y.pdf"]


def test_update_set_metadata_updates_fields(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)

    updated = db_ops.update_set_metadata(111, "New Name", 2025, "Technic", 999)

    assert updated is True
    result = db_ops.get_set_by_id(111)
    assert result["name"] == "New Name"
    assert result["year"] == 2025
    assert result["theme"] == "Technic"
    assert result["pieces"] == 999


def test_update_set_metadata_returns_false_for_missing_set(db_ops):
    assert db_ops.update_set_metadata(999, "X", None, None, None) is False


def test_append_local_instructions_adds_without_duplicating(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)

    added = db_ops.append_local_instructions(
        111, ["75386/instructions/manual.pdf", "75386/instructions/1234.pdf"]
    )

    assert added is True
    result = db_ops.get_set_by_id(111)
    # The pre-existing "1234.pdf" isn't duplicated; only the new file is added.
    assert result["local_instructions"] == [
        "75386/instructions/1234.pdf",
        "75386/instructions/manual.pdf",
    ]


def test_append_local_instructions_returns_false_for_missing_set(db_ops):
    assert db_ops.append_local_instructions(999, ["x/instructions/y.pdf"]) is False


def test_find_sets_missing_metadata_reports_gaps(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=1))  # complete
    db_ops.insert_set_data(
        dict(
            SAMPLE_SET,
            setID=2,
            number="99999",
            year=None,
            theme=None,
            pieces=None,
            local_images=[],
            local_instructions=[],
        )
    )

    results = db_ops.find_sets_missing_metadata()

    assert len(results) == 1
    incomplete = results[0]
    assert incomplete["setID"] == 2
    assert set(incomplete["missing_fields"]) == {
        "year",
        "theme",
        "pieces",
        "cover image",
        "instructions",
    }


def test_find_sets_missing_metadata_empty_when_all_complete(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)
    assert db_ops.find_sets_missing_metadata() == []


def test_location_defaults_empty_and_can_be_set(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)
    assert db_ops.get_set_by_id(111)["location"] == ""

    db_ops.update_location(111, "Shelf 3")
    assert db_ops.get_set_by_id(111)["location"] == "Shelf 3"


def test_location_survives_reinsert(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)
    db_ops.update_location(111, "Shelf 3")

    # Simulate a refresh (re-adding the same set), which uses INSERT OR REPLACE.
    db_ops.insert_set_data(SAMPLE_SET)

    assert db_ops.get_set_by_id(111)["location"] == "Shelf 3"


def test_update_build_status_only_to_storage_clears_location(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)
    db_ops.update_location(111, "Shelf 3")
    db_ops.update_build_status_only(111, "complete")
    assert db_ops.get_set_by_id(111)["location"] == "Shelf 3"

    db_ops.update_build_status_only(111, "storage")

    result = db_ops.get_set_by_id(111)
    assert result["build_status"] == "storage"
    assert result["location"] == ""


def test_update_build_progress_to_storage_clears_location(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)
    db_ops.update_location(111, "Bin A")

    db_ops.update_build_progress(111, build_page=0, build_status="storage")

    result = db_ops.get_set_by_id(111)
    assert result["build_status"] == "storage"
    assert result["location"] == ""


def test_update_location_clears_when_blank(db_ops):
    db_ops.insert_set_data(SAMPLE_SET)
    db_ops.update_location(111, "Shelf 3")

    db_ops.update_location(111, "  ")

    assert db_ops.get_set_by_id(111)["location"] == ""


def test_get_distinct_locations(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=1))
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=2))
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=3))
    db_ops.update_location(1, "Shelf 3")
    db_ops.update_location(2, "Bin A")
    db_ops.update_location(3, "Shelf 3")

    assert db_ops.get_distinct_locations() == ["Bin A", "Shelf 3"]


def test_list_sets_filters_by_location(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=1))
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=2))
    db_ops.update_location(1, "Shelf 3")
    db_ops.update_location(2, "Bin A")

    results, total = db_ops.list_sets(location="Shelf 3")

    assert total == 1
    assert results[0]["setID"] == 1


def test_wishlist_is_valid_but_not_owned_status(db_ops):
    from app.sql_ops import OWNED_BUILD_STATUSES, VALID_BUILD_STATUSES

    assert "wishlist" in VALID_BUILD_STATUSES
    assert "wishlist" not in OWNED_BUILD_STATUSES
    db_ops.insert_set_data(SAMPLE_SET)
    db_ops.update_build_status_only(111, "wishlist")
    assert db_ops.get_set_by_id(111)["build_status"] == "wishlist"


def test_list_sets_excludes_wishlist_by_default(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=1))
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=2))
    db_ops.update_build_status_only(2, "wishlist")

    results, total = db_ops.list_sets()

    assert total == 1
    assert results[0]["setID"] == 1


def test_list_sets_include_wishlist_shows_all(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=1))
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=2))
    db_ops.update_build_status_only(2, "wishlist")

    results, total = db_ops.list_sets(include_wishlist=True)

    assert total == 2


def test_list_sets_explicit_wishlist_status_filter(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=1))
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=2))
    db_ops.update_build_status_only(2, "wishlist")

    results, total = db_ops.list_sets(build_status="wishlist")

    assert total == 1
    assert results[0]["setID"] == 2


def test_count_owned_sets_excludes_wishlist(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=1))
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=2))
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=3))
    db_ops.update_build_status_only(3, "wishlist")

    assert db_ops.count_owned_sets() == 2


def test_rebrickable_settings_roundtrip(db_ops):
    assert db_ops.get_rebrickable_settings() is None

    db_ops.save_rebrickable_settings(api_key="abc123")

    assert db_ops.get_rebrickable_settings() == {"api_key": "abc123"}

    db_ops.save_rebrickable_settings(api_key="xyz789")

    assert db_ops.get_rebrickable_settings() == {"api_key": "xyz789"}


def test_replace_set_parts_and_get_set_parts(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=200))

    assert db_ops.get_set_parts(200) == []
    assert db_ops.has_set_parts(200) is False

    parts = [
        {
            "part_num": "3001",
            "color_id": 5,
            "name": "Brick 2 x 4",
            "color_name": "Red",
            "quantity": 4,
            "image_path": "_parts_cache/3001_5.jpg",
        },
        {
            "part_num": "3002",
            "color_id": 0,
            "name": "Brick 2 x 2",
            "color_name": "Black",
            "quantity": 2,
            "image_path": None,
        },
    ]
    db_ops.replace_set_parts(200, parts)

    stored = db_ops.get_set_parts(200)
    assert db_ops.has_set_parts(200) is True
    assert {p["part_num"] for p in stored} == {"3001", "3002"}
    brick = next(p for p in stored if p["part_num"] == "3001")
    assert brick["quantity"] == 4
    assert brick["image_path"] == "_parts_cache/3001_5.jpg"


def test_replace_set_parts_overwrites_previous_sync(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=201))
    db_ops.replace_set_parts(
        201,
        [
            {
                "part_num": "3001",
                "color_id": 5,
                "name": "Brick",
                "color_name": "Red",
                "quantity": 1,
                "image_path": None,
            }
        ],
    )

    db_ops.replace_set_parts(
        201,
        [
            {
                "part_num": "3002",
                "color_id": 0,
                "name": "Plate",
                "color_name": "Black",
                "quantity": 9,
                "image_path": None,
            }
        ],
    )

    stored = db_ops.get_set_parts(201)
    assert len(stored) == 1
    assert stored[0]["part_num"] == "3002"
    assert stored[0]["quantity"] == 9


def test_set_parts_deleted_when_set_deleted(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=202))
    db_ops.replace_set_parts(
        202,
        [
            {
                "part_num": "3001",
                "color_id": 5,
                "name": "Brick",
                "color_name": "Red",
                "quantity": 1,
                "image_path": None,
            }
        ],
    )

    db_ops.delete_set(202)

    assert db_ops.get_set_parts(202) == []


def test_replace_set_minifigs_and_get_set_minifigs(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=210))

    assert db_ops.get_set_minifigs(210) == []

    minifigs = [
        {
            "fig_num": "fig-001",
            "name": "Luke Skywalker",
            "quantity": 1,
            "image_path": "_minifigs_cache/fig-001.jpg",
        },
        {
            "fig_num": "fig-002",
            "name": "Darth Vader",
            "quantity": 2,
            "image_path": None,
        },
    ]
    db_ops.replace_set_minifigs(210, minifigs)

    stored = db_ops.get_set_minifigs(210)
    assert {m["fig_num"] for m in stored} == {"fig-001", "fig-002"}
    vader = next(m for m in stored if m["fig_num"] == "fig-002")
    assert vader["quantity"] == 2
    assert vader["image_path"] is None


def test_replace_set_minifigs_overwrites_previous_sync(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=211))
    db_ops.replace_set_minifigs(
        211,
        [{"fig_num": "fig-001", "name": "A", "quantity": 1, "image_path": None}],
    )

    db_ops.replace_set_minifigs(
        211,
        [{"fig_num": "fig-002", "name": "B", "quantity": 3, "image_path": None}],
    )

    stored = db_ops.get_set_minifigs(211)
    assert len(stored) == 1
    assert stored[0]["fig_num"] == "fig-002"
    assert stored[0]["quantity"] == 3


def test_set_minifigs_deleted_when_set_deleted(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=212))
    db_ops.replace_set_minifigs(
        212,
        [{"fig_num": "fig-001", "name": "A", "quantity": 1, "image_path": None}],
    )

    db_ops.delete_set(212)

    assert db_ops.get_set_minifigs(212) == []


def test_mark_parts_synced_sets_timestamp(db_ops):
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=213))

    assert db_ops.get_set_by_id(213)["parts_synced_at"] is None

    db_ops.mark_parts_synced(213)

    assert db_ops.get_set_by_id(213)["parts_synced_at"] is not None


def test_mark_parts_synced_persists_even_with_zero_results(db_ops):
    """A set can legitimately have zero minifigs after a real sync — the
    synced marker must stay independent of row counts so the UI/missing-
    metadata scan don't keep treating it as never-synced."""
    db_ops.insert_set_data(dict(SAMPLE_SET, setID=214))

    db_ops.replace_set_parts(214, [])
    db_ops.replace_set_minifigs(214, [])
    db_ops.mark_parts_synced(214)

    assert db_ops.has_set_parts(214) is False
    assert db_ops.get_set_by_id(214)["parts_synced_at"] is not None
