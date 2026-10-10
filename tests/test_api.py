"""Covers app/blueprints/api.py — the JSON API backing the React SPA. This
supersedes tests/test_routes.py, which tested the Jinja UI these endpoints
replaced; UI-only concerns (view toggles, mobile filter collapse, etc.) are
no longer backend behavior and are not re-tested here."""


def test_custom_static_blocks_path_traversal(admin_client):
    response = admin_client.get("/files/sets/../../etc/passwd")
    assert response.status_code == 404


def test_set_detail_404_for_missing_set(admin_client):
    response = admin_client.get("/api/sets/999")
    assert response.status_code == 404


def test_search_suggest_requires_login(admin_user, client):
    response = client.get("/api/search/suggest?query=star")
    assert response.status_code == 401


def test_search_suggest_empty_query_returns_empty_results(admin_client):
    response = admin_client.get("/api/search/suggest?query=")
    assert response.status_code == 200
    assert response.get_json() == {"results": [], "total": 0}


def test_search_suggest_no_matches(admin_client):
    response = admin_client.get("/api/search/suggest?query=zzz_no_such_set")
    assert response.status_code == 200
    data = response.get_json()
    assert data["results"] == []
    assert data["total"] == 0


def test_add_set_manual_requires_name_and_number(admin_client):
    response = admin_client.post(
        "/api/sets/manual", data={"set_number": "", "name": ""}
    )
    assert response.status_code == 400
    assert b"Set number and name are required" in response.data


def test_add_set_manual_creates_set_without_files(app, admin_client):
    response = admin_client.post(
        "/api/sets/manual",
        data={
            "set_number": "99999",
            "name": "Manually Added Set",
            "year": "2024",
            "theme": "Custom",
            "pieces": "42",
        },
    )
    assert response.status_code == 201

    sets_data, total = app.db_ops.list_sets()
    assert total == 1
    assert sets_data[0]["name"] == "Manually Added Set"
    assert sets_data[0]["setID"] < 0
    assert sets_data[0]["local_images"] == []
    assert sets_data[0]["local_instructions"] == []


