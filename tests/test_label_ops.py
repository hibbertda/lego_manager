import os

from PIL import Image

from app import label_ops

SET_DATA = {
    "setID": 111,
    "setNumber": "75386",
    "name": "Test Set",
    "theme": "Star Wars",
    "pieces": 500,
    "local_images": [],
}


def test_generate_label_returns_none_without_base_url(tmp_path):
    result = label_ops.generate_label(SET_DATA, str(tmp_path), None)
    assert result is None
    assert not label_ops.label_exists(SET_DATA, str(tmp_path))


def test_generate_label_creates_png_of_expected_size(tmp_path):
    rel_path = label_ops.generate_label(
        SET_DATA, str(tmp_path), "https://lego.example.com"
    )

    assert rel_path == os.path.join("75386", "label_111.png")
    abs_path = os.path.join(str(tmp_path), rel_path)
    assert os.path.isfile(abs_path)
    with Image.open(abs_path) as img:
        assert img.size == (label_ops.LABEL_WIDTH, label_ops.LABEL_HEIGHT)
    assert label_ops.label_exists(SET_DATA, str(tmp_path))


def test_generate_label_with_cover_image(tmp_path):
    images_dir = tmp_path / "75386" / "images"
    images_dir.mkdir(parents=True)
    cover_rel = os.path.join("75386", "images", "cover.jpg")
    Image.new("RGB", (400, 300), (10, 20, 30)).save(tmp_path / cover_rel)

    set_data = dict(SET_DATA, local_images=[cover_rel])
    rel_path = label_ops.generate_label(
        set_data, str(tmp_path), "https://lego.example.com"
    )

    assert rel_path is not None
    with Image.open(os.path.join(str(tmp_path), rel_path)) as img:
        assert img.size == (label_ops.LABEL_WIDTH, label_ops.LABEL_HEIGHT)


def test_generate_label_missing_set_id_returns_none(tmp_path):
    set_data = dict(SET_DATA)
    del set_data["setID"]
    assert label_ops.generate_label(set_data, str(tmp_path), "https://x.test") is None


def test_label_relpath_is_keyed_by_set_id():
    other = dict(SET_DATA, setID=222)
    assert label_ops.label_relpath(SET_DATA) != label_ops.label_relpath(other)
