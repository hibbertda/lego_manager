from pathlib import Path

from app.brickset_ops import BricksetAPI


class FakeResponse:
    def __init__(self, chunks, content_length=None):
        self.chunks = chunks
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        return iter(self.chunks)


class FakeSession:
    def __init__(self, response):
        self.response = response

    def get(self, *args, **kwargs):
        assert kwargs["stream"] is True
        return self.response


def test_download_images_uses_configured_directory_and_relative_path(tmp_path):
    api = BricksetAPI("key")
    api.session = FakeSession(FakeResponse([b"image"]))
    set_data = {"number": "123", "image": {"imageURL": "https://example.test/box.jpg"}}

    api.download_images(set_data, base_dir=str(tmp_path))

    assert set_data["local_images"] == ["123/images/box.jpg"]
    assert (tmp_path / "123" / "images" / "box.jpg").read_bytes() == b"image"


def test_download_rejects_oversized_content_length(tmp_path):
    api = BricksetAPI("key")
    api.session = FakeSession(FakeResponse([b"image"], content_length=6))
    path = Path(tmp_path) / "image.jpg"

    assert api._download_file("https://example.test/image.jpg", str(path), 5) is False
    assert not path.exists()
