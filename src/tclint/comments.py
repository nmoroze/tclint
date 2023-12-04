from collections import defaultdict

from tclint.syntax_tree import Visitor
from tclint.violations import violation_types


class CommentVisitor(Visitor):
    """Scans the tree for lint waiver comments."""

    def __init__(self):
        # line -> [rule]
        self.ignore_lines = defaultdict(set)

        self._disable_regions = {
            # rule -> line
        }

    def run(self, tree):
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

        rules = []
        if len(split) > 1:
            rest = split[-1]
            rules = rest.split("--", 1)[0]
            rules = rules.replace(" ", "")
            rules = rules.split(",")

        if not rules:
            # default if no rules specified is all violation types
            rules = violation_types

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
