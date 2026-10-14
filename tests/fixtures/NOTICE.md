# Notice about the recorded pages in this folder

Some fixtures in `tests/fixtures/` are recorded copies of public calendar pages and feeds (the `page.*` files).

- They are kept only to test the scrapers. They are not part of the software.
- They are **not** covered by this repository's MIT licence. Copyright stays with their publishers.
- Before saving, descriptions, images and anything about people are removed. What remains is event facts and links.

## The other files in a case folder

- `source.json` and `fetched.json` are written for these tests and are covered by the MIT licence.
- `expected.json` and `dropped.json`: the MIT licence covers only our own field names and structure. The event titles, places, times and links in them come from the publisher and are not ours to license.

## Removal

When a publisher asks for its page to be removed, the whole case folder is deleted, not only the `page.*` file. Open an issue, or contact the people who run this repository.
