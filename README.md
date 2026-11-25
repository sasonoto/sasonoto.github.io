# sasonoto.github.io

Personal academic website of Sasonoto Hasbullah. Plain Jekyll 4, no plugins, built and deployed by GitHub Actions
(`.github/workflows/pages.yml`).

## Edit content
Everything visible lives in `_data/`:

| file | shows on |
|:--|:--|
| `profile.yml` | home (bio, interests, links), sidebar, page titles |
| `news.yml` | home, News |
| `papers.yml` | Research, CV |
| `projects.yml` | Projects |
| `teaching.yml` | Teaching, CV |
| `cv.yml` | CV (and Research experience on Research) |
| `nav.yml` | top menu |

The PDF CV is `files/Sasonoto_Hasbullah_CV.pdf`, the public copy (no phone number) built from the `.tex` in the
parent `cv/files/` folder.

## Blog
Add a post as `_posts/YYYY-MM-DD-short-title.md` with front matter `title:` and `description:`. While `_posts/` is empty,
`/blog/` shows "Coming soon" and the menu shows a "soon" label; both disappear with the first post.

## Preview locally
`./site serve` (needs Homebrew `ruby@3.4`; first time: `bundle install`), then http://localhost:4000.

## Database copy
`./site db sync` copies `_data/*.yml` into the `site` schema on Supabase and chicago-o. See `db/README.md`.
