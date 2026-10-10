from app.rebrickable_ops import RebrickableAPI


class FakeResponse:
    def __init__(self, json_data=None, chunks=None, content_length=None):
        self._json_data = json_data
        self.chunks = chunks or []
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data

    def iter_content(self, chunk_size):
        return iter(self.chunks)


class FakeSession:
    """Routes .get() calls to canned responses by URL, mimicking Rebrickable's
    paginated parts listing (via `next`) plus the part image downloads that
    follow it."""

    def __init__(self, pages, images):
        self.pages = pages
        self.images = images
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None, stream=None):
        self.calls.append(url)
        if url in self.pages:
            return FakeResponse(json_data=self.pages[url])
        if url in self.images:
            return FakeResponse(chunks=[self.images[url]])
        raise AssertionError(f"Unexpected URL requested: {url}")


def _page_url(set_number: str) -> str:
    return f"https://rebrickable.com/api/v3/lego/sets/{set_number}-1/parts/"


def test_get_set_parts_follows_pagination():
    first_url = _page_url("75192")
    second_url = "https://rebrickable.com/api/v3/lego/sets/75192-1/parts/?page=2"
    api = RebrickableAPI("key")
    api.session = FakeSession(
        pages={
            first_url: {
                "next": second_url,
                "results": [{"part": {"part_num": "3001"}, "quantity": 2}],
            },
            second_url: {
                "next": None,
                "results": [{"part": {"part_num": "3002"}, "quantity": 1}],
            },
        },
        images={},
    )

    results = api.get_set_parts("75192")

    assert [r["part"]["part_num"] for r in results] == ["3001", "3002"]


def test_get_set_parts_returns_none_on_request_failure():
    import requests

    class FailingSession:
        def get(self, *a, **k):
            raise requests.RequestException("boom")

    api = RebrickableAPI("key")
    api.session = FailingSession()

    assert api.get_set_parts("75192") is None


def test_get_combined_set_parts_merges_spares_and_downloads_images(tmp_path):
    url = _page_url("123")
    image_url = "https://example.test/parts/3001.jpg"
    api = RebrickableAPI("key")
    api.session = FakeSession(
        pages={
            url: {
                "next": None,
                "results": [
                    {
                        "part": {
                            "part_num": "3001",
                            "name": "Brick 2 x 4",
                            "part_img_url": image_url,
                        },
                        "color": {"id": 5, "name": "Red"},
                        "quantity": 4,
                        "is_spare": False,
                    },
                    {
                        "part": {
                            "part_num": "3001",
                            "name": "Brick 2 x 4",
                            "part_img_url": image_url,
                        },
                        "color": {"id": 5, "name": "Red"},
                        "quantity": 1,
                        "is_spare": True,
                    },
                ],
            }
        },
        images={image_url: b"part-image"},
    )

    parts = api.get_combined_set_parts("123", base_dir=str(tmp_path))

    assert len(parts) == 1
    part = parts[0]
    assert part["part_num"] == "3001"
    assert part["quantity"] == 5
    assert part["color_name"] == "Red"
    assert part["image_path"] == "_parts_cache/3001_5.jpg"
    assert (tmp_path / "_parts_cache" / "3001_5.jpg").read_bytes() == b"part-image"


def test_get_combined_set_parts_returns_none_when_fetch_fails():
    api = RebrickableAPI("key")

    class FailingSession:
        def get(self, *a, **k):
            import requests

            raise requests.RequestException("boom")

    api.session = FailingSession()

    assert api.get_combined_set_parts("123", base_dir="/tmp/unused") is None


def _minifigs_url(set_number: str) -> str:
    return f"https://rebrickable.com/api/v3/lego/sets/{set_number}-1/minifigs/"


def test_get_set_minifigs_follows_pagination():
    first_url = _minifigs_url("75192")
    second_url = "https://rebrickable.com/api/v3/lego/sets/75192-1/minifigs/?page=2"
    api = RebrickableAPI("key")
    api.session = FakeSession(
        pages={
            first_url: {
                "next": second_url,
                "results": [{"set_num": "fig-001", "quantity": 1}],
            },
            second_url: {
                "next": None,
                "results": [{"set_num": "fig-002", "quantity": 1}],
            },
        },
        images={},
    )

    results = api.get_set_minifigs("75192")

    assert [r["set_num"] for r in results] == ["fig-001", "fig-002"]


def test_get_combined_set_minifigs_downloads_images_and_sorts(tmp_path):
    url = _minifigs_url("123")
    image_url = "https://example.test/minifigs/fig-001.jpg"
    api = RebrickableAPI("key")
    api.session = FakeSession(
        pages={
            url: {
                "next": None,
                "results": [
                    {
                        "set_num": "fig-002",
                        "set_name": "Darth Vader",
                        "quantity": 1,
                        "img_url": None,
                    },
                    {
                        "set_num": "fig-001",
                        "set_name": "Luke Skywalker",
                        "quantity": 2,
                        "img_url": image_url,
                    },
                ],
            }
        },
        images={image_url: b"fig-image"},
    )

    minifigs = api.get_combined_set_minifigs("123", base_dir=str(tmp_path))

    assert [m["fig_num"] for m in minifigs] == ["fig-002", "fig-001"]
    luke = minifigs[1]
    assert luke["quantity"] == 2
    assert luke["image_path"] == "_minifigs_cache/fig-001.jpg"
    assert (tmp_path / "_minifigs_cache" / "fig-001.jpg").read_bytes() == b"fig-image"
    vader = minifigs[0]
    assert vader["image_path"] is None


def test_get_combined_set_minifigs_returns_none_when_fetch_fails():
    api = RebrickableAPI("key")

    class FailingSession:
        def get(self, *a, **k):
            import requests

            raise requests.RequestException("boom")

    api.session = FailingSession()

    assert api.get_combined_set_minifigs("123", base_dir="/tmp/unused") is None
