# eShelf

A minimal, ultra-lightweight static website built specifically for browsing and downloading DRM-free EPUB books directly from the experimental web browser on the **Kobo Nia** (and other e-ink devices with slow processors, limited RAM, and legacy WebKit browsers).

---

## Design Principles

- **Zero Bloat:** No frameworks, no CSS libraries, no web fonts, no icons, no cover images, no animations or transitions, no external CDN calls.
- **Pure High-Contrast E-Ink UI:** True black (`#000000`) on white (`#ffffff`). No greys that wash out or cause dithering artifacts on e-ink screens.
- **Large Tap Targets:** All interactive links and download buttons have a minimum tap height of 48px to prevent missed taps on resistive/IR touchscreens.
- **Offline / No-JS Compatible:** Built as static pre-rendered HTML pages. Works 100% with JavaScript disabled.
- **Tiny ES5 Enhancement:** An optional inline script (under 1.2 KB) written in strict ES5 provides live instant search filtering when JavaScript is enabled. If JavaScript is disabled, the search box is hidden so there are no dead controls.
- **Lightweight Footprint:** Under 10 KB per page (well below the 50 KB budget), ensuring instantaneous loading and low memory usage.

---

## Repository Structure

```text
/
├── books/
│   ├── Arthur Conan Doyle/
│   │   ├── The Adventures of Sherlock Holmes.epub
│   │   └── metadata.json          (optional override)
│   ├── Jane Austen/
│   │   └── Pride and Prejudice.epub
│   └── Mary Shelley/
│       └── Frankenstein.epub
├── build/
│   ├── build.py                   (Python 3, standard library only)
│   └── create_samples.py          (helper to generate test EPUBs)
├── .github/workflows/
│   └── build.yml                  (GitHub Action: builds and deploys on push)
├── index.html                     (generated: Latest added, newest first)
├── title.html                     (generated: Title A→Z, ignoring The/A/An)
├── author.html                    (generated: Author A→Z, grouped by author)
├── 404.html                       (minimal 404 page)
├── .nojekyll                      (disables Jekyll processing on GitHub Pages)
└── README.md
```

---

## Adding Books

1. Create a directory inside `books/` named after the author:
   ```text
   books/George Orwell/
   ```
2. Place your `.epub` (or `.kepub.epub`, `.pdf`, `.cbz`) file inside that folder:
   ```text
   books/George Orwell/1984.epub
   ```
3. Commit and push:
   ```bash
   git add books/
   git commit -m "Add 1984 by George Orwell"
   git push origin main
   ```
   GitHub Actions will automatically run `build.py` and publish the updated catalog to GitHub Pages.

### Filename Formatting & Title Cleanup
- Directory name = Author name
- Filename without extension = Book title
- Underscores (`_`) are automatically replaced with spaces.
- Multiple spaces are collapsed.
- Supported file types: `.epub`, `.kepub.epub`, `.pdf`, `.cbz`, `.cbr`, `.mobi`, `.azw3`, `.fb2`, `.djvu`.

### Optional Metadata Overrides (`metadata.json`)
If a filename cannot easily represent the desired title or author, place a `metadata.json` inside the author's folder:

```json
{
  "author": "Sir Arthur Conan Doyle",
  "The Adventures of Sherlock Holmes.epub": {
    "title": "The Adventures of Sherlock Holmes",
    "author": "Sir Arthur Conan Doyle"
  }
}
```

---

## Running the Build Locally

You only need **Python 3** (version 3.8+). No `pip` packages required:

```bash
python3 build/build.py
```

This will:
- Scan `books/` recursively.
- Extract file sizes and "Date added" timestamps (from `git log --diff-filter=A`, falling back to file modification time).
- Verify GitHub size constraints (< 100 MB hard limit, warning at > 50 MB).
- Generate `index.html`, `title.html`, `author.html`, and `404.html`.
- Paginate catalogs with > 200 books (`index-2.html`, etc.).

---

## Setting Up GitHub Pages

1. Push this repository to GitHub.
2. In your GitHub repository, navigate to **Settings** > **Pages**.
3. Under **Build and deployment** > **Source**, select **GitHub Actions**.
4. The workflow in `.github/workflows/build.yml` will automatically trigger and deploy your site to:
   ```text
   https://<your-username>.github.io/<repository-name>/
   ```

---

## Important Limits & Public Warning

- **100 MB GitHub File Limit:** GitHub strictly rejects files larger than 100 MB. `build.py` will abort if any book exceeds 100 MB.
- **50 MB Warning:** Files over 50 MB trigger a warning during the build.
- **1 GB Recommended Repo Size:** Keep your repository under ~1 GB for smooth git operations and fast deployment.
- **Public Access Notice:** Standard GitHub Pages sites are **public to anyone on the internet**. Only host DRM-free titles that you have the legal right to distribute, such as public domain books (from [Standard Ebooks](https://standardebooks.org/) or [Project Gutenberg](https://www.gutenberg.org/)) or Creative Commons works. If you wish to host personal private purchases, consider running eShelf on a local network server (like a Raspberry Pi running a simple HTTP server) or using a private repository with GitHub Enterprise/Pro private pages.

---

## Using on Your Kobo Nia

1. Connect your Kobo Nia to Wi-Fi.
2. Open the main menu: **More** > **Beta Features** > **Web Browser**.
3. Enter your eShelf URL:
   ```text
   https://<your-username>.github.io/<repository-name>/
   ```
4. Tap the browser menu and select **Add to Bookmarks** (or set it as your browser start page) for one-tap access.
5. Tap the **Download** button next to any book. The Kobo browser will download the file directly to device storage.
6. **Importing into Library:** Once downloaded, tap the home button or close the browser. The Kobo will automatically scan its storage and import the new EPUB into your device library, allowing you to read it with custom fonts, margins, annotations, and reading progress tracking.
