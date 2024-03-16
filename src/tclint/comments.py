from collections import defaultdict

from tclint.syntax_tree import Visitor
from tclint.violations import ALL_RULES, Rule


class CommentVisitor(Visitor):
    """Scans the tree for lint waiver comments."""

    def __init__(self):
        # line -> [rule]
        self.ignore_lines = defaultdict(set)

        self._disable_regions = {
            # rule -> line
        }

    def run(self, tree, path):
        self._path = path
        tree.accept(self, recurse=True)

        # resolve remaining disabled regions
        last_line = tree.end_pos[0]
        for rule, start_line in self._disable_regions.items():
            for line in range(start_line, last_line + 1):
                self.ignore_lines[line].add(rule)

        return self.ignore_lines

    def visit_comment(self, comment):
        contents = comment.value.strip()

        if not contents.startswith("tclint-"):
            return

        split = contents.split(" ", 1)

        command = split[0]

        rule_strs = []
        if len(split) > 1:
            rest = split[-1]
            rule_strs = rest.split("--", 1)[0]
            rule_strs = rule_strs.replace(" ", "")
            rule_strs = rule_strs.split(",")

        rules = []
        if not rule_strs:
            # default if no rules specified is all violation types
            rules = ALL_RULES
        else:
            for rule in rule_strs:
                try:
                    rules.append(Rule(rule))
                except ValueError:
                    self._warning(
                        f"unknown rule '{rule}' provided to '{command}'", comment.pos
                    )

        if command == "tclint-disable":
            for rule in rules:
                # if in dictionary, already disabled - this has no effect
                if rule not in self._disable_regions:
                    self._disable_regions[rule] = comment.line
        elif command == "tclint-disable-line":
            line = comment.line
            self.ignore_lines[line].update(rules)
        elif command == "tclint-disable-next-line":
            line = comment.line + 1
            self.ignore_lines[line].update(rules)
        elif command == "tclint-enable":
            for rule in rules:
                if rule in self._disable_regions:
                    disable_start_line = self._disable_regions[rule]
                    disable_end_line = comment.line

                    for line in range(disable_start_line, disable_end_line + 1):
                        self.ignore_lines[line].add(rule)

                    del self._disable_regions[rule]
        else:
            self._warning(
                f"comment starts with '{command}', which looks like a tclint keyword."
                " Is this a typo?",
                comment.pos,
            )

    def _warning(self, message, pos):
        # TODO: formal warning mechanism
        prefix = self._path if self._path is not None else "(stdin)"
        print(f"Warning: {prefix}:{pos[0]}:{pos[1]}: {message}")
