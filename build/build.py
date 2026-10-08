#!/usr/bin/env python3
"""
eShelf Build Script
Scans books/ recursively, extracts metadata, validates limits,
and generates minimal, highly-compatible static HTML pages optimized
for e-ink devices (like Kobo Nia).

Standard library only. No external dependencies.
"""

import os
import sys
import re
import json
import html
import subprocess
import urllib.parse
from datetime import datetime

# Configuration
PAGE_SIZE = 200
WARN_SIZE_BYTES = 50 * 1024 * 1024    # 50 MB GitHub warning threshold
MAX_SIZE_BYTES = 100 * 1024 * 1024   # 100 MB GitHub hard limit

SUPPORTED_EXTENSIONS = (
    ".kepub.epub",
    ".epub",
    ".pdf",
    ".cbz",
    ".cbr",
    ".mobi",
    ".azw3",
    ".fb2",
    ".djvu",
)

def format_size(size_bytes):
    """Formats bytes into human readable format (e.g. 1.2 MB, 450 KB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def clean_title_string(raw_name):
    """Cleans raw filename into a readable title."""
    # Replace underscores and dashes between words with spaces
    title = raw_name.replace("_", " ")
    title = re.sub(r"\s*-\s*", " - ", title)
    # Collapse multiple consecutive whitespace
    title = re.sub(r"\s+", " ", title).strip()
    return title

def sort_title_key(title):
    """
    Sort key ignoring leading English articles (The, A, An).
    Case-insensitive.
    """
    cleaned = title.strip().lower()
    for article in ("the ", "a ", "an "):
        if cleaned.startswith(article):
            return cleaned[len(article):].strip()
    return cleaned

def get_date_added(file_path):
    """
    Retrieves the timestamp when the book was first added.
    Uses the first git commit that added the file (`git log --diff-filter=A`).
    Falls back to file mtime if git is unavailable or file is uncommitted.
    Never uses current build time.
    """
    try:
        rel_path = os.path.relpath(file_path)
        res = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%at", "--", rel_path],
            capture_output=True,
            text=True,
            check=False
        )
        output = res.stdout.strip().split()
        if output:
            # The earliest commit adding the file is the last output line
            return int(output[-1])
    except Exception:
        pass

    # Fallback to file modification time
    return int(os.path.getmtime(file_path))

def load_metadata_override(dirpath):
    """Loads optional metadata.json in a book's author folder."""
    meta_path = os.path.join(dirpath, "metadata.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to parse {meta_path}: {e}", file=sys.stderr)
    return {}

def scan_books(repo_root):
    """
    Recursively scans books/ directory and collects book metadata.
    Validates URL uniqueness and size limits.
    """
    books_dir = os.path.join(repo_root, "books")
    if not os.path.isdir(books_dir):
        print(f"Directory 'books' not found at {books_dir}. Creating empty directory.")
        os.makedirs(books_dir, exist_ok=True)
        return []

    books = []
    seen_urls = {}

    for root, _, files in os.walk(books_dir):
        meta_override = load_metadata_override(root)
        folder_author = os.path.basename(root)
        if folder_author == "books":
            folder_author = "Unknown Author"

        for filename in files:
            lower_name = filename.lower()
            matched_ext = None
            for ext in SUPPORTED_EXTENSIONS:
                if lower_name.endswith(ext):
                    matched_ext = ext
                    break

            if not matched_ext:
                continue

            full_path = os.path.join(root, filename)
            file_size = os.path.getsize(full_path)

            # File size verification
            if file_size > MAX_SIZE_BYTES:
                print(
                    f"ERROR: File exceeds GitHub's 100 MB hard limit: "
                    f"{full_path} ({format_size(file_size)})",
                    file=sys.stderr
                )
                sys.exit(1)

            if file_size > WARN_SIZE_BYTES:
                print(
                    f"WARNING: File exceeds 50 MB threshold: "
                    f"{full_path} ({format_size(file_size)})",
                    file=sys.stderr
                )

            # Determine file type display string
            if matched_ext == ".kepub.epub":
                file_type = "KEPUB.EPUB"
                raw_title = filename[:-11]
            else:
                file_type = matched_ext.lstrip(".").upper()
                raw_title = filename[:-len(matched_ext)]

            # Default author & title
            author = folder_author
            title = clean_title_string(raw_title)

            # Check metadata.json overrides
            override_entry = None
            if filename in meta_override:
                override_entry = meta_override[filename]
            elif raw_title in meta_override:
                override_entry = meta_override[raw_title]

            if isinstance(override_entry, dict):
                title = override_entry.get("title", title)
                author = override_entry.get("author", author)
            elif isinstance(override_entry, str):
                title = override_entry

            if "author" in meta_override and isinstance(meta_override["author"], str):
                author = meta_override["author"]

            # Compute relative path and download URL
            rel_file_path = os.path.relpath(full_path, repo_root).replace("\\", "/")
            url_parts = [urllib.parse.quote(part) for part in rel_file_path.split("/")]
            download_url = "/".join(url_parts)

            # Check duplicate URLs
            if download_url in seen_urls:
                print(
                    f"ERROR: Duplicate download URL detected: '{download_url}' "
                    f"produced by both '{seen_urls[download_url]}' and '{full_path}'",
                    file=sys.stderr
                )
                sys.exit(1)

            seen_urls[download_url] = full_path

            date_added = get_date_added(full_path)

            books.append({
                "title": title,
                "author": author,
                "file_type": file_type,
                "file_size": file_size,
                "file_size_str": format_size(file_size),
                "date_added": date_added,
                "download_url": download_url,
                "filename": filename,
            })

    return books

