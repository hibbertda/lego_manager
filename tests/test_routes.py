def test_index_redirects_to_my_sets(admin_client):
    response = admin_client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/setlist")


def test_index_follow_redirect_shows_my_sets(admin_client):
    response = admin_client.get("/", follow_redirects=True)
    assert response.status_code == 200
    assert b"LEGO Manager" in response.data


def test_list_sets_empty(admin_client):
    response = admin_client.get("/setlist")
    assert response.status_code == 200
    assert b"No sets yet" in response.data


def test_search_without_query_shows_form_only(admin_client):
    response = admin_client.get("/search")
    assert response.status_code == 200
    assert b"Search Sets" in response.data


def test_search_suggest_requires_login(client):
    response = client.get("/search/suggest?query=star")
    assert response.status_code in (302, 401)


def test_search_suggest_empty_query_returns_empty_results(admin_client):
    response = admin_client.get("/search/suggest?query=")
    assert response.status_code == 200
    assert response.get_json() == {"results": []}


def test_search_suggest_no_matches(admin_client):
    response = admin_client.get("/search/suggest?query=zzz_no_such_set")
    assert response.status_code == 200
    data = response.get_json()
    assert data["results"] == []
    assert data["total"] == 0


def test_set_detail_404_for_missing_set(admin_client):
    response = admin_client.get("/set/999")
    assert response.status_code == 404


def test_custom_static_blocks_path_traversal(admin_client):
    response = admin_client.get("/sets/../../etc/passwd")
    assert response.status_code == 404


def test_add_set_page_redirects_to_my_sets_with_modal(admin_client):
    """GET /add_set is no longer a standalone page — adding a set now happens
    via the "Add a Set" modal embedded on every page (see base.html)."""
    response = admin_client.get("/add_set", follow_redirects=True)
    assert response.status_code == 200
    assert b"Set Number" in response.data
    assert b"Add Manually" in response.data


