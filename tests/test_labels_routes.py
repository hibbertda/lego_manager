SAMPLE_MANUAL_SET_FORM = {
    "csrf_token": "",
    "set_number": "88888",
    "name": "Label Test Set",
    "year": "2024",
    "theme": "Custom",
    "pieces": "10",
}


def test_add_set_manual_generates_label_when_base_url_configured(app, admin_client):
    app.config["APP_BASE_URL"] = "https://lego.example.com"

    response = admin_client.post(
        "/add_set/manual", data=SAMPLE_MANUAL_SET_FORM, follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Show label" in response.data


def test_add_set_manual_skips_label_without_base_url(app, admin_client):
    app.config["APP_BASE_URL"] = None

    response = admin_client.post(
        "/add_set/manual", data=SAMPLE_MANUAL_SET_FORM, follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Show label" not in response.data


def test_set_label_page_404_without_label(admin_client):
    response = admin_client.post(
        "/add_set/manual", data=SAMPLE_MANUAL_SET_FORM, follow_redirects=True
    )
    set_id = -1  # first manually-added set
    response = admin_client.get(f"/set/{set_id}/label")
    assert response.status_code == 404


def test_set_label_page_and_image_when_configured(app, admin_client):
    app.config["APP_BASE_URL"] = "https://lego.example.com"
    admin_client.post(
        "/add_set/manual", data=SAMPLE_MANUAL_SET_FORM, follow_redirects=True
    )
    set_id = -1

    view_response = admin_client.get(f"/set/{set_id}/label")
    assert view_response.status_code == 200

    image_response = admin_client.get(f"/set/{set_id}/label/image")
    assert image_response.status_code == 200
    assert image_response.content_type == "image/png"


def test_utility_labels_warns_when_base_url_missing(app, admin_client):
    app.config["APP_BASE_URL"] = None
    response = admin_client.get("/utility/labels")
    assert response.status_code == 200
    assert b"APP_BASE_URL is not set" in response.data


def test_utility_labels_lists_generated_labels(app, admin_client):
    app.config["APP_BASE_URL"] = "https://lego.example.com"
    admin_client.post(
        "/add_set/manual", data=SAMPLE_MANUAL_SET_FORM, follow_redirects=True
    )

    response = admin_client.get("/utility/labels")
    assert response.status_code == 200
    assert b"Label Test Set" in response.data
    assert b"APP_BASE_URL is not set" not in response.data


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

    response = admin_client.post("/admin/tasks/missing_metadata/run")
    assert response.status_code == 200
    assert b"Complete Set" in response.data
    assert b"label" in response.data