# Inline e-ink CSS stylesheet
CSS_STYLES = """* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: #ffffff; color: #000000;
  font-family: Georgia, "Nimbus Roman No9 L", "Times New Roman", serif;
  font-size: 18px; line-height: 1.4;
  -webkit-text-size-adjust: 100%;
}
.container { max-width: 720px; margin: 0 auto; padding: 12px 14px 40px 14px; }
header { border-bottom: 2px solid #000000; padding-bottom: 8px; margin-bottom: 12px; }
h1 { font-size: 28px; margin: 0 0 4px 0; letter-spacing: 0.5px; }
h2.author-heading {
  font-size: 22px; margin: 24px 0 8px 0;
  border-bottom: 1px solid #000000; padding-bottom: 4px;
}
.nav-bar { margin: 12px 0; padding: 4px 0; line-height: 2.2; }
.nav-link {
  display: inline-block; min-height: 48px; line-height: 48px;
  padding: 0 8px; color: #000000; font-size: 18px; text-decoration: underline;
}
.nav-current {
  display: inline-block; min-height: 48px; line-height: 48px;
  padding: 0 8px; font-weight: bold; text-decoration: none;
}
.az-nav {
  margin: 12px 0; padding: 8px 0;
  border-top: 1px solid #000000; border-bottom: 1px solid #000000;
  line-height: 2.4;
}
.az-link {
  display: inline-block; min-width: 44px; min-height: 48px;
  line-height: 48px; text-align: center; font-weight: bold;
  color: #000000; text-decoration: underline;
}
.search-container { margin: 14px 0; }
.search-label { display: block; font-weight: bold; margin-bottom: 6px; font-size: 18px; }
.search-input {
  display: block; width: 100%; height: 48px; min-height: 48px;
  padding: 8px 12px; font-size: 18px; font-family: inherit;
  color: #000000; background: #ffffff; border: 2px solid #000000;
  border-radius: 0; -webkit-appearance: none;
}
.book-count { margin: 12px 0 16px 0; font-size: 18px; }
.book-list { list-style: none; margin: 0; padding: 0; border-top: 2px solid #000000; }
.book-item { border-bottom: 2px solid #000000; padding: 14px 0; }
.book-title { font-size: 20px; font-weight: bold; margin-bottom: 4px; }
.book-author { font-size: 18px; margin-bottom: 4px; }
.book-meta { font-size: 16px; margin-bottom: 10px; }
.download-btn {
  display: inline-block; min-height: 48px; line-height: 44px;
  padding: 0 24px; border: 2px solid #000000; background: #ffffff;
  color: #000000; text-decoration: none; font-weight: bold;
  font-size: 18px; text-align: center; border-radius: 0; -webkit-appearance: none;
}
.download-btn:active { background: #000000; color: #ffffff; }
.pagination {
  margin: 24px 0; padding: 10px 0;
  border-top: 2px solid #000000; text-align: center;
}
.page-btn {
  display: inline-block; min-height: 48px; line-height: 44px;
  padding: 0 18px; margin: 0 6px; border: 2px solid #000000;
  color: #000000; text-decoration: none; font-weight: bold;
}
footer { margin-top: 36px; padding-top: 12px; border-top: 1px solid #000000; font-size: 15px; }
.back-top {
  display: inline-block; min-height: 48px; line-height: 48px;
  font-weight: bold; color: #000000; text-decoration: underline;
}"""

