# Local issue tracker

Each Markdown file in `issues/` is one issue. Frontmatter stores its tracker metadata.

- `status: open|closed`
- `labels`: issue labels
- `parent`: the map issue filename for child issues
- `assignee`: empty means unclaimed
- `blocked_by`: open issue filenames that must close first

The frontier is the ordered set of open, unassigned child issues whose `blocked_by` issues are all closed.