def test_add_set_manual_with_image_and_pdf(app, admin_client):
    import io
    import os

    from PIL import Image

    image_bytes = io.BytesIO()
    Image.new("RGB", (1, 1), color="red").save(image_bytes, format="JPEG")
    image_bytes.seek(0)

    response = admin_client.post(
        "/api/sets/manual",
        data={
            "set_number": "88888",
            "name": "Set With Files",
            "image": (image_bytes, "box.jpg"),
            "instructions": (io.BytesIO(b"%PDF-1.4 fake"), "manual.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201

    sets_data, _ = app.db_ops.list_sets()
    added = next(s for s in sets_data if s["name"] == "Set With Files")
    assert len(added["local_images"]) == 1
    assert added["local_images"][0].endswith("box.jpg")
    assert len(added["local_instructions"]) == 1
    assert added["local_instructions"][0].endswith("manual.pdf")

    saved_image_path = os.path.join(app.config["SETS_DIR"], added["local_images"][0])
    assert os.path.isfile(saved_image_path)


def test_add_set_manual_rejects_bad_image_extension(admin_client):
    import io

    response = admin_client.post(
        "/api/sets/manual",
        data={
            "set_number": "77777",
            "name": "Bad Image Set",
            "image": (io.BytesIO(b"not-an-image"), "virus.exe"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert b"Image must be a PNG, JPG, GIF, or WEBP file" in response.data


def test_add_set_manual_rejects_non_image_content_with_valid_extension(admin_client):
    import io

    response = admin_client.post(
        "/api/sets/manual",
        data={
            "set_number": "66666",
            "name": "Spoofed Image Set",
            "image": (io.BytesIO(b"not-actually-a-jpeg"), "box.jpg"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert b"Image file is corrupt or is not a valid image" in response.data


def test_add_set_manual_rejects_non_pdf_content_with_valid_extension(admin_client):
    import io

    response = admin_client.post(
        "/api/sets/manual",
        data={
            "set_number": "55555",
            "name": "Spoofed PDF Set",
            "instructions": (io.BytesIO(b"not-a-real-pdf"), "manual.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert b"Instructions file is not a valid PDF" in response.data


def test_two_manual_sets_get_distinct_negative_ids(app, admin_client):
    admin_client.post(
        "/api/sets/manual", data={"set_number": "11111", "name": "First Manual Set"}
    )
    admin_client.post(
        "/api/sets/manual", data={"set_number": "22222", "name": "Second Manual Set"}
    )
    sets_data, total = app.db_ops.list_sets()
    assert total == 2
    ids = {s["setID"] for s in sets_data}
    assert len(ids) == 2
    assert all(i < 0 for i in ids)


def test_add_set_manual_with_wishlist_category(app, admin_client):
    response = admin_client.post(
        "/api/sets/manual",
        data={"set_number": "999-1", "name": "Dream Set", "build_status": "wishlist"},
    )
    assert response.status_code == 201
    results, _ = app.db_ops.search_sets("999-1")
    assert results[0]["build_status"] == "wishlist"

    main_list = admin_client.get("/api/sets").get_json()
    assert not any(s["name"] == "Dream Set" for s in main_list["sets"])
    wishlist = admin_client.get("/api/wishlist").get_json()
    assert any(s["name"] == "Dream Set" for s in wishlist["sets"])


def test_add_set_manual_invalid_build_status_defaults(app, admin_client):
    response = admin_client.post(
        "/api/sets/manual",
        data={
            "set_number": "999-2",
            "name": "Bogus Category Set",
            "build_status": "not-a-real-status",
        },
    )
    assert response.status_code == 201
    results, _ = app.db_ops.search_sets("999-2")
    assert results[0]["build_status"] == "not_started"


def test_update_progress_persists(app, admin_client):
    sample = {
        "setID": 500,
        "number": "12345",
        "name": "Progress Test Set",
        "year": 2024,
        "theme": "Test",
        "pieces": 100,
        "local_images": [],
        "local_instructions": [],
    }
    app.db_ops.insert_set_data(sample)

    response = admin_client.post(
        "/api/sets/500/progress",
        json={"build_page": 12, "build_status": "in_progress"},
    )
    assert response.status_code == 200

    updated = app.db_ops.get_set_by_id(500)
    assert updated["build_page"] == 12
    assert updated["build_status"] == "in_progress"


def test_update_progress_404_for_missing_set(admin_client):
    response = admin_client.post(
        "/api/sets/999/progress",
        data={"build_page": "1", "build_status": "in_progress"},
    )
    assert response.status_code == 404


def test_update_progress_page_persists_via_json(app, admin_client):
    sample = {
        "setID": 501,
        "number": "12346",
        "name": "PDF Viewer Progress Test Set",
        "year": 2024,
        "theme": "Test",
        "pieces": 100,
        "local_images": [],
        "local_instructions": [],
    }
    app.db_ops.insert_set_data(sample)

    response = admin_client.post("/api/sets/501/progress/page", json={"build_page": 7})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "build_page": 7}

    updated = app.db_ops.get_set_by_id(501)
    assert updated["build_page"] == 7
    # Untouched default status gets bumped from not_started to in_progress.
    assert updated["build_status"] == "in_progress"


def test_update_progress_page_does_not_override_existing_status(app, admin_client):
    sample = {
        "setID": 502,
        "number": "12347",
        "name": "PDF Viewer Status Preserve Test Set",
        "year": 2024,
        "theme": "Test",
        "pieces": 100,
        "local_images": [],
        "local_instructions": [],
    }
    app.db_ops.insert_set_data(sample)
    app.db_ops.update_build_progress(502, 40, "complete")

    admin_client.post("/api/sets/502/progress/page", json={"build_page": 41})

    updated = app.db_ops.get_set_by_id(502)
    assert updated["build_page"] == 41
    assert updated["build_status"] == "complete"


def test_update_progress_page_404_for_missing_set(admin_client):
    response = admin_client.post("/api/sets/999/progress/page", json={"build_page": 1})
    assert response.status_code == 404


def test_update_progress_page_rejects_non_integer(app, admin_client):
    sample = {
        "setID": 503,
        "number": "12348",
        "name": "PDF Viewer Validation Test Set",
        "year": 2024,
        "theme": "Test",
        "pieces": 100,
        "local_images": [],
        "local_instructions": [],
    }
    app.db_ops.insert_set_data(sample)

    response = admin_client.post(
        "/api/sets/503/progress/page", json={"build_page": "not-a-number"}
    )
    assert response.status_code == 400


def test_delete_set_removes_it_and_its_files(app, admin_client):
    import os

    sample = {
        "setID": 501,
        "number": "54321",
        "name": "Deletable Set",
        "year": 2024,
        "theme": "Test",
        "pieces": 100,
        "local_images": ["54321/images/x.jpg"],
        "local_instructions": ["54321/instructions/y.pdf"],
    }
    app.db_ops.insert_set_data(sample)

    set_dir = os.path.join(app.config["SETS_DIR"], "54321")
    os.makedirs(os.path.join(set_dir, "images"), exist_ok=True)
    with open(os.path.join(set_dir, "images", "x.jpg"), "wb") as f:
        f.write(b"fake")

    response = admin_client.delete("/api/sets/501")
    assert response.status_code == 200
    assert app.db_ops.get_set_by_id(501) is None
    assert not os.path.isdir(set_dir)


def test_delete_set_404_for_missing_set(admin_client):
    response = admin_client.delete("/api/sets/999")
    assert response.status_code == 404


def test_delete_set_forbidden_for_non_admin(app, user_client):
    app.db_ops.insert_set_data(
        {
            "setID": 805,
            "number": "80005",
            "name": "Keep Me",
            "local_images": [],
            "local_instructions": [],
        }
    )
    response = user_client.delete("/api/sets/805")
    assert response.status_code == 403


def test_list_sets_theme_filter(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 601,
            "number": "1",
            "name": "Set A",
            "year": 2024,
            "theme": "Star Wars",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )
    app.db_ops.insert_set_data(
        {
            "setID": 602,
            "number": "2",
            "name": "Set B",
            "year": 2024,
            "theme": "Technic",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.get("/api/sets?theme=Technic")
    assert response.status_code == 200
    names = {s["name"] for s in response.get_json()["sets"]}
    assert names == {"Set B"}


def test_list_sets_sort_option_orders_results_and_falls_back_when_invalid(
    app, admin_client
):
    app.db_ops.insert_set_data(
        {
            "setID": 611,
            "number": "1",
            "name": "Zebra Set",
            "year": 2015,
            "theme": "Star Wars",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )
    app.db_ops.insert_set_data(
        {
            "setID": 612,
            "number": "2",
            "name": "Apple Set",
            "year": 2023,
            "theme": "Technic",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )

    def names(resp):
        return [s["name"] for s in resp.get_json()["sets"]]

    year_response = admin_client.get("/api/sets?sort=year")
    assert names(year_response).index("Apple Set") < names(year_response).index(
        "Zebra Set"
    )

    bogus_response = admin_client.get("/api/sets?sort=bogus")
    assert bogus_response.status_code == 200
    assert names(bogus_response).index("Apple Set") < names(bogus_response).index(
        "Zebra Set"
    )


def test_toggle_favorite(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 701,
            "number": "1",
            "name": "Fave Set",
            "year": 2024,
            "theme": "Star Wars",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.post("/api/sets/701/favorite")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "favorite": True}

    response = admin_client.post("/api/sets/701/favorite")
    assert response.get_json() == {"ok": True, "favorite": False}


def test_toggle_favorite_404_for_missing_set(admin_client):
    response = admin_client.post("/api/sets/999/favorite")
    assert response.status_code == 404


def test_update_status_only(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 702,
            "number": "1",
            "name": "Status Set",
            "year": 2024,
            "theme": "Star Wars",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.post(
        "/api/sets/702/status", json={"build_status": "storage"}
    )
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "build_status": "storage"}
    assert app.db_ops.get_set_by_id(702)["build_status"] == "storage"


def test_update_status_only_rejects_invalid_status(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 703,
            "number": "1",
            "name": "Status Set 2",
            "year": 2024,
            "theme": "Star Wars",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.post("/api/sets/703/status", json={"build_status": "bogus"})
    assert response.status_code == 400


def test_update_location_persists(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 705,
            "number": "1",
            "name": "Location Set",
            "year": 2024,
            "theme": "Star Wars",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.post("/api/sets/705/location", data={"location": "Shelf 3"})
    assert response.status_code == 200
    assert app.db_ops.get_set_by_id(705)["location"] == "Shelf 3"


def test_update_location_404_for_missing_set(admin_client):
    response = admin_client.post("/api/sets/999/location", data={"location": "Shelf 3"})
    assert response.status_code == 404


def test_changing_status_to_storage_clears_location(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 706,
            "number": "1",
            "name": "Location Clear Set",
            "year": 2024,
            "theme": "Star Wars",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )
    app.db_ops.update_location(706, "Shelf 3")
    app.db_ops.update_build_status_only(706, "complete")
    assert app.db_ops.get_set_by_id(706)["location"] == "Shelf 3"

    response = admin_client.post(
        "/api/sets/706/status", json={"build_status": "storage"}
    )
    assert response.status_code == 200
    assert app.db_ops.get_set_by_id(706)["location"] == ""


def test_list_sets_location_filter(app, admin_client):
    for i, location in enumerate(["Shelf 3", "Bin A"], start=707):
        app.db_ops.insert_set_data(
            {
                "setID": i,
                "number": str(i),
                "name": f"Set {i}",
                "year": 2024,
                "theme": "Star Wars",
                "pieces": 1,
                "local_images": [],
                "local_instructions": [],
            }
        )
        app.db_ops.update_location(i, location)

    response = admin_client.get("/api/sets?location=Shelf+3")
    assert response.status_code == 200
    names = {s["name"] for s in response.get_json()["sets"]}
    assert names == {"Set 707"}


def test_list_sets_favorite_filter(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 704,
            "number": "1",
            "name": "Set Fave",
            "year": 2024,
            "theme": "Star Wars",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )
    app.db_ops.insert_set_data(
        {
            "setID": 705,
            "number": "2",
            "name": "Set Plain",
            "year": 2024,
            "theme": "Star Wars",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )
    admin_client.post("/api/sets/704/favorite")

    response = admin_client.get("/api/sets?favorite=1")
    assert response.status_code == 200
    names = {s["name"] for s in response.get_json()["sets"]}
    assert names == {"Set Fave"}


def test_wishlist_items_excluded_from_main_list(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 960,
            "number": "1",
            "name": "Wanted Set",
            "year": 2024,
            "theme": "Icons",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )
    app.db_ops.update_build_status_only(960, "wishlist")

    response = admin_client.get("/api/sets")
    assert not any(s["name"] == "Wanted Set" for s in response.get_json()["sets"])

    # Even a manually crafted status=wishlist query string must not leak
    # wishlist items into the main list.
    response = admin_client.get("/api/sets?status=wishlist")
    assert not any(s["name"] == "Wanted Set" for s in response.get_json()["sets"])


def test_wishlist_page_shows_wishlist_items(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 961,
            "number": "1",
            "name": "Wanted Set",
            "year": 2024,
            "theme": "Icons",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )
    app.db_ops.update_build_status_only(961, "wishlist")
    app.db_ops.insert_set_data(
        {
            "setID": 962,
            "number": "2",
            "name": "Owned Set",
            "year": 2024,
            "theme": "Icons",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.get("/api/wishlist")
    assert response.status_code == 200
    names = {s["name"] for s in response.get_json()["sets"]}
    assert names == {"Wanted Set"}


def test_edit_set_updates_metadata(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 801,
            "number": "80001",
            "name": "Old Name",
            "year": 2020,
            "theme": "Old Theme",
            "pieces": 10,
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.post(
        "/api/sets/801/edit",
        data={
            "name": "New Name",
            "year": "2024",
            "theme": "New Theme",
            "pieces": "500",
        },
    )

    assert response.status_code == 200
    updated = app.db_ops.get_set_by_id(801)
    assert updated["name"] == "New Name"
    assert updated["year"] == 2024
    assert updated["theme"] == "New Theme"
    assert updated["pieces"] == 500


def test_edit_set_requires_name(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 802,
            "number": "80002",
            "name": "Keep Me",
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.post("/api/sets/802/edit", data={"name": ""})

    assert response.status_code == 400
    assert b"Name is required" in response.data
    assert app.db_ops.get_set_by_id(802)["name"] == "Keep Me"


def test_edit_set_appends_new_instruction_pdf(app, admin_client):
    import io

    app.db_ops.insert_set_data(
        {
            "setID": 803,
            "number": "80003",
            "name": "Instr Set",
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.post(
        "/api/sets/803/edit",
        data={
            "name": "Instr Set",
            "instructions": (io.BytesIO(b"%PDF-1.4 fake"), "extra.pdf"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    updated = app.db_ops.get_set_by_id(803)
    assert len(updated["local_instructions"]) == 1
    assert updated["local_instructions"][0].endswith("extra.pdf")


def test_edit_set_rejects_non_pdf_content(app, admin_client):
    import io

    app.db_ops.insert_set_data(
        {
            "setID": 804,
            "number": "80004",
            "name": "Instr Set",
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.post(
        "/api/sets/804/edit",
        data={
            "name": "Instr Set",
            "instructions": (io.BytesIO(b"not-a-pdf"), "extra.pdf"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"Instructions file is not a valid PDF" in response.data
    assert app.db_ops.get_set_by_id(804)["local_instructions"] == []


def test_edit_set_404_for_missing_set(admin_client):
    response = admin_client.post("/api/sets/999/edit", data={"name": "X"})
    assert response.status_code == 404


def test_edit_set_forbidden_for_non_admin(app, user_client):
    app.db_ops.insert_set_data(
        {
            "setID": 805,
            "number": "80005",
            "name": "Keep Me",
            "local_images": [],
            "local_instructions": [],
        }
    )
    response = user_client.post("/api/sets/805/edit", data={"name": "Hacked"})
    assert response.status_code == 403


def test_refresh_set_manual_set_shows_error(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": -1,
            "number": "90001",
            "name": "Manual Set",
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.post("/api/sets/-1/refresh")

    assert response.status_code == 400
    assert (
        b"isn&#39;t linked to Brickset" in response.data
        or b"isn't linked to Brickset" in response.data
    )


def test_refresh_set_404_for_missing_set(admin_client):
    response = admin_client.post("/api/sets/999/refresh")
    assert response.status_code == 404


def test_refresh_set_success_re_downloads_data(app, admin_client, monkeypatch):
    app.db_ops.insert_set_data(
        {
            "setID": 806,
            "number": "80006",
            "name": "Stale Name",
            "local_images": [],
            "local_instructions": [],
        }
    )

    def fake_get_combined_data(set_number, base_dir=None, max_bytes=None):
        return {
            "sets": [
                {
                    "setID": 806,
                    "number": "80006",
                    "name": "Fresh Name",
                    "year": 2024,
                    "theme": "Fresh Theme",
                    "pieces": 777,
                    "local_images": [],
                    "local_instructions": ["80006/instructions/fresh.pdf"],
                }
            ]
        }

    monkeypatch.setattr(app.brickset_api, "get_combined_data", fake_get_combined_data)

    response = admin_client.post("/api/sets/806/refresh")

    assert response.status_code == 200
    updated = app.db_ops.get_set_by_id(806)
    assert updated["name"] == "Fresh Name"
    assert updated["local_instructions"] == ["80006/instructions/fresh.pdf"]


def test_refresh_set_failure_shows_error(app, admin_client, monkeypatch):
    app.db_ops.insert_set_data(
        {
            "setID": 807,
            "number": "80007",
            "name": "Set",
            "local_images": [],
            "local_instructions": [],
        }
    )
    monkeypatch.setattr(app.brickset_api, "get_combined_data", lambda *a, **k: None)

    response = admin_client.post("/api/sets/807/refresh")

    assert response.status_code == 422
    assert b"Failed to refresh from Brickset" in response.data


def test_get_set_parts_returns_empty_when_not_synced(app, user_client):
    app.db_ops.insert_set_data(
        {"setID": 850, "number": "80050", "name": "Set", "local_images": []}
    )

    response = user_client.get("/api/sets/850/parts")

    assert response.status_code == 200
    body = response.get_json()
    assert body["parts"] == []
    assert body["minifigs"] == []
    assert body["synced"] is False


def test_sync_set_parts_requires_admin(app, user_client):
    app.db_ops.insert_set_data(
        {"setID": 851, "number": "80051", "name": "Set", "local_images": []}
    )

    response = user_client.post("/api/sets/851/parts/sync")

    assert response.status_code == 403


def test_sync_set_parts_requires_rebrickable_configured(app, admin_client):
    app.db_ops.insert_set_data(
        {"setID": 852, "number": "80052", "name": "Set", "local_images": []}
    )
    app.rebrickable_api.configure("")

    response = admin_client.post("/api/sets/852/parts/sync")

    assert response.status_code == 400
    assert b"Rebrickable isn't configured" in response.data


def test_sync_set_parts_success_stores_and_returns_parts_and_minifigs(
    app, admin_client, monkeypatch
):
    app.db_ops.insert_set_data(
        {"setID": 853, "number": "80053", "name": "Set", "local_images": []}
    )
    app.rebrickable_api.configure("test-key")

    def fake_get_combined_set_parts(set_number, base_dir=None, max_bytes=None):
        return [
            {
                "part_num": "3001",
                "name": "Brick 2 x 4",
                "color_id": 5,
                "color_name": "Red",
                "quantity": 4,
                "image_path": None,
            }
        ]

    def fake_get_combined_set_minifigs(set_number, base_dir=None, max_bytes=None):
        return [
            {
                "fig_num": "fig-001",
                "name": "Luke Skywalker",
                "quantity": 1,
                "image_path": None,
            }
        ]

    monkeypatch.setattr(
        app.rebrickable_api, "get_combined_set_parts", fake_get_combined_set_parts
    )
    monkeypatch.setattr(
        app.rebrickable_api,
        "get_combined_set_minifigs",
        fake_get_combined_set_minifigs,
    )

    response = admin_client.post("/api/sets/853/parts/sync")

    assert response.status_code == 200
    body = response.get_json()
    assert body["synced"] is True
    assert body["parts"] == [
        {
            "part_num": "3001",
            "name": "Brick 2 x 4",
            "color_name": "Red",
            "quantity": 4,
            "image_url": None,
        }
    ]
    assert body["minifigs"] == [
        {
            "fig_num": "fig-001",
            "name": "Luke Skywalker",
            "quantity": 1,
            "image_url": None,
        }
    ]

    follow_up = admin_client.get("/api/sets/853/parts")
    follow_up_body = follow_up.get_json()
    assert follow_up_body["synced"] is True
    assert follow_up_body["minifigs"] == body["minifigs"]


def test_sync_set_parts_failure_shows_error(app, admin_client, monkeypatch):
    app.db_ops.insert_set_data(
        {"setID": 854, "number": "80054", "name": "Set", "local_images": []}
    )
    app.rebrickable_api.configure("test-key")
    monkeypatch.setattr(
        app.rebrickable_api, "get_combined_set_parts", lambda *a, **k: None
    )

    response = admin_client.post("/api/sets/854/parts/sync")

    assert response.status_code == 422
    assert b"Failed to fetch parts from Rebrickable" in response.data


def test_sync_set_parts_succeeds_even_if_minifig_fetch_fails(
    app, admin_client, monkeypatch
):
    app.db_ops.insert_set_data(
        {"setID": 855, "number": "80055", "name": "Set", "local_images": []}
    )
    app.rebrickable_api.configure("test-key")
    monkeypatch.setattr(
        app.rebrickable_api, "get_combined_set_parts", lambda *a, **k: []
    )
    monkeypatch.setattr(
        app.rebrickable_api, "get_combined_set_minifigs", lambda *a, **k: None
    )

    response = admin_client.post("/api/sets/855/parts/sync")

    assert response.status_code == 200
    body = response.get_json()
    assert body["synced"] is True
    assert body["minifigs"] == []


def test_run_missing_metadata_task_lists_incomplete_sets(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 901,
            "number": "90101",
            "name": "Complete Set",
            "year": 2024,
            "theme": "Complete",
            "pieces": 100,
            "local_images": ["90101/images/x.jpg"],
            "local_instructions": ["90101/instructions/y.pdf"],
        }
    )
    app.db_ops.insert_set_data(
        {
            "setID": 902,
            "number": "90102",
            "name": "Incomplete Set",
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.post("/api/utility/missing-metadata/run")

    assert response.status_code == 200
    results = response.get_json()["results"]
    names = {r["name"] for r in results}
    assert "Incomplete Set" in names
    assert "Complete Set" not in names


def test_run_missing_metadata_task_no_gaps_returns_empty(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 903,
            "number": "90103",
            "name": "Complete Set",
            "year": 2024,
            "theme": "Complete",
            "pieces": 100,
            "local_images": ["90103/images/x.jpg"],
            "local_instructions": ["90103/instructions/y.pdf"],
        }
    )

    response = admin_client.post("/api/utility/missing-metadata/run")

    assert response.status_code == 200
    assert response.get_json()["results"] == []


def test_run_missing_metadata_flags_unsynced_parts_and_minifigs(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 904,
            "number": "90104",
            "name": "Needs Sync",
            "year": 2024,
            "theme": "Complete",
            "pieces": 100,
            "local_images": ["90104/images/x.jpg"],
            "local_instructions": ["90104/instructions/y.pdf"],
        }
    )
    app.rebrickable_api.configure("test-key")

    response = admin_client.post("/api/utility/missing-metadata/run")

    assert response.status_code == 200
    body = response.get_json()
    assert body["rebrickable_configured"] is True
    result = next(r for r in body["results"] if r["setID"] == 904)
    assert "parts" in result["missing_fields"]
    assert "minifigs" in result["missing_fields"]


def test_run_missing_metadata_ignores_parts_when_rebrickable_not_configured(
    app, admin_client
):
    app.db_ops.insert_set_data(
        {
            "setID": 905,
            "number": "90105",
            "name": "No Rebrickable",
            "year": 2024,
            "theme": "Complete",
            "pieces": 100,
            "local_images": ["90105/images/x.jpg"],
            "local_instructions": ["90105/instructions/y.pdf"],
        }
    )

    response = admin_client.post("/api/utility/missing-metadata/run")

    assert response.status_code == 200
    body = response.get_json()
    assert body["rebrickable_configured"] is False
    assert body["results"] == []


def test_run_missing_metadata_clears_parts_flag_once_synced(
    app, admin_client, monkeypatch
):
    app.db_ops.insert_set_data(
        {
            "setID": 906,
            "number": "90106",
            "name": "Synced Set",
            "year": 2024,
            "theme": "Complete",
            "pieces": 100,
            "local_images": ["90106/images/x.jpg"],
            "local_instructions": ["90106/instructions/y.pdf"],
        }
    )
    app.rebrickable_api.configure("test-key")
    monkeypatch.setattr(
        app.rebrickable_api, "get_combined_set_parts", lambda *a, **k: []
    )
    monkeypatch.setattr(
        app.rebrickable_api, "get_combined_set_minifigs", lambda *a, **k: []
    )
    admin_client.post("/api/sets/906/parts/sync")

    response = admin_client.post("/api/utility/missing-metadata/run")

    assert response.status_code == 200
    names = {r["name"] for r in response.get_json()["results"]}
    assert "Synced Set" not in names


def test_owned_set_count_excludes_wishlist(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 970,
            "number": "1",
            "name": "Owned Set A",
            "year": 2024,
            "theme": "Icons",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )
    app.db_ops.insert_set_data(
        {
            "setID": 971,
            "number": "2",
            "name": "Owned Set B",
            "year": 2024,
            "theme": "Icons",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )
    app.db_ops.insert_set_data(
        {
            "setID": 972,
            "number": "3",
            "name": "Wishlist Set",
            "year": 2024,
            "theme": "Icons",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )
    app.db_ops.update_build_status_only(972, "wishlist")

    assert app.db_ops.count_owned_sets() == 2

    response = admin_client.get("/api/session")
    assert response.get_json()["owned_set_count"] == 2


def _tiny_jpeg_bytes():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color="blue").save(buf, format="JPEG")
    buf.seek(0)
    return buf


def test_upload_build_photos_persists_and_serves(app, user_client):
    app.db_ops.insert_set_data(
        {
            "setID": 900,
            "number": "90000",
            "name": "Photo Test Set",
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = user_client.post(
        "/api/sets/900/photos",
        data={"photos": (_tiny_jpeg_bytes(), "finished.jpg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert len(payload["build_photos"]) == 1
    assert payload["build_photos"][0].endswith("finished.jpg")
    assert payload["build_photo_urls"][0].startswith("/files/sets/")

    updated = app.db_ops.get_set_by_id(900)
    assert updated["build_photos"] == payload["build_photos"]

    import os

    saved_path = os.path.join(app.config["SETS_DIR"], updated["build_photos"][0])
    assert os.path.isfile(saved_path)

    static_response = user_client.get(payload["build_photo_urls"][0])
    assert static_response.status_code == 200


def test_upload_build_photos_multiple_files_appends(app, user_client):
    app.db_ops.insert_set_data(
        {
            "setID": 901,
            "number": "90001",
            "name": "Multi Photo Set",
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = user_client.post(
        "/api/sets/901/photos",
        data={
            "photos": [
                (_tiny_jpeg_bytes(), "one.jpg"),
                (_tiny_jpeg_bytes(), "two.jpg"),
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert len(response.get_json()["build_photos"]) == 2

    # Uploading again with a same-named file should not clobber the first.
    response2 = user_client.post(
        "/api/sets/901/photos",
        data={"photos": (_tiny_jpeg_bytes(), "one.jpg")},
        content_type="multipart/form-data",
    )
    assert response2.status_code == 201
    updated = app.db_ops.get_set_by_id(901)
    assert len(updated["build_photos"]) == 3
    assert len(set(updated["build_photos"])) == 3


def test_upload_build_photos_rejects_bad_extension(app, user_client):
    import io

    app.db_ops.insert_set_data(
        {
            "setID": 902,
            "number": "90002",
            "name": "Bad Ext Set",
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = user_client.post(
        "/api/sets/902/photos",
        data={"photos": (io.BytesIO(b"not-an-image"), "virus.exe")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert app.db_ops.get_set_by_id(902)["build_photos"] == []


def test_upload_build_photos_rejects_non_image_content(app, user_client):
    import io

    app.db_ops.insert_set_data(
        {
            "setID": 903,
            "number": "90003",
            "name": "Fake Image Set",
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = user_client.post(
        "/api/sets/903/photos",
        data={"photos": (io.BytesIO(b"not-really-a-jpeg"), "fake.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert app.db_ops.get_set_by_id(903)["build_photos"] == []


def test_upload_build_photos_requires_at_least_one_file(user_client):
    response = user_client.post(
        "/api/sets/900/photos",
        data={},
        content_type="multipart/form-data",
    )
    assert response.status_code in (400, 404)


def test_upload_build_photos_404_for_missing_set(user_client):
    response = user_client.post(
        "/api/sets/999/photos",
        data={"photos": (_tiny_jpeg_bytes(), "x.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 404


def test_delete_build_photo_removes_file_and_db_entry(app, user_client):
    app.db_ops.insert_set_data(
        {
            "setID": 904,
            "number": "90004",
            "name": "Delete Photo Set",
            "local_images": [],
            "local_instructions": [],
        }
    )
    upload = user_client.post(
        "/api/sets/904/photos",
        data={"photos": (_tiny_jpeg_bytes(), "deleteme.jpg")},
        content_type="multipart/form-data",
    )
    rel_path = upload.get_json()["build_photos"][0]

    import os

    saved_path = os.path.join(app.config["SETS_DIR"], rel_path)
    assert os.path.isfile(saved_path)

    response = user_client.delete("/api/sets/904/photos", json={"path": rel_path})
    assert response.status_code == 200
    assert app.db_ops.get_set_by_id(904)["build_photos"] == []
    assert not os.path.isfile(saved_path)


def test_delete_build_photo_404_for_unknown_path(app, user_client):
    app.db_ops.insert_set_data(
        {
            "setID": 905,
            "number": "90005",
            "name": "No Photo Set",
            "local_images": [],
            "local_instructions": [],
        }
    )
    response = user_client.delete(
        "/api/sets/905/photos", json={"path": "90005/build_photos/ghost.jpg"}
    )
    assert response.status_code == 404


def test_delete_build_photo_404_for_missing_set(user_client):
    response = user_client.delete("/api/sets/999/photos", json={"path": "x/y.jpg"})
    assert response.status_code == 404