# Tiny inline ES5 script (under 1.2 KB)
ES5_SCRIPT = """(function() {
  var wrap = document.getElementById("search-wrap");
  var input = document.getElementById("search-input");
  var count = document.getElementById("book-count");
  if (!wrap || !input) return;
  wrap.style.display = "block";
  var items = document.getElementsByClassName("book-item");
  var groups = document.getElementsByClassName("author-group");
  var total = items.length;
  function filter() {
    var q = input.value.toLowerCase().replace(/^\\s+|\\s+$/g, "");
    var visible = 0;
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var str = item.getAttribute("data-search") || "";
      if (!q || str.indexOf(q) !== -1) {
        item.style.display = "";
        visible++;
      } else {
        item.style.display = "none";
      }
    }
    for (var g = 0; g < groups.length; g++) {
      var grp = groups[g];
      var grpItems = grp.getElementsByClassName("book-item");
      var any = false;
      for (var k = 0; k < grpItems.length; k++) {
        if (grpItems[k].style.display !== "none") {
          any = true;
          break;
        }
      }
      grp.style.display = any ? "" : "none";
    }
    if (count) {
      if (q) {
        count.innerHTML = "<strong>Showing " + visible + " of " + total + " books</strong>";
      } else {
        count.innerHTML = "<strong>" + total + " books</strong>";
      }
    }
  }
  input.addEventListener("input", filter);
  input.addEventListener("keyup", filter);
})();"""

def minify_html(raw_html):
    """
    Minifies HTML by stripping unnecessary whitespace between tags
    while keeping the content valid and lightweight.
    """
    # Remove HTML comments (except doctype)
    minified = re.sub(r"<!--(?!\[if).*?-->", "", raw_html, flags=re.DOTALL)
    # Collapse multiple whitespaces between tags
    minified = re.sub(r">\s+<", "><", minified)
    return minified.strip()

def render_sort_nav(current_view, current_page=1):
    """Renders the top sort links with current one bold and unlinked."""
    def link_or_bold(label, target_file, is_current):
        if is_current:
            return f'<strong class="nav-current">{label}</strong>'
        return f'<a href="{target_file}" class="nav-link">{label}</a>'

    index_target = "index.html"
    title_target = "title.html"
    author_target = "author.html"

    parts = [
        link_or_bold("Latest added", index_target, current_view == "latest"),
        link_or_bold("Title A→Z", title_target, current_view == "title"),
        link_or_bold("Author A→Z", author_target, current_view == "author"),
    ]
    return f'<nav class="nav-bar" aria-label="Sort options">{" | ".join(parts)}</nav>'

def render_pagination(base_name, current_page, total_pages):
    """Renders pagination links if there are multiple pages."""
    if total_pages <= 1:
        return ""

    prev_link = ""
    next_link = ""

    if current_page > 1:
        prev_target = f"{base_name}.html" if current_page == 2 else f"{base_name}-{current_page - 1}.html"
        prev_link = f'<a href="{prev_target}" class="page-btn">← Previous</a>'

    if current_page < total_pages:
        next_target = f"{base_name}-{current_page + 1}.html"
        next_link = f'<a href="{next_target}" class="page-btn">Next →</a>'

    return f"""<nav class="pagination" aria-label="Pagination">
  {prev_link}
  <span style="display:inline-block;line-height:48px;padding:0 8px;">Page {current_page} of {total_pages}</span>
  {next_link}
</nav>"""

def render_book_item(book):
    """Renders a single book list item."""
    esc_title = html.escape(book["title"])
    esc_author = html.escape(book["author"])
    esc_filename = html.escape(book["filename"])
    search_data = html.escape(f"{book['title']} {book['author']}".lower())

    return f"""<li class="book-item" data-search="{search_data}">
  <div class="book-title">{esc_title}</div>
  <div class="book-author">{esc_author}</div>
  <div class="book-meta">{book['file_type']} · {book['file_size_str']}</div>
  <div class="book-action">
    <a href="{book['download_url']}" class="download-btn" download="{esc_filename}">Download</a>
  </div>
</li>"""

def render_page(title_suffix, current_view, content_html, total_books, build_time_str,
                az_nav_html="", pagination_html="", current_page=1):
    """Assembles a complete, self-contained HTML page."""
    sort_nav = render_sort_nav(current_view, current_page)

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <meta name="description" content="eShelf - Minimal DRM-free eBook library for e-ink devices">
  <title>eShelf - {title_suffix}</title>
  <style>{CSS_STYLES}</style>
