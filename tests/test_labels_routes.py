SAMPLE_MANUAL_SET_FORM = {
    "set_number": "88888",
    "name": "Label Test Set",
    "year": "2024",
    "theme": "Custom",
    "pieces": "10",
}


def test_add_set_manual_generates_label_when_base_url_configured(app, admin_client):
    app.config["APP_BASE_URL"] = "https://lego.example.com"

    response = admin_client.post("/api/sets/manual", data=SAMPLE_MANUAL_SET_FORM)
    assert response.status_code == 201
    set_id = response.get_json()["set_id"]

    image_response = admin_client.get(f"/set/{set_id}/label/image")
    assert image_response.status_code == 200


def test_add_set_manual_skips_label_without_base_url(app, admin_client):
    app.config["APP_BASE_URL"] = None

    response = admin_client.post("/api/sets/manual", data=SAMPLE_MANUAL_SET_FORM)
    assert response.status_code == 201
    set_id = response.get_json()["set_id"]

    image_response = admin_client.get(f"/set/{set_id}/label/image")
    assert image_response.status_code == 404


def test_set_label_page_404_without_label(admin_client):
    admin_client.post("/api/sets/manual", data=SAMPLE_MANUAL_SET_FORM)
    set_id = -1  # first manually-added set
    response = admin_client.get(f"/set/{set_id}/label")
    assert response.status_code == 404


def test_set_label_page_and_image_when_configured(app, admin_client):
    app.config["APP_BASE_URL"] = "https://lego.example.com"
    admin_client.post("/api/sets/manual", data=SAMPLE_MANUAL_SET_FORM)
    set_id = -1

    view_response = admin_client.get(f"/set/{set_id}/label")
    assert view_response.status_code == 200

    image_response = admin_client.get(f"/set/{set_id}/label/image")
    assert image_response.status_code == 200
    assert image_response.content_type == "image/png"


def test_utility_labels_warns_when_base_url_missing(app, admin_client):
    app.config["APP_BASE_URL"] = None
    response = admin_client.get("/api/utility/labels")
    assert response.status_code == 200
    assert response.get_json()["base_url_configured"] is False


def test_utility_labels_lists_generated_labels(app, admin_client):
    app.config["APP_BASE_URL"] = "https://lego.example.com"
    admin_client.post("/api/sets/manual", data=SAMPLE_MANUAL_SET_FORM)

    response = admin_client.get("/api/utility/labels")
    assert response.status_code == 200
    body = response.get_json()
    assert body["base_url_configured"] is True
    assert any(s["name"] == "Label Test Set" for s in body["sets"])


def test_missing_metadata_task_flags_missing_label(app, admin_client):
    app.config["APP_BASE_URL"] = "https://lego.example.com"
    # Insert a fully-complete set directly (bypassing add_set_manual's own
    # label generation) so the only thing "missing" is the label itself.
    set_data = {
        "setID": 5001,
        "number": "12345",
        "numberVariant": 1,
        "name": "Complete Set",
        "year": 2024,
        "theme": "Custom",
        "pieces": 100,
        "launchDate": None,
        "instructions": [],
        "local_images": ["12345/images/cover.jpg"],
        "local_instructions": ["12345/instructions/1.pdf"],
    }
    app.db_ops.insert_set_data(set_data)

    response = admin_client.post("/api/utility/missing-metadata/run")
    assert response.status_code == 200
    results = response.get_json()["results"]
    match = next(r for r in results if r["name"] == "Complete Set")
    assert "label" in match["missing_fields"]