def test_add_set_manual_requires_name_and_number(admin_client):
    response = admin_client.post(
        "/add_set/manual",
        data={"csrf_token": "", "set_number": "", "name": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Set number and name are required" in response.data


def test_add_set_manual_creates_set_without_files(app, admin_client):
    response = admin_client.post(
        "/add_set/manual",
        data={
            "csrf_token": "",
            "set_number": "99999",
            "name": "Manually Added Set",
            "year": "2024",
            "theme": "Custom",
            "pieces": "42",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Manually Added Set" in response.data

    sets_data, total = app.db_ops.list_sets()
    assert total == 1
    assert sets_data[0]["name"] == "Manually Added Set"
    assert sets_data[0]["setID"] < 0
    assert sets_data[0]["local_images"] == []
    assert sets_data[0]["local_instructions"] == []


def test_add_set_manual_with_image_and_pdf(app, admin_client):
    import io

    from PIL import Image

    image_bytes = io.BytesIO()
    Image.new("RGB", (1, 1), color="red").save(image_bytes, format="JPEG")
    image_bytes.seek(0)

    response = admin_client.post(
        "/add_set/manual",
        data={
            "csrf_token": "",
            "set_number": "88888",
            "name": "Set With Files",
            "image": (image_bytes, "box.jpg"),
            "instructions": (io.BytesIO(b"%PDF-1.4 fake"), "manual.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200

    sets_data, _ = app.db_ops.list_sets()
    added = next(s for s in sets_data if s["name"] == "Set With Files")
    assert len(added["local_images"]) == 1
    assert added["local_images"][0].endswith("box.jpg")
    assert len(added["local_instructions"]) == 1
    assert added["local_instructions"][0].endswith("manual.pdf")

    import os

    saved_image_path = os.path.join(app.config["SETS_DIR"], added["local_images"][0])
    assert os.path.isfile(saved_image_path)


def test_add_set_manual_rejects_bad_image_extension(admin_client):
    import io

    response = admin_client.post(
        "/add_set/manual",
        data={
            "csrf_token": "",
            "set_number": "77777",
            "name": "Bad Image Set",
            "image": (io.BytesIO(b"not-an-image"), "virus.exe"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Image must be a PNG, JPG, GIF, or WEBP file" in response.data


def test_add_set_manual_rejects_non_image_content_with_valid_extension(admin_client):
    import io

    response = admin_client.post(
        "/add_set/manual",
        data={
            "csrf_token": "",
            "set_number": "66666",
            "name": "Spoofed Image Set",
            "image": (io.BytesIO(b"not-actually-a-jpeg"), "box.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Image file is corrupt or is not a valid image" in response.data


def test_add_set_manual_rejects_non_pdf_content_with_valid_extension(admin_client):
    import io

    response = admin_client.post(
        "/add_set/manual",
        data={
            "csrf_token": "",
            "set_number": "55555",
            "name": "Spoofed PDF Set",
            "instructions": (io.BytesIO(b"not-a-real-pdf"), "manual.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Instructions file is not a valid PDF" in response.data


def test_two_manual_sets_get_distinct_negative_ids(app, admin_client):
    admin_client.post(
        "/add_set/manual",
        data={"csrf_token": "", "set_number": "11111", "name": "First Manual Set"},
        follow_redirects=True,
    )
    admin_client.post(
        "/add_set/manual",
        data={"csrf_token": "", "set_number": "22222", "name": "Second Manual Set"},
        follow_redirects=True,
    )
    sets_data, total = app.db_ops.list_sets()
    assert total == 2
    ids = {s["setID"] for s in sets_data}
    assert len(ids) == 2
    assert all(i < 0 for i in ids)


def test_update_progress_persists_and_redirects(app, admin_client):
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
        "/set/500/progress", data={"build_page": "12", "build_status": "in_progress"}
    )
    assert response.status_code == 302

    updated = app.db_ops.get_set_by_id(500)
    assert updated["build_page"] == 12
    assert updated["build_status"] == "in_progress"


def test_update_progress_404_for_missing_set(admin_client):
    response = admin_client.post(
        "/set/999/progress", data={"build_page": "1", "build_status": "in_progress"}
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

    response = admin_client.post("/set/501/progress/page", json={"build_page": 7})
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

    admin_client.post("/set/502/progress/page", json={"build_page": 41})

    updated = app.db_ops.get_set_by_id(502)
    assert updated["build_page"] == 41
    assert updated["build_status"] == "complete"


def test_update_progress_page_404_for_missing_set(admin_client):
    response = admin_client.post("/set/999/progress/page", json={"build_page": 1})
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
        "/set/503/progress/page", json={"build_page": "not-a-number"}
    )
    assert response.status_code == 400


def test_delete_set_removes_it_and_its_files(app, admin_client, tmp_path):
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

    response = admin_client.post("/set/501/delete")
    assert response.status_code == 302
    assert app.db_ops.get_set_by_id(501) is None
    assert not os.path.isdir(set_dir)


def test_delete_set_404_for_missing_set(admin_client):
    response = admin_client.post("/set/999/delete")
    assert response.status_code == 404


def test_list_sets_view_toggle_and_theme_filter(app, admin_client):
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

    grid_response = admin_client.get("/setlist?view=grid")
    assert grid_response.status_code == 200
    assert b"Set A" in grid_response.data and b"Set B" in grid_response.data

    filtered_response = admin_client.get("/setlist?theme=Technic")
    assert filtered_response.status_code == 200
    assert b"Set B" in filtered_response.data
    assert b"Set A" not in filtered_response.data


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

    year_response = admin_client.get("/setlist?sort=year")
    assert year_response.status_code == 200
    assert year_response.data.index(b"Apple Set") < year_response.data.index(
        b"Zebra Set"
    )

    default_response = admin_client.get("/setlist")
    assert default_response.data.index(b"Apple Set") < default_response.data.index(
        b"Zebra Set"
    )

    bogus_response = admin_client.get("/setlist?sort=bogus")
    assert bogus_response.status_code == 200
    assert bogus_response.data.index(b"Apple Set") < bogus_response.data.index(
        b"Zebra Set"
    )


def test_list_sets_defaults_to_grid_view(app, admin_client):
    app.db_ops.insert_set_data(
        {
            "setID": 706,
            "number": "1",
            "name": "Default View Set",
            "year": 2024,
            "theme": "Star Wars",
            "pieces": 1,
            "local_images": [],
            "local_instructions": [],
        }
    )

    response = admin_client.get("/setlist")
    assert response.status_code == 200
    assert b"set-grid-card" in response.data


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

    response = admin_client.post("/set/701/favorite")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "favorite": True}

    response = admin_client.post("/set/701/favorite")
    assert response.get_json() == {"ok": True, "favorite": False}


def test_toggle_favorite_404_for_missing_set(admin_client):
    response = admin_client.post("/set/999/favorite")
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

    response = admin_client.post("/set/702/status", json={"build_status": "storage"})
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

    response = admin_client.post("/set/703/status", json={"build_status": "bogus"})
    assert response.status_code == 400


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
    admin_client.post("/set/704/favorite")

    response = admin_client.get("/setlist?favorite=1")
    assert response.status_code == 200
    assert b"Set Fave" in response.data
    assert b"Set Plain" not in response.data


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
        "/set/801/edit",
        data={
            "csrf_token": "",
            "name": "New Name",
            "year": "2024",
            "theme": "New Theme",
            "pieces": "500",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Set updated" in response.data
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

    response = admin_client.post(
        "/set/802/edit",
        data={"csrf_token": "", "name": ""},
        follow_redirects=True,
    )

    assert response.status_code == 200
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
        "/set/803/edit",
        data={
            "csrf_token": "",
            "name": "Instr Set",
            "instructions": (io.BytesIO(b"%PDF-1.4 fake"), "extra.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
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
        "/set/804/edit",
        data={
            "csrf_token": "",
            "name": "Instr Set",
            "instructions": (io.BytesIO(b"not-a-pdf"), "extra.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Instructions file is not a valid PDF" in response.data
    assert app.db_ops.get_set_by_id(804)["local_instructions"] == []


def test_edit_set_404_for_missing_set(admin_client):
    response = admin_client.post("/set/999/edit", data={"csrf_token": "", "name": "X"})
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
    response = user_client.post(
        "/set/805/edit", data={"csrf_token": "", "name": "Hacked"}
    )
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

    response = admin_client.post("/set/-1/refresh", follow_redirects=True)

    assert response.status_code == 200
    assert b"isn&#39;t linked to Brickset" in response.data


def test_refresh_set_404_for_missing_set(admin_client):
    response = admin_client.post("/set/999/refresh")
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

    response = admin_client.post("/set/806/refresh", follow_redirects=True)

    assert response.status_code == 200
    assert b"Set refreshed from Brickset" in response.data
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

    response = admin_client.post("/set/807/refresh", follow_redirects=True)

    assert response.status_code == 200
    assert b"Failed to refresh from Brickset" in response.data


def test_admin_tasks_page_loads(admin_client):
    response = admin_client.get("/admin/tasks")
    assert response.status_code == 200
    assert b"Find sets with missing metadata" in response.data


def test_admin_tasks_page_forbidden_for_non_admin(user_client):
    response = user_client.get("/admin/tasks")
    assert response.status_code == 403


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

    response = admin_client.post(
        "/admin/tasks/missing_metadata/run",
        data={"csrf_token": ""},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Incomplete Set" in response.data
    assert b"Complete Set" not in response.data


def test_run_missing_metadata_task_no_gaps_shows_success(app, admin_client):
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

    response = admin_client.post(
        "/admin/tasks/missing_metadata/run",
        data={"csrf_token": ""},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"No sets are missing metadata" in response.data


def test_run_unknown_task_404s(admin_client):
    response = admin_client.post(
        "/admin/tasks/not-a-real-task/run", data={"csrf_token": ""}
    )
    assert response.status_code == 404