</head>
<body>
  <div class="container">
    <header id="top">
      <h1>eShelf</h1>
    </header>

    <div id="search-wrap" class="search-container" style="display:none;">
      <label for="search-input" class="search-label">Search library:</label>
      <input type="search" id="search-input" class="search-input" placeholder="Filter by title or author…" autocomplete="off">
    </div>

    {sort_nav}

    <p id="book-count" class="book-count"><strong>{total_books} books</strong></p>

    {az_nav_html}

    {content_html}

    {pagination_html}

    <footer>
      <div>Built: {build_time_str} · <a href="#top" class="back-top">Back to top</a></div>
    </footer>
  </div>
  <script>{ES5_SCRIPT}</script>
</body>
</html>"""

    return minify_html(page_html)

def build_latest_pages(books, repo_root, build_time_str):
    """Builds index.html (and index-2.html...) sorted newest first."""
    # Newest first, secondary sort title A-Z
    sorted_books = sorted(
        books,
        key=lambda b: (-b["date_added"], sort_title_key(b["title"]))
    )

    total_books = len(sorted_books)
    total_pages = max(1, (total_books + PAGE_SIZE - 1) // PAGE_SIZE) if total_books > 0 else 1

    for p in range(1, total_pages + 1):
        start_idx = (p - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_books = sorted_books[start_idx:end_idx]

        items_html = "\n".join(render_book_item(b) for b in page_books)
        content_html = f'<ul class="book-list">{items_html}</ul>'
        pagination_html = render_pagination("index", p, total_pages)

        filename = "index.html" if p == 1 else f"index-{p}.html"
        out_path = os.path.join(repo_root, filename)

        html_out = render_page(
            title_suffix="Latest added",
            current_view="latest",
            content_html=content_html,
            total_books=total_books,
            build_time_str=build_time_str,
            pagination_html=pagination_html,
            current_page=p
        )

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_out)
        print(f"Generated {filename} ({os.path.getsize(out_path)} bytes)")

def build_title_pages(books, repo_root, build_time_str):
    """Builds title.html (and title-2.html...) sorted Title A->Z."""
    sorted_books = sorted(
        books,
        key=lambda b: (sort_title_key(b["title"]), b["author"].lower())
    )

    total_books = len(sorted_books)
    total_pages = max(1, (total_books + PAGE_SIZE - 1) // PAGE_SIZE) if total_books > 0 else 1

    # Build A-Z jump links
    letters = set()
    for b in sorted_books:
        key = sort_title_key(b["title"])
        first_char = key[0].upper() if key and key[0].isalpha() else "#"
        letters.add(first_char)

    sorted_letters = sorted([l for l in letters if l != "#"])
    if "#" in letters:
        sorted_letters.append("#")

    az_links = [f'<a href="#letter-{l}" class="az-link">{l}</a>' for l in sorted_letters]
    az_nav = f'<nav class="az-nav" aria-label="Title A to Z index">Jump: {" ".join(az_links)}</nav>' if az_links else ""

    seen_page_letters = set()
    for p in range(1, total_pages + 1):
        start_idx = (p - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_books = sorted_books[start_idx:end_idx]

        items = []
        for b in page_books:
            key = sort_title_key(b["title"])
            first_char = key[0].upper() if key and key[0].isalpha() else "#"
            item_html = render_book_item(b)
            # Add anchor ID to the first book starting with this letter
            if first_char not in seen_page_letters:
                seen_page_letters.add(first_char)
                item_html = item_html.replace(
                    'class="book-item"',
                    f'id="letter-{first_char}" class="book-item"',
                    1
                )
            items.append(item_html)

        items_joined = "\n".join(items)
        content_html = f'<ul class="book-list">{items_joined}</ul>'
        pagination_html = render_pagination("title", p, total_pages)

        filename = "title.html" if p == 1 else f"title-{p}.html"
        out_path = os.path.join(repo_root, filename)

        html_out = render_page(
            title_suffix="Title A→Z",
            current_view="title",
            content_html=content_html,
            total_books=total_books,
            build_time_str=build_time_str,
            az_nav_html=az_nav,
            pagination_html=pagination_html,
            current_page=p
        )

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_out)
        print(f"Generated {filename} ({os.path.getsize(out_path)} bytes)")

def build_author_pages(books, repo_root, build_time_str):
    """Builds author.html (and author-2.html...) grouped by author."""
    # Group books by author
    author_map = {}
    for b in books:
        author_map.setdefault(b["author"], []).append(b)

    # Sort authors alphabetically, and books within each author
    sorted_authors = sorted(author_map.keys(), key=lambda a: a.strip().lower())
    for a in sorted_authors:
        author_map[a].sort(key=lambda b: sort_title_key(b["title"]))

    total_books = len(books)

    # A-Z jump links for authors
    author_letters = set()
    for a in sorted_authors:
        clean_a = a.strip()
        first_char = clean_a[0].upper() if clean_a and clean_a[0].isalpha() else "#"
        author_letters.add(first_char)

    sorted_letters = sorted([l for l in author_letters if l != "#"])
    if "#" in author_letters:
        sorted_letters.append("#")

    az_links = [f'<a href="#author-letter-{l}" class="az-link">{l}</a>' for l in sorted_letters]
    az_nav = f'<nav class="az-nav" aria-label="Author A to Z index">Jump: {" ".join(az_links)}</nav>' if az_links else ""

    # Check pagination: count total books across author groups
    # For pagination with authors, we paginate if total_books > PAGE_SIZE
    total_pages = max(1, (total_books + PAGE_SIZE - 1) // PAGE_SIZE) if total_books > 0 else 1

    seen_author_letters = set()
    current_book_count = 0
    page_num = 1
    current_page_groups = []

    for a in sorted_authors:
        b_list = author_map[a]
        clean_a = a.strip()
        first_char = clean_a[0].upper() if clean_a and clean_a[0].isalpha() else "#"

        letter_attr = ""
        if first_char not in seen_author_letters:
            seen_author_letters.add(first_char)
            letter_attr = f' id="author-letter-{first_char}"'

        group_html = f"""<section class="author-group"{letter_attr}>
  <h2 class="author-heading">{html.escape(a)}</h2>
  <ul class="book-list">
    {"".join(render_book_item(b) for b in b_list)}
  </ul>
