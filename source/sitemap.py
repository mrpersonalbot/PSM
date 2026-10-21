import re
from html.parser import HTMLParser
from pathlib import Path


class _RobotsAndCanonicalParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.canonical_hrefs = []
        self.robots_contents = []

    def handle_starttag(self, tag, attrs):
        attributes = {name.casefold(): value or "" for name, value in attrs}
        if tag.casefold() == "link":
            rel_tokens = {token.casefold() for token in attributes.get("rel", "").split()}
            if "canonical" in rel_tokens:
                self.canonical_hrefs.append(attributes.get("href", "").strip())
        elif tag.casefold() == "meta":
            name = attributes.get("name", "").strip().casefold()
            if name == "robots" or "bot" in name:
                self.robots_contents.append(attributes.get("content", ""))


def indexable_canonical_urls(dist: Path, site_url: str) -> list[str]:
    """Return generated index.html routes that are self-canonical and indexable.

    Pages with missing or ambiguous canonical declarations fail the build rather
    than silently entering the sitemap. A page whose canonical points elsewhere
    or whose robots directives include noindex/none is omitted.
    """
    dist = Path(dist)
    base_url = site_url.rstrip("/")
    urls = []
    seen = set()

    for page in sorted(dist.rglob("index.html")):
        parts = page.relative_to(dist).parts
        route = "/" if parts == ("index.html",) else "/" + "/".join(parts[:-1]) + "/"
        expected_canonical = base_url + route

        parser = _RobotsAndCanonicalParser()
        parser.feed(page.read_text(encoding="utf-8"))
        parser.close()

        if len(parser.canonical_hrefs) != 1:
            raise ValueError(
                f"{page}: expected exactly one canonical link, "
                f"found {len(parser.canonical_hrefs)}"
            )
        if parser.canonical_hrefs[0] != expected_canonical:
            continue

        directives = {
            directive.casefold()
            for content in parser.robots_contents
            for directive in re.split(r"[\s,;]+", content.strip())
            if directive
        }
        if {"noindex", "none"} & directives:
            continue

        if expected_canonical in seen:
            raise ValueError(f"Duplicate canonical sitemap URL: {expected_canonical}")
        seen.add(expected_canonical)
        urls.append(expected_canonical)

    return urls
