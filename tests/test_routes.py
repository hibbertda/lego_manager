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
    from sql_ops import DatabaseOps

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

    response = admin_client.post("/set/500/progress", data={"build_page": "12", "build_status": "in_progress"})
    assert response.status_code == 302

    updated = app.db_ops.get_set_by_id(500)
    assert updated["build_page"] == 12
    assert updated["build_status"] == "in_progress"


def test_update_progress_404_for_missing_set(admin_client):
    response = admin_client.post("/set/999/progress", data={"build_page": "1", "build_status": "in_progress"})
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

    response = admin_client.post("/set/503/progress/page", json={"build_page": "not-a-number"})
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
    app.db_ops.insert_set_data({
        "setID": 601, "number": "1", "name": "Set A", "year": 2024,
        "theme": "Star Wars", "pieces": 1, "local_images": [], "local_instructions": [],
    })
    app.db_ops.insert_set_data({
        "setID": 602, "number": "2", "name": "Set B", "year": 2024,
        "theme": "Technic", "pieces": 1, "local_images": [], "local_instructions": [],
    })

    grid_response = admin_client.get("/setlist?view=grid")
    assert grid_response.status_code == 200
    assert b"Set A" in grid_response.data and b"Set B" in grid_response.data

    filtered_response = admin_client.get("/setlist?theme=Technic")
    assert filtered_response.status_code == 200
    assert b"Set B" in filtered_response.data
    assert b"Set A" not in filtered_response.data