</section>"""
        current_page_groups.append(group_html)
        current_book_count += len(b_list)

        # If page size exceeded and not the last author
        if current_book_count >= PAGE_SIZE and a != sorted_authors[-1]:
            content_html = "\n".join(current_page_groups)
            pagination_html = render_pagination("author", page_num, total_pages)
            filename = "author.html" if page_num == 1 else f"author-{page_num}.html"
            out_path = os.path.join(repo_root, filename)

            html_out = render_page(
                title_suffix="Author A→Z",
                current_view="author",
                content_html=content_html,
                total_books=total_books,
                build_time_str=build_time_str,
                az_nav_html=az_nav,
                pagination_html=pagination_html,
                current_page=page_num
            )
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html_out)
            print(f"Generated {filename} ({os.path.getsize(out_path)} bytes)")

            page_num += 1
            current_page_groups = []
            current_book_count = 0

    # Output remaining group for last page
    if current_page_groups or page_num == 1:
        content_html = "\n".join(current_page_groups)
        pagination_html = render_pagination("author", page_num, total_pages)
        filename = "author.html" if page_num == 1 else f"author-{page_num}.html"
        out_path = os.path.join(repo_root, filename)

        html_out = render_page(
            title_suffix="Author A→Z",
            current_view="author",
            content_html=content_html,
            total_books=total_books,
            build_time_str=build_time_str,
            az_nav_html=az_nav,
            pagination_html=pagination_html,
            current_page=page_num
        )
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_out)
        print(f"Generated {filename} ({os.path.getsize(out_path)} bytes)")

def build_404_page(repo_root, build_time_str):
    """Builds 404.html adhering to the same lightweight layout."""
    content_html = """<div style="margin: 30px 0; padding: 20px 0; border-top: 2px solid #000; border-bottom: 2px solid #000;">
  <h2 style="margin-top:0;">404 - Book or Page Not Found</h2>
  <p>The requested book or page does not exist in this library.</p>
  <div style="margin-top:20px;">
    <a href="index.html" class="download-btn">Return to Library</a>
  </div>
</div>"""

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <meta name="description" content="eShelf - Page Not Found">
  <title>eShelf - 404 Not Found</title>
  <style>{CSS_STYLES}</style>
</head>
<body>
  <div class="container">
    <header id="top">
      <h1>eShelf</h1>
    </header>
    {content_html}
    <footer>
      <div>Built: {build_time_str} · <a href="index.html" class="back-top">Home</a></div>
    </footer>
  </div>
</body>
</html>"""

    out_path = os.path.join(repo_root, "404.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(minify_html(page_html))
    print(f"Generated 404.html ({os.path.getsize(out_path)} bytes)")

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    build_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    print(f"--- eShelf Build starting ({build_time_str}) ---")
    books = scan_books(repo_root)
    print(f"Found {len(books)} books.")

    build_latest_pages(books, repo_root, build_time_str)
    build_title_pages(books, repo_root, build_time_str)
    build_author_pages(books, repo_root, build_time_str)
    build_404_page(repo_root, build_time_str)

    print("--- eShelf Build completed successfully ---")

if __name__ == "__main__":
    main()
