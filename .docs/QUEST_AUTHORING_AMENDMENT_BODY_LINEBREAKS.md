# Amendment: Scene Body Text Must Not Contain Hard Line Breaks Within Paragraphs

## The Problem

The YAML `|` block scalar preserves every line break literally. When body text is hard-wrapped in the YAML file — a sentence broken across two lines for readability — that line break is stored in the DB and rendered in-game as a mid-sentence break. This causes prose to split at arbitrary column widths rather than at paragraph boundaries.

**Wrong (hard-wrapped — will break mid-sentence in game):**
```yaml
body: |
  Morris calls at seven in the morning, which already tells you something — Morris
  is a noon-at-the-earliest kind of person, and a seven a.m. call means either
  the job is time-sensitive or something went wrong upstream.

  He doesn't explain which.
```

**Right (each paragraph is one unbroken line):**
```yaml
body: |
  Morris calls at seven in the morning, which already tells you something — Morris is a noon-at-the-earliest kind of person, and a seven a.m. call means either the job is time-sensitive or something went wrong upstream.

  He doesn't explain which.
```

## The Rule

Each paragraph in a `body` field must be written as a single continuous line in the YAML file, no matter how long. Paragraph breaks are represented by a single blank line between paragraphs, which the `|` scalar stores as `\n\n`. That double newline is the only intentional line break — everything else is the renderer's job.

This applies to all `body` fields on scenes. It also applies to `arrival_flavor` and `failure_arrival_flavor`, though those are single sentences and the problem rarely arises there.

## For Claude When Converting Specs to YAML

When generating YAML from a markdown spec, never introduce line breaks inside a paragraph to fit a column width. The spec may have prose wrapped at 80 characters for readability — do not carry that wrapping into the YAML output. Unwrap each paragraph into a single line before writing it to the `body` block.
